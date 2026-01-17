"""
Source Registry - Data Source Registration and Management

All data sources must be registered before integration with the Deal Engine.
This registry tracks source metadata, capabilities, and operational status.

Document Reference: DATA_SOURCE_EXPANSION_FRAMEWORK.md Section 2
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final, Optional

from core.ingestion.schema import SourceCategory


@dataclass(frozen=True)
class SourceRegistration:
    """
    Immutable source registration record.

    Every data source must be formally registered before integration.
    This record defines the source's identity, capabilities, and constraints.
    """

    # === Identity ===
    source_id: str
    source_name: str
    source_category: SourceCategory

    # === Classification ===
    is_auction: bool
    is_distressed: bool
    is_off_market: bool

    # === Data Quality Declaration ===
    # Sources must accurately declare which fields they provide
    provides_tenure: bool
    provides_property_type: bool
    provides_bedrooms: bool
    provides_bathrooms: bool
    provides_coordinates: bool
    provides_square_feet: bool

    # === Operational ===
    rate_limit_seconds: float
    requires_authentication: bool
    active: bool

    # === Audit ===
    registered_date: date
    last_verified_date: date

    def __post_init__(self) -> None:
        """Validate registration constraints."""
        if not self.source_id:
            raise ValueError("source_id is required")
        if not self.source_name:
            raise ValueError("source_name is required")

        # Validate source_id format (lowercase alphanumeric with underscores)
        import re

        if not re.match(r"^[a-z0-9_]+$", self.source_id):
            raise ValueError(
                f"source_id must be lowercase alphanumeric with underscores: {self.source_id}"
            )

        if self.rate_limit_seconds < 0:
            raise ValueError("rate_limit_seconds cannot be negative")


# =============================================================================
# Source Registry
# =============================================================================

# Global registry of all registered sources
_SOURCE_REGISTRY: dict[str, SourceRegistration] = {}


def register_source(registration: SourceRegistration) -> None:
    """
    Register a new data source.

    Args:
        registration: The source registration record

    Raises:
        ValueError: If source_id is already registered
    """
    if registration.source_id in _SOURCE_REGISTRY:
        raise ValueError(f"Source already registered: {registration.source_id}")
    _SOURCE_REGISTRY[registration.source_id] = registration


def get_source(source_id: str) -> Optional[SourceRegistration]:
    """
    Get a registered source by ID.

    Args:
        source_id: The source identifier

    Returns:
        The source registration if found, None otherwise
    """
    return _SOURCE_REGISTRY.get(source_id)


def get_active_sources() -> list[SourceRegistration]:
    """Get all active registered sources."""
    return [s for s in _SOURCE_REGISTRY.values() if s.active]


def get_sources_by_category(category: SourceCategory) -> list[SourceRegistration]:
    """Get all registered sources in a category."""
    return [s for s in _SOURCE_REGISTRY.values() if s.source_category == category]


# Expose registry for inspection (read-only view)
SOURCE_REGISTRY: Final = _SOURCE_REGISTRY


# =============================================================================
# Default Registrations
# =============================================================================

# Register Auction House London (existing integration)
register_source(
    SourceRegistration(
        source_id="auction_house_london",
        source_name="Auction House London",
        source_category=SourceCategory.AUCTION,
        is_auction=True,
        is_distressed=False,
        is_off_market=False,
        provides_tenure=True,
        provides_property_type=True,
        provides_bedrooms=False,
        provides_bathrooms=False,
        provides_coordinates=False,
        provides_square_feet=False,
        rate_limit_seconds=1.5,
        requires_authentication=False,
        active=True,
        registered_date=date(2026, 1, 17),
        last_verified_date=date(2026, 1, 17),
    )
)

# Register Mock Scraper (for testing only)
register_source(
    SourceRegistration(
        source_id="mock_scraper",
        source_name="Mock Scraper (Testing)",
        source_category=SourceCategory.OTHER,
        is_auction=False,
        is_distressed=False,
        is_off_market=False,
        provides_tenure=True,
        provides_property_type=True,
        provides_bedrooms=True,
        provides_bathrooms=True,
        provides_coordinates=False,
        provides_square_feet=False,
        rate_limit_seconds=0,
        requires_authentication=False,
        active=True,
        registered_date=date(2026, 1, 17),
        last_verified_date=date(2026, 1, 17),
    )
)

# =============================================================================
# Future Source Templates (Inactive - Pending Integration)
# =============================================================================

register_source(
    SourceRegistration(
        source_id="allsop_auctions",
        source_name="Allsop Auctions",
        source_category=SourceCategory.AUCTION,
        is_auction=True,
        is_distressed=False,
        is_off_market=False,
        provides_tenure=True,
        provides_property_type=True,
        provides_bedrooms=True,
        provides_bathrooms=False,
        provides_coordinates=False,
        provides_square_feet=True,
        rate_limit_seconds=2.0,
        requires_authentication=False,
        active=False,  # Pending integration
        registered_date=date(2026, 1, 17),
        last_verified_date=date(2026, 1, 17),
    )
)

register_source(
    SourceRegistration(
        source_id="savills_auctions",
        source_name="Savills Auctions",
        source_category=SourceCategory.AUCTION,
        is_auction=True,
        is_distressed=False,
        is_off_market=False,
        provides_tenure=True,
        provides_property_type=True,
        provides_bedrooms=True,
        provides_bathrooms=True,
        provides_coordinates=False,
        provides_square_feet=True,
        rate_limit_seconds=2.0,
        requires_authentication=False,
        active=False,  # Pending integration
        registered_date=date(2026, 1, 17),
        last_verified_date=date(2026, 1, 17),
    )
)

register_source(
    SourceRegistration(
        source_id="sdl_auctions",
        source_name="SDL Property Auctions",
        source_category=SourceCategory.AUCTION,
        is_auction=True,
        is_distressed=False,
        is_off_market=False,
        provides_tenure=True,
        provides_property_type=True,
        provides_bedrooms=True,
        provides_bathrooms=False,
        provides_coordinates=False,
        provides_square_feet=False,
        rate_limit_seconds=1.5,
        requires_authentication=False,
        active=False,  # Pending integration
        registered_date=date(2026, 1, 17),
        last_verified_date=date(2026, 1, 17),
    )
)

register_source(
    SourceRegistration(
        source_id="lpa_receivers_network",
        source_name="LPA Receivers Network",
        source_category=SourceCategory.RECEIVERSHIP,
        is_auction=False,
        is_distressed=True,
        is_off_market=True,
        provides_tenure=True,
        provides_property_type=True,
        provides_bedrooms=True,
        provides_bathrooms=True,
        provides_coordinates=True,
        provides_square_feet=True,
        rate_limit_seconds=0,  # Push-based feed
        requires_authentication=True,
        active=False,  # Pending integration
        registered_date=date(2026, 1, 17),
        last_verified_date=date(2026, 1, 17),
    )
)

register_source(
    SourceRegistration(
        source_id="insolvency_service_feed",
        source_name="Insolvency Service Direct Feed",
        source_category=SourceCategory.RECEIVERSHIP,
        is_auction=False,
        is_distressed=True,
        is_off_market=True,
        provides_tenure=True,
        provides_property_type=True,
        provides_bedrooms=False,
        provides_bathrooms=False,
        provides_coordinates=False,
        provides_square_feet=False,
        rate_limit_seconds=0,
        requires_authentication=True,
        active=False,  # Pending integration
        registered_date=date(2026, 1, 17),
        last_verified_date=date(2026, 1, 17),
    )
)
