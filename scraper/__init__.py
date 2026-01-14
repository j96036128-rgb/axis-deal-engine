"""
Scraper module for fetching property listings.
"""

from .base import BaseScraper
from .mock import MockScraper

__all__ = ["BaseScraper", "MockScraper"]
