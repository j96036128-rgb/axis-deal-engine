"""
Land Registry Price Paid Data Service

Provides comparable sales data from UK Land Registry for valuation.
This is a stub implementation - in production, this would connect to
the Land Registry API or a local database of Price Paid Data.

Data Source: UK Land Registry Price Paid Data (completed sales only)
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional
import hashlib

from .comp_engine import (
    ComparableSale,
    SubjectProperty,
    PropertyType,
    Tenure,
)


@dataclass
class LandRegistryQuery:
    """Query parameters for Land Registry search."""
    postcode: str
    property_type: PropertyType
    tenure: Tenure
    latitude: float
    longitude: float
    max_radius_miles: float = 1.5
    max_age_months: int = 24


class LandRegistryService:
    """
    Service for fetching comparable sales from Land Registry.

    In production, this would:
    1. Query the Land Registry Price Paid Data API
    2. Or query a local database of Price Paid Data
    3. Or use a third-party property data provider

    For now, this is a stub that returns empty results,
    ensuring the system handles zero-comp scenarios gracefully.
    """

    def __init__(self):
        """Initialize the Land Registry service."""
        self._cache = {}

    def fetch_comparables(
        self,
        query: LandRegistryQuery,
        reference_date: date = None,
    ) -> List[ComparableSale]:
        """
        Fetch comparable sales from Land Registry.

        Args:
            query: Search parameters
            reference_date: Reference date for age calculation (default: today)

        Returns:
            List of comparable sales (empty if none found)

        Note:
            This is a stub implementation. In production, this would
            fetch real data from Land Registry Price Paid Data.
        """
        # Stub implementation returns empty list
        # This ensures the system handles zero-comp scenarios gracefully
        # The Comp Engine will return appropriate Low confidence results
        return []

    def fetch_comparables_for_subject(
        self,
        subject: SubjectProperty,
        reference_date: date = None,
    ) -> List[ComparableSale]:
        """
        Convenience method to fetch comparables for a SubjectProperty.

        Args:
            subject: The subject property being valued
            reference_date: Reference date for age calculation

        Returns:
            List of comparable sales
        """
        query = LandRegistryQuery(
            postcode=subject.postcode,
            property_type=subject.property_type,
            tenure=subject.tenure,
            latitude=subject.latitude,
            longitude=subject.longitude,
        )
        return self.fetch_comparables(query, reference_date)


# Singleton instance for the application
_land_registry_service: Optional[LandRegistryService] = None


def get_land_registry_service() -> LandRegistryService:
    """Get the Land Registry service singleton."""
    global _land_registry_service
    if _land_registry_service is None:
        _land_registry_service = LandRegistryService()
    return _land_registry_service
