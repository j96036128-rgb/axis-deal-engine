"""
Source Adapter Interface - Abstract Base for Data Source Integrations

All data sources must implement this interface to integrate with the
Deal Engine. Adapters handle fetching, normalisation, and rejection tracking.

Document Reference: DATA_SOURCE_EXPANSION_FRAMEWORK.md Section 4
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any, AsyncIterator, Final, Optional

from core.comp_engine.models import PropertyType, Tenure
from core.ingestion.registry import SourceRegistration, get_source
from core.ingestion.schema import (
    ListingStatus,
    RejectionRecord,
    SourceCategory,
    SourceMetadata,
    ValidatedAsset,
    normalise_uk_postcode,
    validate_uk_postcode,
)


logger = logging.getLogger(__name__)


# =============================================================================
# Property Type Mapping
# =============================================================================

# Standard property type mappings shared across adapters
# Each adapter may extend this with source-specific values
STANDARD_PROPERTY_TYPE_MAP: Final[dict[str, PropertyType]] = {
    # Flat variants
    "flat": PropertyType.FLAT,
    "apartment": PropertyType.FLAT,
    "studio": PropertyType.FLAT,
    "studio flat": PropertyType.FLAT,
    "studio apartment": PropertyType.FLAT,
    "penthouse": PropertyType.FLAT,
    "ground floor flat": PropertyType.FLAT,
    "upper floor flat": PropertyType.FLAT,
    # Maisonette
    "maisonette": PropertyType.MAISONETTE,
    # Terraced variants
    "terraced": PropertyType.TERRACED,
    "terrace": PropertyType.TERRACED,
    "terraced house": PropertyType.TERRACED,
    "end terrace": PropertyType.TERRACED,
    "end of terrace": PropertyType.TERRACED,
    "mid terrace": PropertyType.TERRACED,
    "mid-terrace": PropertyType.TERRACED,
    "town house": PropertyType.TERRACED,
    "townhouse": PropertyType.TERRACED,
    # Semi-detached variants
    "semi-detached": PropertyType.SEMI_DETACHED,
    "semi detached": PropertyType.SEMI_DETACHED,
    "semi": PropertyType.SEMI_DETACHED,
    "semi-detached house": PropertyType.SEMI_DETACHED,
    # Detached variants
    "detached": PropertyType.DETACHED,
    "detached house": PropertyType.DETACHED,
    "bungalow": PropertyType.DETACHED,
    "detached bungalow": PropertyType.DETACHED,
    "cottage": PropertyType.DETACHED,
    "farmhouse": PropertyType.DETACHED,
    "villa": PropertyType.DETACHED,
}

# Standard tenure mappings
STANDARD_TENURE_MAP: Final[dict[str, Tenure]] = {
    "freehold": Tenure.FREEHOLD,
    "share of freehold": Tenure.FREEHOLD,
    "share freehold": Tenure.FREEHOLD,
    "leasehold": Tenure.LEASEHOLD,
    "long leasehold": Tenure.LEASEHOLD,
}


# =============================================================================
# Validation Thresholds
# =============================================================================

MIN_ASKING_PRICE: Final[int] = 10_000
MAX_ASKING_PRICE: Final[int] = 50_000_000
MAX_LISTING_AGE_DAYS: Final[int] = 365


# =============================================================================
# Source Adapter Interface
# =============================================================================


class SourceAdapter(ABC):
    """
    Abstract interface for all data source integrations.

    Adapters are responsible for:
    1. Fetching raw data from the source
    2. Normalising to ValidatedAsset schema
    3. Rejecting records that cannot be normalised
    4. Tracking rejections for quality monitoring

    Subclasses must implement:
    - source_registration: property returning SourceRegistration
    - fetch_listings: async generator yielding ValidatedAsset
    - fetch_single: fetch single listing by source ID

    Subclasses may override:
    - normalise_property_type: custom type mapping
    - normalise_tenure: custom tenure mapping
    - get_property_type_map: extend standard mappings
    - get_tenure_map: extend standard mappings
    """

    def __init__(self) -> None:
        """Initialise adapter with rejection tracking."""
        self._rejections: list[RejectionRecord] = []

    @property
    @abstractmethod
    def source_registration(self) -> SourceRegistration:
        """Return the source's registration record."""
        ...

    @abstractmethod
    async def fetch_listings(
        self,
        since: Optional[datetime] = None,
    ) -> AsyncIterator[ValidatedAsset]:
        """
        Fetch and normalise listings from the source.

        Args:
            since: Only fetch listings modified after this time (if supported)

        Yields:
            ValidatedAsset records that pass normalisation

        Note:
            Records that cannot be normalised are logged and skipped.
            This method NEVER yields partially-populated records.
        """
        ...

    @abstractmethod
    async def fetch_single(
        self,
        source_listing_id: str,
    ) -> Optional[ValidatedAsset]:
        """
        Fetch a single listing by its source-specific ID.

        Returns:
            ValidatedAsset if found and normalisable, None otherwise
        """
        ...

    # =========================================================================
    # Property Type Normalisation
    # =========================================================================

    def get_property_type_map(self) -> dict[str, PropertyType]:
        """
        Get property type mapping for this source.

        Override to add source-specific mappings.
        Default returns standard mappings.
        """
        return STANDARD_PROPERTY_TYPE_MAP.copy()

    def normalise_property_type(self, raw_type: str) -> Optional[PropertyType]:
        """
        Map source-specific property type to normalised enum.

        Args:
            raw_type: Raw property type string from source

        Returns:
            PropertyType if mappable, None if unmappable (record will be rejected)
        """
        if not raw_type:
            return None

        normalised = raw_type.lower().strip()
        type_map = self.get_property_type_map()
        return type_map.get(normalised)

    # =========================================================================
    # Tenure Normalisation
    # =========================================================================

    def get_tenure_map(self) -> dict[str, Tenure]:
        """
        Get tenure mapping for this source.

        Override to add source-specific mappings.
        Default returns standard mappings.
        """
        return STANDARD_TENURE_MAP.copy()

    def normalise_tenure(self, raw_tenure: str) -> Optional[Tenure]:
        """
        Map source-specific tenure to normalised enum.

        Args:
            raw_tenure: Raw tenure string from source

        Returns:
            Tenure if mappable, None if unmappable (record will be rejected)
        """
        if not raw_tenure:
            return None

        normalised = raw_tenure.lower().strip()
        tenure_map = self.get_tenure_map()
        return tenure_map.get(normalised)

    # =========================================================================
    # Rejection Handling
    # =========================================================================

    @property
    def rejections(self) -> list[RejectionRecord]:
        """Get all rejection records from this adapter session."""
        return self._rejections.copy()

    def clear_rejections(self) -> None:
        """Clear rejection records (e.g., after processing)."""
        self._rejections.clear()

    def _reject(
        self,
        source_listing_id: str,
        rejection_code: str,
        raw_data: Optional[dict] = None,
    ) -> None:
        """
        Record a rejection.

        Args:
            source_listing_id: ID from source
            rejection_code: Code from REJECTION_CODES
            raw_data: Optional raw data for debugging hash
        """
        record = RejectionRecord.create(
            source_id=self.source_registration.source_id,
            source_listing_id=source_listing_id,
            rejection_code=rejection_code,
            raw_data=raw_data,
        )
        self._rejections.append(record)
        logger.warning(
            "Rejected listing %s from %s: %s",
            source_listing_id,
            self.source_registration.source_id,
            rejection_code,
        )

    # =========================================================================
    # Validation Helpers
    # =========================================================================

    def validate_and_normalise(
        self,
        raw_data: dict[str, Any],
        source_listing_id: str,
    ) -> Optional[ValidatedAsset]:
        """
        Validate raw data and create ValidatedAsset if valid.

        This is a convenience method that applies all validation rules
        and creates a ValidatedAsset if successful.

        Args:
            raw_data: Dictionary of raw listing data
            source_listing_id: ID from source

        Returns:
            ValidatedAsset if valid, None if rejected (rejection recorded)
        """
        reg = self.source_registration

        # Required field: address
        address = raw_data.get("address", "").strip()
        if not address:
            self._reject(source_listing_id, "MISSING_ADDRESS", raw_data)
            return None

        # Required field: postcode
        postcode = raw_data.get("postcode", "").strip()
        if not postcode:
            self._reject(source_listing_id, "MISSING_POSTCODE", raw_data)
            return None
        if not validate_uk_postcode(postcode):
            self._reject(source_listing_id, "INVALID_POSTCODE", raw_data)
            return None
        postcode = normalise_uk_postcode(postcode)

        # Required field: city
        city = raw_data.get("city", "").strip()
        if not city:
            # Try to infer from postcode area if not provided
            city = raw_data.get("town", "").strip() or raw_data.get("area", "").strip()
        if not city:
            self._reject(source_listing_id, "MISSING_ADDRESS", raw_data)
            return None

        # Required field: property_type
        raw_property_type = raw_data.get("property_type", "").strip()
        if not raw_property_type:
            self._reject(source_listing_id, "MISSING_PROPERTY_TYPE", raw_data)
            return None
        property_type = self.normalise_property_type(raw_property_type)
        if property_type is None:
            self._reject(source_listing_id, "UNMAPPED_PROPERTY_TYPE", raw_data)
            return None

        # Required field: tenure
        raw_tenure = raw_data.get("tenure", "").strip()
        if not raw_tenure:
            self._reject(source_listing_id, "MISSING_TENURE", raw_data)
            return None
        tenure = self.normalise_tenure(raw_tenure)
        if tenure is None:
            self._reject(source_listing_id, "UNMAPPED_TENURE", raw_data)
            return None

        # Required field: asking_price
        asking_price = raw_data.get("asking_price")
        if asking_price is None:
            self._reject(source_listing_id, "MISSING_PRICE", raw_data)
            return None
        try:
            asking_price = int(asking_price)
        except (ValueError, TypeError):
            self._reject(source_listing_id, "INVALID_PRICE", raw_data)
            return None
        if asking_price <= 0:
            self._reject(source_listing_id, "INVALID_PRICE", raw_data)
            return None
        if asking_price < MIN_ASKING_PRICE:
            self._reject(source_listing_id, "PRICE_BELOW_THRESHOLD", raw_data)
            return None
        if asking_price > MAX_ASKING_PRICE:
            self._reject(source_listing_id, "PRICE_ABOVE_THRESHOLD", raw_data)
            return None

        # Required field: listing_date
        listing_date = raw_data.get("listing_date")
        if listing_date is None:
            self._reject(source_listing_id, "MISSING_LISTING_DATE", raw_data)
            return None
        if isinstance(listing_date, str):
            try:
                listing_date = date.fromisoformat(listing_date)
            except ValueError:
                self._reject(source_listing_id, "MISSING_LISTING_DATE", raw_data)
                return None
        if listing_date > date.today():
            self._reject(source_listing_id, "FUTURE_LISTING_DATE", raw_data)
            return None
        if (date.today() - listing_date).days > MAX_LISTING_AGE_DAYS:
            self._reject(source_listing_id, "STALE_LISTING", raw_data)
            return None

        # Required field: listing_url
        listing_url = raw_data.get("listing_url", "").strip()
        if not listing_url:
            self._reject(source_listing_id, "MISSING_URL", raw_data)
            return None

        # Optional fields
        bedrooms = raw_data.get("bedrooms")
        if bedrooms is not None:
            try:
                bedrooms = int(bedrooms)
                if bedrooms < 0:
                    bedrooms = None
            except (ValueError, TypeError):
                bedrooms = None

        bathrooms = raw_data.get("bathrooms")
        if bathrooms is not None:
            try:
                bathrooms = int(bathrooms)
                if bathrooms < 0:
                    bathrooms = None
            except (ValueError, TypeError):
                bathrooms = None

        latitude = raw_data.get("latitude")
        longitude = raw_data.get("longitude")
        if latitude is not None and longitude is not None:
            try:
                latitude = float(latitude)
                longitude = float(longitude)
                if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                    latitude = None
                    longitude = None
            except (ValueError, TypeError):
                latitude = None
                longitude = None

        # Build source metadata
        source_metadata = SourceMetadata(
            source_id=reg.source_id,
            source_name=reg.source_name,
            source_listing_id=source_listing_id,
            source_url=listing_url,
            source_category=reg.source_category,
            auction_date=raw_data.get("auction_date"),
            lot_number=raw_data.get("lot_number"),
            receiver_name=raw_data.get("receiver_name"),
            insolvency_type=raw_data.get("insolvency_type"),
            source_scraped_at=datetime.utcnow(),
            source_last_modified=raw_data.get("last_modified"),
        )

        # Generate asset ID
        asset_id = ValidatedAsset.generate_asset_id(
            source_id=reg.source_id,
            source_listing_id=source_listing_id,
            listing_date=listing_date,
        )

        # Create validated asset
        try:
            return ValidatedAsset(
                asset_id=asset_id,
                address=address,
                postcode=postcode,
                city=city,
                area=raw_data.get("area"),
                property_type=property_type,
                tenure=tenure,
                asking_price=asking_price,
                listing_status=ListingStatus.ACTIVE,
                listing_date=listing_date,
                source=source_metadata,
                validated_at=datetime.utcnow(),
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                latitude=latitude,
                longitude=longitude,
                price_qualifier=raw_data.get("price_qualifier"),
                square_feet=raw_data.get("square_feet"),
                plot_acres=raw_data.get("plot_acres"),
            )
        except ValueError as e:
            logger.error(
                "Validation error creating ValidatedAsset for %s: %s",
                source_listing_id,
                e,
            )
            return None

    # =========================================================================
    # Quality Metrics
    # =========================================================================

    def get_quality_metrics(self) -> dict[str, Any]:
        """
        Get quality metrics for this adapter session.

        Returns dict with:
        - total_processed: Total listings attempted
        - total_normalised: Successfully normalised
        - total_rejected: Failed normalisation
        - normalisation_rate: Success rate
        - rejections_by_code: Breakdown by rejection code
        """
        total = len(self._rejections)  # This is just rejections
        # Note: To get true metrics, caller should track normalised count

        rejections_by_code: dict[str, int] = {}
        for r in self._rejections:
            rejections_by_code[r.rejection_code] = (
                rejections_by_code.get(r.rejection_code, 0) + 1
            )

        return {
            "source_id": self.source_registration.source_id,
            "total_rejected": total,
            "rejections_by_code": rejections_by_code,
        }
