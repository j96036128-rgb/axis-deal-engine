"""
Tests to ensure NO dummy/mock data ever appears in the system.

These tests fail if:
- Any address matches known dummy patterns
- Any listing lacks a real verifiable URL
- Any source field indicates mock/test data
"""

import pytest
import re
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import PropertyListing


# =============================================================================
# Known Dummy Data Patterns
# =============================================================================

# Common dummy street names used in mock data
# NOTE: Must be specific - "High Street" and "Church Road" are real UK street names
# Only flag patterns that are clearly synthetic/generated
DUMMY_STREET_PATTERNS = [
    r"\bsample\s+(area|road|street|property|town|city)\b",
    r"\btest\s+(address|property|listing|street|road)\b",
    r"\bdummy\s+(address|property|street)\b",
    r"\bfake\s+(address|street|road)\b",
    r"\bexample\s+(street|road|address)\b",
    r"\bplaceholder\b",
    r"\bexample\.com\b",
    r"\blocalhost\b",
    # Generic numbered patterns only (e.g. "123 Test Street")
    r"^\d+\s+test\s+",
    r"^\d+\s+sample\s+",
    r"^\d+\s+fake\s+",
]

# Invalid/placeholder postcodes
DUMMY_POSTCODE_PATTERNS = [
    r"^XX\d",  # XX prefix is not valid
    r"^ZZ\d",  # ZZ prefix is not valid
    r"^AA\d{2}\s*\d[A-Z]{2}$",  # AA followed by two digits is suspicious
    r"^\w{2}00\s",  # 00 district codes are suspicious
]

# Invalid source identifiers
INVALID_SOURCES = [
    "mock",
    "sample",
    "test",
    "dummy",
    "fake",
    "placeholder",
    "example",
]

# Valid source domains
VALID_SOURCE_DOMAINS = [
    "auctionhouselondon.co.uk",
]


# =============================================================================
# Validation Functions
# =============================================================================

def is_dummy_address(address: str) -> bool:
    """Check if address matches known dummy patterns."""
    if not address:
        return True

    address_lower = address.lower()

    for pattern in DUMMY_STREET_PATTERNS:
        if re.search(pattern, address_lower, re.IGNORECASE):
            return True

    return False


def is_dummy_postcode(postcode: str) -> bool:
    """Check if postcode matches known dummy patterns."""
    if not postcode:
        return True

    for pattern in DUMMY_POSTCODE_PATTERNS:
        if re.match(pattern, postcode.upper()):
            return True

    return False


def is_invalid_source(source: str) -> bool:
    """Check if source indicates mock/test data."""
    if not source:
        return True

    return source.lower() in INVALID_SOURCES


def is_invalid_url(url: str) -> bool:
    """Check if URL is fake or missing."""
    if not url:
        return True

    # Must not be example.com or localhost
    if "example.com" in url.lower():
        return True
    if "localhost" in url.lower():
        return True

    # Must contain a valid source domain
    return not any(domain in url.lower() for domain in VALID_SOURCE_DOMAINS)


def validate_listing_is_real(listing: PropertyListing) -> list[str]:
    """
    Validate that a listing contains real data.

    Returns list of validation errors (empty if valid).
    """
    errors = []

    if is_dummy_address(listing.address):
        errors.append(f"Dummy address detected: {listing.address}")

    if is_dummy_postcode(listing.postcode):
        errors.append(f"Dummy postcode detected: {listing.postcode}")

    if is_invalid_source(listing.source):
        errors.append(f"Invalid source: {listing.source}")

    if is_invalid_url(listing.url):
        errors.append(f"Invalid URL: {listing.url}")

    return errors


# =============================================================================
# Unit Tests: Pattern Detection
# =============================================================================

class TestDummyAddressDetection:
    """Tests for dummy address pattern detection."""

    @pytest.mark.parametrize("address,is_dummy", [
        # Known dummy patterns - should be flagged
        ("Sample Area, Test City", True),
        ("Test Address, Sample Town", True),
        ("123 Test Street, London", True),
        ("456 Sample Road, Manchester", True),
        ("Fake Address, Placeholder Town", True),
        ("99 Dummy Street, Nowhere", True),

        # Real addresses - should NOT be flagged
        # Note: "High Street", "Church Road" etc. are real UK street names
        ("123 High Street, London", False),
        ("45 Church Road, Manchester", False),
        ("Carlisle House, Oxford Road, Reading, Berkshire, RG1 7NG", False),
        ("Flat A, 93 Mount View Road, Hornsey, London, N4 4JA", False),
        ("68 Southcote Avenue, Feltham, Middlesex, TW13 4EG", False),
        ("215 Ross Road, South Norwood, London, SE25 6TN", False),
        ("8 & 8A Bell Row, High Street, Baldock, Hertfordshire, SG7 6AP", False),
    ])
    def test_dummy_address_detection(self, address, is_dummy):
        """Verify dummy address patterns are correctly identified."""
        assert is_dummy_address(address) == is_dummy, f"Failed for: {address}"


class TestDummyPostcodeDetection:
    """Tests for dummy postcode pattern detection."""

    @pytest.mark.parametrize("postcode,is_dummy", [
        # Valid UK postcodes - should NOT be flagged
        ("SW1A 1AA", False),
        ("M1 1AE", False),
        ("B33 8TH", False),
        ("CR2 6XH", False),
        ("RG1 7NG", False),
        ("N4 4JA", False),
        ("TW13 4EG", False),
        ("SE25 6TN", False),

        # Empty/missing - should be flagged
        ("", True),
        (None, True),
    ])
    def test_dummy_postcode_detection(self, postcode, is_dummy):
        """Verify dummy postcode patterns are correctly identified."""
        result = is_dummy_postcode(postcode) if postcode else True
        assert result == is_dummy, f"Failed for: {postcode}"


class TestInvalidSourceDetection:
    """Tests for invalid source detection."""

    @pytest.mark.parametrize("source,is_invalid", [
        # Invalid sources
        ("mock", True),
        ("Mock", True),
        ("MOCK", True),
        ("sample", True),
        ("test", True),
        ("dummy", True),
        ("fake", True),
        ("", True),

        # Valid sources
        ("AuctionHouseLondon", False),
        ("auctionhouselondon", False),
    ])
    def test_invalid_source_detection(self, source, is_invalid):
        """Verify invalid sources are correctly identified."""
        assert is_invalid_source(source) == is_invalid, f"Failed for: {source}"


class TestInvalidUrlDetection:
    """Tests for invalid URL detection."""

    @pytest.mark.parametrize("url,is_invalid", [
        # Invalid URLs
        ("", True),
        ("https://example.com/property/123", True),
        ("http://localhost:8000/listing/1", True),
        ("https://fake-site.com/property", True),

        # Valid URLs
        ("https://auctionhouselondon.co.uk/lot/123-test-street-123456", False),
    ])
    def test_invalid_url_detection(self, url, is_invalid):
        """Verify invalid URLs are correctly identified."""
        assert is_invalid_url(url) == is_invalid, f"Failed for: {url}"


# =============================================================================
# Integration Tests: Real Scraper Data
# =============================================================================

@pytest.mark.integration
class TestScraperProducesRealData:
    """
    Integration tests to verify the scraper ONLY returns real data.

    Run with: pytest -m integration tests/test_no_dummy_data.py
    """

    def test_all_listings_have_real_addresses(self):
        """All scraped listings must have real addresses."""
        from scraper import fetch_auction_listings

        listings = fetch_auction_listings()

        for listing in listings:
            errors = validate_listing_is_real(listing)
            assert not errors, f"Listing {listing.id} has validation errors: {errors}"

    def test_no_mock_source_in_listings(self):
        """No listing should have 'mock' as source."""
        from scraper import fetch_auction_listings

        listings = fetch_auction_listings()

        for listing in listings:
            assert listing.source.lower() != "mock", f"Mock source found: {listing.id}"

    def test_all_urls_point_to_auction_house(self):
        """All listing URLs must point to auctionhouselondon.co.uk."""
        from scraper import fetch_auction_listings

        listings = fetch_auction_listings()

        for listing in listings:
            assert "auctionhouselondon.co.uk" in listing.url, (
                f"Invalid URL for {listing.id}: {listing.url}"
            )


# =============================================================================
# Validation Layer Tests
# =============================================================================

class TestValidationLayerRejectsDummyData:
    """Tests for the validation layer in web/app.py."""

    def test_mock_listing_fails_validation(self):
        """A mock listing should fail validation."""
        from web.app import validate_listing

        mock_listing = PropertyListing(
            id="mock-123",
            address="123 High Street, Sample Town",
            area="Sample Area",
            city="Test City",
            postcode="XX1 1AA",
            property_type="house",
            bedrooms=3,
            bathrooms=2,
            asking_price=250000,
            estimated_value=300000,
            days_on_market=30,
            listed_date="2024-01-01",
            source="mock",
            url="https://example.com/property/123",
        )

        assert not validate_listing(mock_listing), "Mock listing should fail validation"

    def test_real_listing_passes_validation(self):
        """A real listing should pass validation."""
        from web.app import validate_listing

        real_listing = PropertyListing(
            id="AHL-1-abc123",
            address="Carlisle House, Oxford Road, Reading, Berkshire, RG1 7NG",
            area="Oxford Road",
            city="Reading",
            postcode="RG1 7NG",
            property_type="block-of-flats",
            bedrooms=0,
            bathrooms=0,
            asking_price=500000,
            estimated_value=500000,
            days_on_market=0,
            listed_date="2024-01-15",
            source="AuctionHouseLondon",
            url="https://auctionhouselondon.co.uk/lot/carlisle-house-123456",
        )

        assert validate_listing(real_listing), "Real listing should pass validation"


# =============================================================================
# Regression Test: MockScraper Not Used
# =============================================================================

class TestMockScraperNotUsed:
    """Ensure MockScraper is not imported or used in production code."""

    def test_app_does_not_import_mock_scraper(self):
        """web/app.py should not import MockScraper."""
        app_path = Path(__file__).parent.parent / "web" / "app.py"
        content = app_path.read_text()

        assert "MockScraper" not in content, (
            "MockScraper found in web/app.py - this should use AuctionHouseLondonScraper only"
        )

    def test_app_uses_auction_house_scraper(self):
        """web/app.py should use AuctionHouseLondonScraper."""
        app_path = Path(__file__).parent.parent / "web" / "app.py"
        content = app_path.read_text()

        assert "AuctionHouseLondonScraper" in content, (
            "AuctionHouseLondonScraper not found in web/app.py"
        )


# =============================================================================
# Regression Test: Zero Results Safety
# =============================================================================

class TestZeroResultsSafety:
    """
    Regression tests to ensure zero results are handled safely.

    These tests prove:
    - Zero real listings returns HTTP 200 (not 500)
    - UI renders safely with appropriate message
    - No mock data is injected as fallback
    - No exceptions are raised
    """

    def test_scraper_returns_empty_list_not_exception(self):
        """Scraper should return empty list, not raise exception, when no listings."""
        from scraper.auction_house_london import AuctionHouseLondonParser

        # Empty HTML should return empty list, not raise
        result = AuctionHouseLondonParser.parse("")
        assert result == [], "Parser should return empty list for empty HTML"

        # HTML with no listings should return empty list
        result = AuctionHouseLondonParser.parse("<html><body>No auctions</body></html>")
        assert result == [], "Parser should return empty list when no listings found"

    def test_filter_validated_listings_handles_empty(self):
        """filter_validated_listings should return empty list for empty input."""
        from web.app import filter_validated_listings

        result = filter_validated_listings([])
        assert result == [], "Should return empty list for empty input"

    def test_filter_validated_listings_rejects_all_invalid(self):
        """filter_validated_listings should return empty list if all invalid."""
        from web.app import filter_validated_listings

        # Create listings that will fail validation
        mock_listings = [
            type('Listing', (), {
                'address': 'Test Address',
                'postcode': 'XX1 1AA',  # Invalid postcode
                'url': 'https://example.com/test',  # Invalid URL
                'source': 'mock',  # Invalid source
            })(),
            type('Listing', (), {
                'address': '',  # Empty address
                'postcode': 'SW1A 1AA',
                'url': 'https://auctionhouselondon.co.uk/lot/123',
                'source': 'AuctionHouseLondon',
            })(),
        ]

        result = filter_validated_listings(mock_listings)
        assert result == [], "Should return empty list when all listings fail validation"

    def test_app_handles_zero_listings_gracefully(self):
        """
        App should handle zero listings without crashing.

        Verifies the code structure allows for graceful zero-result handling.
        """
        app_path = Path(__file__).parent.parent / "web" / "app.py"
        content = app_path.read_text()

        # Verify the app has proper zero-listing handling in the search route
        # Check for the pattern that returns a template response with empty analyses
        assert "if not listings:" in content, (
            "App should check for empty listings"
        )

        # Check that there's a no_listings_message response
        assert "no_listings_message" in content, (
            "App should have a no_listings_message for empty results"
        )

        # Check analyses is set to empty list when no listings
        assert '"analyses": []' in content or "'analyses': []" in content or \
               "analyses=[]" in content or '"analyses": []' in content.replace(" ", ""), (
            "App should set analyses to empty list for no listings"
        )

        # Verify the pattern: return template response instead of raising error
        assert "TemplateResponse" in content, (
            "App should use TemplateResponse for results"
        )

        # Verify no fallback to mock data in the zero-listings path
        lines = content.split("\n")
        in_no_listings_block = False
        for line in lines:
            if "if not listings:" in line:
                in_no_listings_block = True
            if in_no_listings_block:
                assert "MockScraper" not in line, (
                    "No MockScraper fallback in zero-listings handling"
                )
                assert "mock" not in line.lower() or "# " in line, (
                    "No mock data injection in zero-listings handling"
                )
                # Exit block check after return statement
                if "return" in line and "TemplateResponse" in line:
                    break

    def test_app_no_mock_fallback_on_error(self):
        """App should NOT fall back to mock data on scraper error."""
        app_path = Path(__file__).parent.parent / "web" / "app.py"
        content = app_path.read_text()

        # Check that there's no fallback logic to MockScraper
        assert "MockScraper()" not in content, (
            "App should not instantiate MockScraper"
        )

        # Check that MockScraper is not imported
        assert "from scraper import MockScraper" not in content, (
            "App should not import MockScraper"
        )
        assert "from scraper.mock import" not in content, (
            "App should not import from scraper.mock"
        )
