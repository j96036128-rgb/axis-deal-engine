"""
Scraper module for fetching property listings.

Available scrapers:
- MockScraper: Development/testing with generated data
- AuctionHouseLondonScraper: Live auction listings from auctionhouselondon.co.uk
"""

from .base import BaseScraper
from .mock import MockScraper
from .auction_house_london import (
    AuctionHouseLondonScraper,
    AuctionListing,
    fetch_auction_listings,
)

__all__ = [
    "BaseScraper",
    "MockScraper",
    "AuctionHouseLondonScraper",
    "AuctionListing",
    "fetch_auction_listings",
]
