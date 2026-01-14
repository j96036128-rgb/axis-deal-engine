"""
Base scraper interface.
"""

from abc import ABC, abstractmethod
from typing import List

from core.models import PropertyListing, SearchCriteria


class BaseScraper(ABC):
    """Abstract base class for property scrapers."""

    @abstractmethod
    async def search(self, criteria: SearchCriteria) -> List[PropertyListing]:
        """
        Search for properties matching the given criteria.

        Args:
            criteria: Search parameters including location, beds, baths, etc.

        Returns:
            List of PropertyListing objects matching the criteria.
        """
        pass

    @abstractmethod
    async def get_listing_details(self, listing_id: str) -> PropertyListing | None:
        """
        Fetch detailed information for a specific listing.

        Args:
            listing_id: Unique identifier for the listing.

        Returns:
            PropertyListing with full details, or None if not found.
        """
        pass
