"""
Data models for the deal engine.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class SearchCriteria:
    """Search parameters for property listings."""

    location: str
    min_beds: int = 1
    max_beds: Optional[int] = None
    min_baths: int = 1
    max_baths: Optional[int] = None
    max_price: Optional[int] = None
    target_bmv_percent: float = 15.0  # Target below market value percentage

    def __post_init__(self):
        """Validate criteria after initialization."""
        if self.min_beds < 0:
            raise ValueError("min_beds must be non-negative")
        if self.max_beds is not None and self.max_beds < self.min_beds:
            raise ValueError("max_beds must be >= min_beds")
        if self.target_bmv_percent < 0 or self.target_bmv_percent > 100:
            raise ValueError("target_bmv_percent must be between 0 and 100")


@dataclass
class PropertyListing:
    """A property listing from any source."""

    id: str
    address: str
    area: str
    city: str
    postcode: str
    property_type: str
    bedrooms: int
    bathrooms: int
    asking_price: int
    estimated_value: int
    days_on_market: int
    listed_date: str
    source: str
    url: str

    # Optional fields
    description: str = ""
    features: list = field(default_factory=list)
    images: list = field(default_factory=list)

    @property
    def bmv_percent(self) -> float:
        """Calculate below market value percentage."""
        if self.estimated_value <= 0:
            return 0.0
        discount = self.estimated_value - self.asking_price
        return (discount / self.estimated_value) * 100


@dataclass
class DealAnalysis:
    """Analysis results for a property deal."""

    listing: PropertyListing
    bmv_score: float  # 0-100 composite score
    bmv_percent: float  # Actual BMV percentage
    urgency_score: float  # Based on days on market, price drops
    location_score: float  # Based on area desirability
    value_score: float  # Price vs estimated value
    overall_score: float  # Weighted composite
    recommendation: str  # "strong", "moderate", "weak", "avoid"
    notes: list = field(default_factory=list)

    @property
    def potential_profit(self) -> int:
        """Estimated profit if purchased at asking and sold at estimated value."""
        return self.listing.estimated_value - self.listing.asking_price

    @property
    def roi_percent(self) -> float:
        """Return on investment percentage."""
        if self.listing.asking_price <= 0:
            return 0.0
        return (self.potential_profit / self.listing.asking_price) * 100
