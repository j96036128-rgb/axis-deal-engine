"""
ValidatedAsset Schema - Canonical Normalised Property Record

This is the ONLY schema that enters the Deal Engine pipeline.
All source-specific data is either normalised into these fields
or retained as metadata (which never affects scoring).

Document Reference: DATA_SOURCE_EXPANSION_FRAMEWORK.md Section 3
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Final, Optional

from core.comp_engine.models import PropertyType, Tenure


class SourceCategory(Enum):
    """Classification of data source types."""

    AUCTION = "auction"
    RECEIVERSHIP = "receivership"
    DISTRESSED = "distressed"
    OTHER = "other"


class ListingStatus(Enum):
    """Current listing status."""

    ACTIVE = "active"
    UNDER_OFFER = "under_offer"
    SOLD = "sold"
    WITHDRAWN = "withdrawn"


# UK postcode validation regex
# Matches formats: AA9A 9AA, A9A 9AA, A9 9AA, A99 9AA, AA9 9AA, AA99 9AA
UK_POSTCODE_REGEX: Final = re.compile(
    r"^([A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2})$", re.IGNORECASE
)


def validate_uk_postcode(postcode: str) -> bool:
    """Validate UK postcode format."""
    if not postcode:
        return False
    # Remove extra spaces and uppercase
    normalised = " ".join(postcode.upper().split())
    return bool(UK_POSTCODE_REGEX.match(normalised))


def normalise_uk_postcode(postcode: str) -> str:
    """
    Normalise UK postcode to standard format.

    Ensures single space between outward and inward codes.
    """
    if not postcode:
        return ""
    # Remove all spaces, uppercase
    clean = postcode.upper().replace(" ", "")
    # Insert space before last 3 characters (inward code)
    if len(clean) >= 4:
        return f"{clean[:-3]} {clean[-3:]}"
    return clean


@dataclass(frozen=True)
class SourceMetadata:
    """
    Source-specific information that does NOT affect scoring.

    Retained for audit trail and provenance only. The Deal Engine
    MUST NOT read these fields in any scoring or recommendation logic.
    """

    # Required source identity
    source_id: str
    source_name: str
    source_listing_id: str
    source_url: str
    source_category: SourceCategory

    # Auction-specific (metadata only - does not affect scoring)
    auction_date: Optional[date] = None
    lot_number: Optional[str] = None

    # Receivership-specific (metadata only - does not affect scoring)
    receiver_name: Optional[str] = None
    insolvency_type: Optional[str] = None

    # Timestamps
    source_scraped_at: Optional[datetime] = None
    source_last_modified: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate required fields."""
        if not self.source_id:
            raise ValueError("source_id is required")
        if not self.source_name:
            raise ValueError("source_name is required")
        if not self.source_listing_id:
            raise ValueError("source_listing_id is required")
        if not self.source_url:
            raise ValueError("source_url is required")


@dataclass(frozen=True)
class ValidatedAsset:
    """
    Canonical normalised property record.

    This is the ONLY schema that enters the Deal Engine pipeline.
    All source-specific data is either normalised into these fields
    or retained as metadata (which never affects scoring).

    Invariants:
        - asset_id is globally unique and immutable
        - property_type is one of exactly five normalised values
        - tenure is one of exactly two normalised values
        - asking_price is always a positive integer in GBP
        - source metadata NEVER influences scoring
        - ValidatedAsset is immutable (frozen dataclass)

    Prohibited fields (never exist on this schema):
        - estimated_value (calculated by Deal Engine)
        - bmv_percent (calculated by Deal Engine)
        - score (calculated by Deal Engine)
        - recommendation (calculated by Deal Engine)
    """

    # === IDENTITY (Required) ===
    asset_id: str
    address: str
    postcode: str
    city: str
    area: Optional[str]

    # === PROPERTY ATTRIBUTES (Required) ===
    property_type: PropertyType
    tenure: Tenure

    # === PRICING (Required) ===
    asking_price: int

    # === LISTING STATUS (Required) ===
    listing_status: ListingStatus
    listing_date: date

    # === SOURCE METADATA (Required - does NOT affect scoring) ===
    source: SourceMetadata

    # === AUDIT (Required) ===
    validated_at: datetime

    # === PROPERTY ATTRIBUTES (Optional) ===
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    square_feet: Optional[int] = None
    plot_acres: Optional[float] = None

    # === PRICING METADATA (Optional) ===
    price_qualifier: Optional[str] = None

    # === LOCATION (Optional - for comp radius calculation) ===
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # === SCHEMA VERSION ===
    schema_version: str = field(default="1.0", repr=False)

    def __post_init__(self) -> None:
        """Validate all constraints at construction time."""
        # Required string fields
        if not self.asset_id:
            raise ValueError("asset_id is required")
        if not self.address:
            raise ValueError("address is required")
        if not self.postcode:
            raise ValueError("postcode is required")
        if not self.city:
            raise ValueError("city is required")

        # Postcode validation
        if not validate_uk_postcode(self.postcode):
            raise ValueError(f"Invalid UK postcode format: {self.postcode}")

        # Price validation
        if self.asking_price <= 0:
            raise ValueError("asking_price must be positive")

        # Optional field constraints
        if self.bedrooms is not None and self.bedrooms < 0:
            raise ValueError("bedrooms cannot be negative")
        if self.bathrooms is not None and self.bathrooms < 0:
            raise ValueError("bathrooms cannot be negative")
        if self.square_feet is not None and self.square_feet <= 0:
            raise ValueError("square_feet must be positive if provided")
        if self.plot_acres is not None and self.plot_acres <= 0:
            raise ValueError("plot_acres must be positive if provided")

        # Coordinate validation
        if self.latitude is not None:
            if not -90 <= self.latitude <= 90:
                raise ValueError("latitude must be between -90 and 90")
        if self.longitude is not None:
            if not -180 <= self.longitude <= 180:
                raise ValueError("longitude must be between -180 and 180")

    @property
    def days_on_market(self) -> int:
        """Calculate days since listing date."""
        delta = date.today() - self.listing_date
        return max(0, delta.days)

    @property
    def postcode_district(self) -> str:
        """Extract postcode district (e.g., 'SW1A' from 'SW1A 1AA')."""
        parts = self.postcode.upper().split()
        return parts[0] if parts else ""

    @property
    def postcode_sector(self) -> str:
        """Extract postcode sector (e.g., 'SW1A 1' from 'SW1A 1AA')."""
        parts = self.postcode.upper().split()
        if len(parts) == 2 and len(parts[1]) >= 1:
            return f"{parts[0]} {parts[1][0]}"
        return self.postcode_district

    @classmethod
    def generate_asset_id(
        cls,
        source_id: str,
        source_listing_id: str,
        listing_date: date,
    ) -> str:
        """
        Generate a deterministic, globally unique asset ID.

        Format: va-{date}-{source_hash}-{listing_hash}
        """
        date_str = listing_date.strftime("%Y%m%d")
        source_hash = hashlib.sha256(source_id.encode()).hexdigest()[:6]
        listing_hash = hashlib.sha256(source_listing_id.encode()).hexdigest()[:8]
        return f"va-{date_str}-{source_hash}-{listing_hash}"


# =============================================================================
# Rejection Handling
# =============================================================================


REJECTION_CODES: Final[dict[str, str]] = {
    "MISSING_ADDRESS": "Required field 'address' not provided",
    "MISSING_POSTCODE": "Required field 'postcode' not provided",
    "INVALID_POSTCODE": "Postcode format validation failed",
    "MISSING_PROPERTY_TYPE": "Required field 'property_type' not provided",
    "UNMAPPED_PROPERTY_TYPE": "Property type could not be normalised to valid enum",
    "MISSING_TENURE": "Required field 'tenure' not provided",
    "UNMAPPED_TENURE": "Tenure could not be normalised to valid enum",
    "MISSING_PRICE": "Required field 'asking_price' not provided",
    "INVALID_PRICE": "Asking price is not a positive integer",
    "PRICE_BELOW_THRESHOLD": "Asking price below minimum threshold (£10,000)",
    "PRICE_ABOVE_THRESHOLD": "Asking price above maximum threshold (£50,000,000)",
    "MISSING_LISTING_DATE": "Required field 'listing_date' not provided",
    "FUTURE_LISTING_DATE": "Listing date is in the future",
    "STALE_LISTING": "Listing date more than 365 days old",
    "MISSING_URL": "Required field 'listing_url' not provided",
    "INVALID_URL": "Listing URL is not a valid URL format",
}


@dataclass(frozen=True)
class RejectionRecord:
    """
    Record of a listing that failed normalisation.

    Used for audit trail and data quality monitoring.
    """

    source_id: str
    source_listing_id: str
    rejection_code: str
    rejection_reason: str
    raw_data_hash: str
    rejected_at: datetime

    @classmethod
    def create(
        cls,
        source_id: str,
        source_listing_id: str,
        rejection_code: str,
        raw_data: Optional[dict] = None,
    ) -> "RejectionRecord":
        """Create a rejection record with automatic hash and timestamp."""
        reason = REJECTION_CODES.get(rejection_code, f"Unknown code: {rejection_code}")

        # Hash raw data for debugging without storing PII
        if raw_data:
            data_str = str(sorted(raw_data.items()))
            raw_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]
        else:
            raw_hash = "no_data"

        return cls(
            source_id=source_id,
            source_listing_id=source_listing_id,
            rejection_code=rejection_code,
            rejection_reason=reason,
            raw_data_hash=raw_hash,
            rejected_at=datetime.utcnow(),
        )
