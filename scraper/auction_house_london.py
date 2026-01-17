"""
Auction House London scraper.

Extracts live auction listings from auctionhouselondon.co.uk for analysis.
Only fetches text metadata — no images, PDFs, or copyrighted layouts.

Rate-limited and legally cautious by design.
"""

import re
import time
import hashlib
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional
from urllib.parse import urljoin

import requests

from core.models import PropertyListing, SearchCriteria


# =============================================================================
# Configuration
# =============================================================================

BASE_URL = "https://auctionhouselondon.co.uk"
CURRENT_AUCTION_URL = f"{BASE_URL}/current-auction"
USER_AGENT = "AxisAllocationResearchBot/1.0 (contact: info@axisallocation.com)"
REQUEST_DELAY_SECONDS = 1.5
REQUEST_TIMEOUT_SECONDS = 30


# =============================================================================
# Raw Listing Data Structure
# =============================================================================

@dataclass
class AuctionListing:
    """
    Raw listing data extracted from Auction House London.
    Intermediate format before normalisation to PropertyListing.
    """
    source: str = "AuctionHouseLondon"
    listing_id: str = ""
    lot_number: str = ""
    title: str = ""
    address: str = ""
    postcode: str = ""
    guide_price: int = 0
    guide_price_formatted: str = ""
    tenure: str = ""
    property_type: str = ""
    auction_date: Optional[date] = None
    listing_url: str = ""
    raw_description: str = ""
    slug: str = ""


# =============================================================================
# Parser
# =============================================================================

class AuctionHouseLondonParser:
    """
    Parser for Auction House London RSC (React Server Components) page format.
    Extracts lot data from embedded JSON in the page source.
    """

    # Regex patterns for RSC-escaped JSON fields
    FIELD_PATTERNS = {
        "fullAddress": r'\\"fullAddress\\":\\"([^"\\]+(?:\\u[0-9a-fA-F]{4}[^"\\]*)*)\\"',
        "guidePrice": r'\\"guidePrice\\":(\d+)',
        "guidePriceFormatted": r'\\"guidePriceFormatted\\":\\"([^"\\]+)\\"',
        "lotNumber": r'\\"lotNumber\\":\\"(\d+)\\"',
        "propertyType": r'\\"propertyType\\":\\"([^"\\]+)\\"',
        "slug": r'\\"slug\\":\\"([^"\\]+)\\"',
        "tenureType": r'\\"tenureType\\":\\"([^"\\]+)\\"',
        "auctionDate": r'\\"auctionDate\\":\\"([^"\\]+)\\"',
    }

    @classmethod
    def parse(cls, html: str) -> list[AuctionListing]:
        """
        Parse auction listings from HTML containing RSC payload.

        Args:
            html: Raw HTML from the current-auction page.

        Returns:
            List of AuctionListing objects.
        """
        listings = []

        # Extract auction date (applies to all lots)
        auction_date = cls._extract_auction_date(html)

        # Split by displayOrder to find individual lot sections
        # Each lot in the RSC payload starts with displayOrder
        sections = re.split(r'(?=\\"displayOrder\\":\d+)', html)

        for section in sections:
            # Must contain fullAddress to be a valid lot section
            if '\\"fullAddress\\"' not in section:
                continue

            listing = cls._parse_section(section, auction_date)
            if listing and listing.lot_number:
                listings.append(listing)

        # Sort by lot number
        listings.sort(key=lambda x: int(x.lot_number) if x.lot_number.isdigit() else 0)

        return listings

    @classmethod
    def _extract_auction_date(cls, html: str) -> Optional[date]:
        """Extract the auction date from the page."""
        match = re.search(cls.FIELD_PATTERNS["auctionDate"], html)
        if match:
            try:
                # Format: 2024-02-12T00:00:00.000Z or similar
                date_str = match.group(1)
                return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
            except (ValueError, TypeError):
                pass
        return None

    @classmethod
    def _parse_section(cls, section: str, auction_date: Optional[date]) -> Optional[AuctionListing]:
        """Parse a single lot section."""
        listing = AuctionListing()
        listing.auction_date = auction_date

        # Extract each field
        for field, pattern in cls.FIELD_PATTERNS.items():
            match = re.search(pattern, section)
            if match:
                value = cls._unescape_value(match.group(1))

                if field == "fullAddress":
                    listing.address = value
                    listing.title = value.split(",")[0] if value else ""
                    listing.postcode = cls._extract_postcode(value)
                elif field == "guidePrice":
                    listing.guide_price = int(value)
                elif field == "guidePriceFormatted":
                    listing.guide_price_formatted = value
                elif field == "lotNumber":
                    listing.lot_number = value
                    listing.listing_id = f"AHL-LOT-{value}"
                elif field == "propertyType":
                    listing.property_type = value
                elif field == "slug":
                    listing.slug = value
                    listing.listing_url = f"{BASE_URL}/lot/{value}"
                elif field == "tenureType":
                    listing.tenure = value

        return listing if listing.address else None

    @staticmethod
    def _unescape_value(value: str) -> str:
        """Unescape RSC-encoded string values."""
        # Handle Unicode escapes
        value = re.sub(
            r"\\u([0-9a-fA-F]{4})",
            lambda m: chr(int(m.group(1), 16)),
            value,
        )
        # Handle common escapes
        value = value.replace('\\"', '"')
        value = value.replace("\\n", "\n")
        value = value.replace("\\t", "\t")
        return value

    @staticmethod
    def _extract_postcode(address: str) -> str:
        """Extract UK postcode from address string."""
        # UK postcode pattern: AA9A 9AA, A9A 9AA, A9 9AA, A99 9AA, AA9 9AA, AA99 9AA
        pattern = r"([A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2})"
        match = re.search(pattern, address.upper())
        return match.group(1) if match else ""


# =============================================================================
# Normaliser
# =============================================================================

class AuctionListingNormaliser:
    """
    Converts raw AuctionListing to the engine's PropertyListing schema.
    """

    # Property type mapping to standardised values
    # Order matters for fuzzy matching - more specific terms first
    TYPE_MAPPING = {
        "terraced house": "terraced",
        "semi-detached house": "semi-detached",
        "detached house": "detached",
        "terraced": "terraced",
        "semi-detached": "semi-detached",
        "detached": "detached",
        "house": "house",
        "flat": "flat",
        "apartment": "flat",
        "maisonette": "maisonette",
        "bungalow": "bungalow",
        "land": "land",
        "commercial": "commercial",
        "mixed use": "mixed-use",
        "block of apartments": "block-of-flats",
        "restaurant": "commercial",
        "shop": "commercial",
        "office": "commercial",
        "warehouse": "commercial",
        "garage": "garage",
    }

    @classmethod
    def normalise(cls, auction_listing: AuctionListing) -> PropertyListing:
        """
        Convert AuctionListing to PropertyListing.

        Note: Auction listings don't have bedroom/bathroom counts or
        estimated values, so we use sensible defaults and flag for
        manual review.
        """
        # Normalise property type
        prop_type_lower = auction_listing.property_type.lower()
        normalised_type = cls.TYPE_MAPPING.get(
            prop_type_lower,
            cls._fuzzy_match_type(prop_type_lower),
        )

        # Extract city from address
        city = cls._extract_city(auction_listing.address)

        # Extract area (typically first part after property name)
        area = cls._extract_area(auction_listing.address)

        # Generate stable ID
        stable_id = cls._generate_stable_id(auction_listing)

        return PropertyListing(
            id=stable_id,
            address=auction_listing.address,
            area=area,
            city=city,
            postcode=auction_listing.postcode,
            property_type=normalised_type,
            bedrooms=0,  # Not available from auction listing
            bathrooms=0,  # Not available from auction listing
            asking_price=auction_listing.guide_price,
            estimated_value=auction_listing.guide_price,  # Conservative: assume guide = value
            days_on_market=0,  # Auction listings don't have this
            listed_date=datetime.now().isoformat(),
            source="AuctionHouseLondon",
            url=auction_listing.listing_url,
            description=f"Lot {auction_listing.lot_number}: {auction_listing.property_type}. "
                        f"Tenure: {auction_listing.tenure}. "
                        f"Guide price: {auction_listing.guide_price_formatted}",
            features=[
                f"Lot: {auction_listing.lot_number}",
                f"Tenure: {auction_listing.tenure}",
                f"Type: {auction_listing.property_type}",
            ],
        )

    @classmethod
    def _fuzzy_match_type(cls, prop_type: str) -> str:
        """Attempt fuzzy matching for unknown property types."""
        for key, value in cls.TYPE_MAPPING.items():
            if key in prop_type:
                return value
        return "other"

    @staticmethod
    def _extract_city(address: str) -> str:
        """Extract city from address (typically second-to-last or third-to-last part)."""
        parts = [p.strip() for p in address.split(",")]
        if len(parts) >= 3:
            # Last part is usually postcode, second-to-last is county/region
            # City is often third-to-last
            return parts[-3] if len(parts) > 3 else parts[-2]
        elif len(parts) == 2:
            return parts[-1]
        return ""

    @staticmethod
    def _extract_area(address: str) -> str:
        """Extract area/neighbourhood from address."""
        parts = [p.strip() for p in address.split(",")]
        if len(parts) >= 2:
            return parts[1] if len(parts) > 2 else parts[0]
        return ""

    @staticmethod
    def _generate_stable_id(listing: AuctionListing) -> str:
        """Generate a stable ID for the listing based on content."""
        # Use lot number and address for stability
        content = f"{listing.lot_number}:{listing.address}:{listing.guide_price}"
        hash_val = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"AHL-{listing.lot_number}-{hash_val}"


# =============================================================================
# Scraper
# =============================================================================

class AuctionHouseLondonScraper:
    """
    Production-safe scraper for Auction House London.

    Features:
    - Rate-limited requests (≥1.5s between calls)
    - Custom User-Agent for identification
    - Graceful error handling
    - No parallel requests
    - Text-only extraction (no images/PDFs)
    """

    def __init__(self):
        self._last_request_time: float = 0
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
        })

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < REQUEST_DELAY_SECONDS:
            time.sleep(REQUEST_DELAY_SECONDS - elapsed)
        self._last_request_time = time.time()

    def fetch_current_auction(self) -> list[PropertyListing]:
        """
        Fetch all listings from the current auction.

        Returns:
            List of PropertyListing objects.

        Raises:
            requests.RequestException: On network errors.
            ValueError: On parsing errors.
        """
        self._rate_limit()

        response = self._session.get(
            CURRENT_AUCTION_URL,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        # Parse raw listings
        raw_listings = AuctionHouseLondonParser.parse(response.text)

        # Return empty list if no listings found
        # This is valid - auctions may not always have active listings
        if not raw_listings:
            return []

        # Normalise to PropertyListing
        return [
            AuctionListingNormaliser.normalise(listing)
            for listing in raw_listings
        ]

    async def search(self, criteria: SearchCriteria) -> list[PropertyListing]:
        """
        Search for auction listings matching criteria.

        Note: Auction listings are limited — filtering is done post-fetch.

        Args:
            criteria: Search parameters.

        Returns:
            List of matching PropertyListing objects.
        """
        all_listings = self.fetch_current_auction()

        # Filter by location if specified
        if criteria.location:
            location_lower = criteria.location.lower()
            all_listings = [
                l for l in all_listings
                if location_lower in l.city.lower()
                or location_lower in l.area.lower()
                or location_lower in l.postcode.lower()
            ]

        # Filter by max price if specified
        if criteria.max_price:
            all_listings = [
                l for l in all_listings
                if l.asking_price <= criteria.max_price
            ]

        return all_listings

    async def get_listing_details(self, listing_id: str) -> Optional[PropertyListing]:
        """
        Get details for a specific listing.

        Args:
            listing_id: Listing ID (format: AHL-{lot}-{hash}).

        Returns:
            PropertyListing if found, None otherwise.
        """
        # For auction listings, we need to fetch all and filter
        all_listings = self.fetch_current_auction()

        for listing in all_listings:
            if listing.id == listing_id:
                return listing

        return None

    def close(self) -> None:
        """Close the session."""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# =============================================================================
# Convenience Functions
# =============================================================================

def fetch_auction_listings() -> list[PropertyListing]:
    """
    Fetch all current auction listings.

    Convenience function for quick access.

    Returns:
        List of PropertyListing objects.
    """
    with AuctionHouseLondonScraper() as scraper:
        return scraper.fetch_current_auction()


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    print("Fetching Auction House London listings...")
    print(f"User-Agent: {USER_AGENT}")
    print(f"Rate limit: {REQUEST_DELAY_SECONDS}s between requests")
    print()

    try:
        listings = fetch_auction_listings()
        print(f"Found {len(listings)} listings:\n")

        for listing in listings[:10]:  # Show first 10
            print(f"ID: {listing.id}")
            print(f"  Address: {listing.address}")
            print(f"  Price: £{listing.asking_price:,}")
            print(f"  Type: {listing.property_type}")
            print(f"  URL: {listing.url}")
            print()

        if len(listings) > 10:
            print(f"... and {len(listings) - 10} more listings")

    except Exception as e:
        print(f"Error: {e}")
