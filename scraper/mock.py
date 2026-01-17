"""
Mock scraper for development and testing.
Generates realistic placeholder data without external requests.
"""

import random
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from core.models import PropertyListing, SearchCriteria


class MockScraper:
    """Mock scraper that generates placeholder property listings."""

    # Sample data for generating realistic listings
    LOCATIONS = {
        "london": ["Hackney", "Islington", "Camden", "Lewisham", "Southwark", "Tower Hamlets"],
        "manchester": ["Salford", "Trafford", "Stockport", "Oldham", "Rochdale", "Bury"],
        "birmingham": ["Edgbaston", "Selly Oak", "Erdington", "Sutton Coldfield", "Moseley"],
        "leeds": ["Headingley", "Roundhay", "Horsforth", "Moortown", "Chapel Allerton"],
        "liverpool": ["Anfield", "Everton", "Toxteth", "Wavertree", "Allerton"],
    }

    PROPERTY_TYPES = ["terraced", "semi-detached", "detached", "flat", "maisonette"]

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize mock scraper.

        Args:
            seed: Optional random seed for reproducible results.
        """
        if seed is not None:
            random.seed(seed)

    async def search(self, criteria: SearchCriteria) -> List[PropertyListing]:
        """
        Generate mock property listings matching criteria.

        Args:
            criteria: Search parameters.

        Returns:
            List of mock PropertyListing objects.
        """
        location_key = criteria.location.lower().strip()
        areas = self.LOCATIONS.get(location_key, [location_key.title()])

        # Generate 5-15 mock listings
        num_listings = random.randint(5, 15)
        listings = []

        for _ in range(num_listings):
            listing = self._generate_listing(
                area=random.choice(areas),
                city=criteria.location.title(),
                min_beds=criteria.min_beds,
                max_beds=criteria.max_beds,
                min_baths=criteria.min_baths,
            )
            listings.append(listing)

        return listings

    async def get_listing_details(self, listing_id: str) -> Optional[PropertyListing]:
        """
        Generate a mock listing with the given ID.

        Args:
            listing_id: Listing identifier.

        Returns:
            Mock PropertyListing.
        """
        # Generate a deterministic listing based on ID
        random.seed(hash(listing_id) % (2**32))
        listing = self._generate_listing(
            area="Sample Area",
            city="Sample City",
            min_beds=1,
            max_beds=5,
            min_baths=1,
        )
        listing.id = listing_id
        return listing

    def _generate_listing(
        self,
        area: str,
        city: str,
        min_beds: int = 1,
        max_beds: Optional[int] = None,
        min_baths: int = 1,
    ) -> PropertyListing:
        """Generate a single mock listing."""
        beds = random.randint(min_beds, max_beds or min_beds + 3)
        baths = random.randint(min_baths, max(min_baths, beds - 1))

        # Base price calculation (rough UK averages)
        base_price = 150000 + (beds * 50000) + random.randint(-30000, 50000)

        # Apply location multiplier
        if city.lower() == "london":
            base_price *= 2.5
        elif city.lower() in ["manchester", "birmingham"]:
            base_price *= 1.3

        # Round to nearest 5000
        asking_price = round(base_price / 5000) * 5000

        # Generate estimated value (asking price +/- 15%)
        value_variance = random.uniform(-0.15, 0.15)
        estimated_value = round(asking_price * (1 + value_variance) / 1000) * 1000

        # Days on market
        days_on_market = random.randint(1, 180)

        return PropertyListing(
            id=str(uuid4())[:8],
            address=f"{random.randint(1, 200)} {random.choice(['High', 'Church', 'Station', 'Park', 'Victoria', 'Queens'])} {random.choice(['Street', 'Road', 'Lane', 'Avenue', 'Close'])}",
            area=area,
            city=city,
            postcode=f"{city[:2].upper()}{random.randint(1, 20)} {random.randint(1, 9)}{random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}",
            property_type=random.choice(self.PROPERTY_TYPES),
            bedrooms=beds,
            bathrooms=baths,
            asking_price=asking_price,
            estimated_value=estimated_value,
            days_on_market=days_on_market,
            listed_date=(datetime.now() - timedelta(days=days_on_market)).isoformat(),
            source="mock",
            url=f"https://example.com/property/{uuid4()}",
        )
