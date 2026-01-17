"""
Comp Engine v1.0

Comparable sales selection and valuation pipeline using UK Land Registry
Price Paid Data to calculate EMV, BMV%, and confidence ratings.

Data Source: UK Land Registry Price Paid Data (completed sales only)
"""

from .models import (
    ComparableSale,
    SubjectProperty,
    PropertyType,
    Tenure,
    CompSelectionResult,
    ValuationResult,
    Confidence,
    Recommendation,
)
from .filters import CompEligibilityFilter
from .valuation import CompValuationEngine

__all__ = [
    # Models
    "ComparableSale",
    "SubjectProperty",
    "PropertyType",
    "Tenure",
    "CompSelectionResult",
    "ValuationResult",
    "Confidence",
    "Recommendation",
    # Engine
    "CompEligibilityFilter",
    "CompValuationEngine",
]

__version__ = "1.0"
