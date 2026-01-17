"""
Tests for Auction House London scraper.

Unit tests use a saved HTML snapshot to avoid hitting the live site.
Integration test is marked to run only on explicit request.
"""

import pytest
from pathlib import Path
from datetime import date

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.auction_house_london import (
    AuctionHouseLondonParser,
    AuctionListingNormaliser,
    AuctionHouseLondonScraper,
    AuctionListing,
)
from core.models import PropertyListing


# =============================================================================
# Fixtures
# =============================================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_html():
    """Load the sample HTML fixture."""
    fixture_path = FIXTURES_DIR / "auction_house_london_sample.html"
    return fixture_path.read_text()


@pytest.fixture
def sample_auction_listing():
    """Create a sample AuctionListing for testing normalisation."""
    return AuctionListing(
        source="AuctionHouseLondon",
        listing_id="AHL-LOT-1",
        lot_number="1",
        title="123 Test Street",
        address="123 Test Street, Camden, London, NW1 8AB",
        postcode="NW1 8AB",
        guide_price=350000,
        guide_price_formatted="£350,000+",
        tenure="Freehold",
        property_type="Terraced House",
        auction_date=date(2024, 2, 15),
        listing_url="https://auctionhouselondon.co.uk/lot/123-test-street-123456",
        raw_description="",
        slug="123-test-street-123456",
    )


# =============================================================================
# Unit Tests: Parser
# =============================================================================

class TestAuctionHouseLondonParser:
    """Tests for the RSC payload parser."""

    def test_parse_extracts_all_lots(self, sample_html):
        """Parser should extract all lots from the sample HTML."""
        listings = AuctionHouseLondonParser.parse(sample_html)

        assert len(listings) == 4
        assert listings[0].lot_number == "1"
        assert listings[1].lot_number == "2"
        assert listings[2].lot_number == "3"
        assert listings[3].lot_number == "4"

    def test_parse_extracts_addresses(self, sample_html):
        """Parser should correctly extract full addresses."""
        listings = AuctionHouseLondonParser.parse(sample_html)

        assert "123 Test Street" in listings[0].address
        assert "Camden" in listings[0].address
        assert "NW1 8AB" in listings[0].address

    def test_parse_extracts_prices(self, sample_html):
        """Parser should correctly extract guide prices."""
        listings = AuctionHouseLondonParser.parse(sample_html)

        assert listings[0].guide_price == 350000
        assert listings[1].guide_price == 275000
        assert listings[2].guide_price == 150000
        assert listings[3].guide_price == 425000

    def test_parse_extracts_property_types(self, sample_html):
        """Parser should correctly extract property types."""
        listings = AuctionHouseLondonParser.parse(sample_html)

        assert listings[0].property_type == "Terraced House"
        assert listings[1].property_type == "Flat"
        assert listings[2].property_type == "Land"
        assert listings[3].property_type == "Mixed Use"

    def test_parse_extracts_tenure(self, sample_html):
        """Parser should correctly extract tenure type."""
        listings = AuctionHouseLondonParser.parse(sample_html)

        assert listings[0].tenure == "Freehold"
        assert listings[1].tenure == "Leasehold"

    def test_parse_extracts_postcodes(self, sample_html):
        """Parser should extract postcodes from addresses."""
        listings = AuctionHouseLondonParser.parse(sample_html)

        assert listings[0].postcode == "NW1 8AB"
        assert listings[1].postcode == "SE10 9NN"
        assert listings[2].postcode == "CR0 1XX"

    def test_parse_builds_urls(self, sample_html):
        """Parser should build correct listing URLs from slugs."""
        listings = AuctionHouseLondonParser.parse(sample_html)

        assert listings[0].listing_url == "https://auctionhouselondon.co.uk/lot/123-test-street-camden-london-nw1-8ab-123456"

    def test_parse_extracts_auction_date(self, sample_html):
        """Parser should extract the auction date."""
        listings = AuctionHouseLondonParser.parse(sample_html)

        assert listings[0].auction_date == date(2024, 2, 15)

    def test_parse_handles_empty_html(self):
        """Parser should return empty list for empty HTML."""
        listings = AuctionHouseLondonParser.parse("")
        assert listings == []

    def test_parse_handles_no_lots(self):
        """Parser should return empty list when no lots found."""
        html = "<html><body>No auction data</body></html>"
        listings = AuctionHouseLondonParser.parse(html)
        assert listings == []


# =============================================================================
# Unit Tests: Normaliser
# =============================================================================

class TestAuctionListingNormaliser:
    """Tests for the listing normaliser."""

    def test_normalise_creates_property_listing(self, sample_auction_listing):
        """Normaliser should create a valid PropertyListing."""
        result = AuctionListingNormaliser.normalise(sample_auction_listing)

        assert isinstance(result, PropertyListing)
        assert result.source == "AuctionHouseLondon"

    def test_normalise_maps_price(self, sample_auction_listing):
        """Normaliser should map guide price to asking price."""
        result = AuctionListingNormaliser.normalise(sample_auction_listing)

        assert result.asking_price == 350000
        assert result.estimated_value == 350000  # Conservative default

    def test_normalise_maps_address_fields(self, sample_auction_listing):
        """Normaliser should correctly map address components."""
        result = AuctionListingNormaliser.normalise(sample_auction_listing)

        assert result.address == "123 Test Street, Camden, London, NW1 8AB"
        assert result.postcode == "NW1 8AB"

    def test_normalise_maps_property_type(self, sample_auction_listing):
        """Normaliser should normalise property type."""
        result = AuctionListingNormaliser.normalise(sample_auction_listing)

        assert result.property_type == "terraced"

    def test_normalise_flat_type(self):
        """Normaliser should map Flat to flat."""
        listing = AuctionListing(
            address="Test Flat",
            property_type="Flat",
            guide_price=100000,
            lot_number="1",
        )
        result = AuctionListingNormaliser.normalise(listing)

        assert result.property_type == "flat"

    def test_normalise_land_type(self):
        """Normaliser should map Land to land."""
        listing = AuctionListing(
            address="Test Land",
            property_type="Land",
            guide_price=50000,
            lot_number="1",
        )
        result = AuctionListingNormaliser.normalise(listing)

        assert result.property_type == "land"

    def test_normalise_generates_stable_id(self, sample_auction_listing):
        """Normaliser should generate a stable ID."""
        result1 = AuctionListingNormaliser.normalise(sample_auction_listing)
        result2 = AuctionListingNormaliser.normalise(sample_auction_listing)

        assert result1.id == result2.id
        assert result1.id.startswith("AHL-1-")

    def test_normalise_includes_url(self, sample_auction_listing):
        """Normaliser should include the listing URL."""
        result = AuctionListingNormaliser.normalise(sample_auction_listing)

        assert result.url == sample_auction_listing.listing_url

    def test_normalise_sets_defaults_for_missing_fields(self, sample_auction_listing):
        """Normaliser should set sensible defaults for unavailable fields."""
        result = AuctionListingNormaliser.normalise(sample_auction_listing)

        # Auction listings don't have bedroom/bathroom counts
        assert result.bedrooms == 0
        assert result.bathrooms == 0
        assert result.days_on_market == 0


# =============================================================================
# Unit Tests: Postcode Extraction
# =============================================================================

class TestPostcodeExtraction:
    """Tests for postcode extraction from addresses."""

    @pytest.mark.parametrize("address,expected", [
        ("123 Test St, London, NW1 8AB", "NW1 8AB"),
        ("Flat 5, London, SE10 9NN", "SE10 9NN"),
        ("Property, Reading, RG1 2PQ", "RG1 2PQ"),
        ("House, Manchester, M1 1AA", "M1 1AA"),
        ("Building, Edinburgh, EH1 1AA", "EH1 1AA"),
        ("No postcode here", ""),
    ])
    def test_extract_postcode(self, address, expected):
        """Should extract various UK postcode formats."""
        result = AuctionHouseLondonParser._extract_postcode(address)
        assert result == expected


# =============================================================================
# Integration Test (requires network)
# =============================================================================

@pytest.mark.integration
@pytest.mark.skip(reason="Requires network access - run explicitly with -m integration")
class TestAuctionHouseLondonScraperIntegration:
    """
    Integration tests that hit the live website.

    Run explicitly with: pytest -m integration tests/test_auction_house_london.py
    """

    def test_fetch_returns_listings(self):
        """Should fetch at least one listing from the live site."""
        scraper = AuctionHouseLondonScraper()

        listings = scraper.fetch_current_auction()

        assert len(listings) >= 1
        assert all(isinstance(l, PropertyListing) for l in listings)

    def test_listings_have_required_fields(self):
        """All listings should have required fields populated."""
        scraper = AuctionHouseLondonScraper()

        listings = scraper.fetch_current_auction()

        for listing in listings:
            assert listing.id
            assert listing.address
            assert listing.asking_price > 0
            assert listing.url.startswith("https://")
            assert listing.source == "AuctionHouseLondon"

    def test_listings_have_valid_urls(self):
        """All listing URLs should be valid and verifiable."""
        scraper = AuctionHouseLondonScraper()

        listings = scraper.fetch_current_auction()

        for listing in listings:
            assert "auctionhouselondon.co.uk/lot/" in listing.url


# =============================================================================
# Rate Limiting Test
# =============================================================================

class TestRateLimiting:
    """Tests for rate limiting behaviour."""

    def test_scraper_has_rate_limit_config(self):
        """Scraper should have rate limiting configured."""
        from scraper.auction_house_london import REQUEST_DELAY_SECONDS

        assert REQUEST_DELAY_SECONDS >= 1.5

    def test_scraper_has_custom_user_agent(self):
        """Scraper should use custom user agent."""
        from scraper.auction_house_london import USER_AGENT

        assert "AxisAllocationResearchBot" in USER_AGENT
        assert "info@axisallocation.com" in USER_AGENT
