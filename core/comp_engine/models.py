"""
Data models for Comp Engine v1.0

Defines structures for comparable sales data from UK Land Registry
and valuation results.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Optional


class PropertyType(Enum):
    """
    Property type classification.

    Exact match only - no cross-type substitution allowed.
    """
    FLAT = "flat"
    MAISONETTE = "maisonette"
    TERRACED = "terraced"
    SEMI_DETACHED = "semi-detached"
    DETACHED = "detached"

    @classmethod
    def from_string(cls, value: str) -> Optional["PropertyType"]:
        """Convert string to PropertyType, case-insensitive."""
        normalised = value.lower().strip().replace("_", "-")
        for member in cls:
            if member.value == normalised:
                return member
        return None


class Tenure(Enum):
    """
    Property tenure type.

    Freehold <-> Freehold only
    Leasehold <-> Leasehold only
    Shared ownership is excluded.
    """
    FREEHOLD = "freehold"
    LEASEHOLD = "leasehold"

    @classmethod
    def from_string(cls, value: str) -> Optional["Tenure"]:
        """Convert string to Tenure, case-insensitive."""
        normalised = value.lower().strip()
        for member in cls:
            if member.value == normalised:
                return member
        return None


class Confidence(Enum):
    """
    Confidence rating for valuation.

    High: >= 5 comps, <= 12 months, <= 0.5 miles
    Medium: 3-4 comps OR <= 18 months
    Low: Fallback radius/date used
    """
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Recommendation(Enum):
    """
    Deal recommendation based on BMV%.

    BMV% >= 15%: Strong
    BMV% 8-14%: Moderate
    BMV% 3-7%: Weak
    BMV% < 3%: Avoid
    BMV% < 0%: Overpriced
    """
    STRONG = "Strong"
    MODERATE = "Moderate"
    WEAK = "Weak"
    AVOID = "Avoid"
    OVERPRICED = "Overpriced"


@dataclass
class ComparableSale:
    """
    A comparable sale from UK Land Registry Price Paid Data.

    Represents a completed sale only - no asking prices, under offer,
    SSTC, withdrawn, or relisted properties.
    """
    # Required fields
    transaction_id: str
    price: int  # Sale price in GBP
    sale_date: date
    property_type: PropertyType
    tenure: Tenure
    postcode: str

    # Location (for distance calculation)
    latitude: float
    longitude: float

    # Address components
    paon: str = ""  # Primary Addressable Object Name (e.g., house number)
    saon: str = ""  # Secondary Addressable Object Name (e.g., flat number)
    street: str = ""
    locality: str = ""
    town: str = ""
    district: str = ""
    county: str = ""

    # Metadata
    new_build: bool = False

    @property
    def full_address(self) -> str:
        """Construct full address string."""
        parts = []
        if self.saon:
            parts.append(self.saon)
        if self.paon:
            parts.append(self.paon)
        if self.street:
            parts.append(self.street)
        if self.locality:
            parts.append(self.locality)
        if self.town:
            parts.append(self.town)
        if self.postcode:
            parts.append(self.postcode)
        return ", ".join(parts)

    @property
    def postcode_district(self) -> str:
        """Extract postcode district (e.g., 'SW1A' from 'SW1A 1AA')."""
        if not self.postcode:
            return ""
        parts = self.postcode.upper().split()
        return parts[0] if parts else ""


@dataclass
class SubjectProperty:
    """
    The subject property being valued.

    This is the auction/listing property we're finding comps for.
    """
    postcode: str
    property_type: PropertyType
    tenure: Tenure
    latitude: float
    longitude: float
    guide_price: int  # Asking/guide price

    # Optional address components
    address: str = ""

    @property
    def postcode_district(self) -> str:
        """Extract postcode district."""
        if not self.postcode:
            return ""
        parts = self.postcode.upper().split()
        return parts[0] if parts else ""


@dataclass
class CompSelectionResult:
    """
    Result of comp selection process.

    Contains selected comps and metadata about the selection.
    """
    comps: List[ComparableSale]
    radius_miles: float
    date_range_months: int

    # Selection metadata
    initial_count: int = 0  # Before outlier removal
    outliers_removed: int = 0
    fallback_used: bool = False

    @property
    def comp_count(self) -> int:
        """Number of comps after all filtering."""
        return len(self.comps)

    @property
    def is_sufficient(self) -> bool:
        """Whether minimum comp count (3) is met."""
        return self.comp_count >= 3


@dataclass
class ValuationResult:
    """
    Complete valuation result for a subject property.

    Output format as specified in requirements.
    """
    # Core valuation
    estimated_market_value: float
    bmv_percentage: float
    recommendation: Recommendation
    confidence: Confidence

    # Comp metadata
    comps_used: int
    comp_radius_miles: float
    comp_date_range_months: int

    # Detailed comp data (for audit trail)
    comp_prices: List[int] = field(default_factory=list)

    # Client-safe language
    valuation_statement: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON output."""
        return {
            "estimated_market_value": self.estimated_market_value,
            "bmv_percentage": self.bmv_percentage,
            "recommendation": self.recommendation.value,
            "confidence": self.confidence.value,
            "comps_used": self.comps_used,
            "comp_radius_miles": self.comp_radius_miles,
            "comp_date_range_months": self.comp_date_range_months,
        }
