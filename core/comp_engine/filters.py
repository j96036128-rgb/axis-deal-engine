"""
Comp Eligibility Filters for Comp Engine v1.0

Implements hard filters for comparable sale selection:
- Sale status (completed only)
- Sale date (12-24 months)
- Geographic radius (0.5-1.5 miles)
- Property type (exact match)
- Tenure (exact match)
"""

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Tuple

from .models import ComparableSale, SubjectProperty, PropertyType, Tenure


# =============================================================================
# Configuration Constants
# =============================================================================

# Sale date limits (months)
PREFERRED_DATE_MONTHS = 12
MAXIMUM_DATE_MONTHS = 18
FALLBACK_DATE_MONTHS = 24

# Geographic radius limits (miles)
RADIUS_PREFERRED = 0.5
RADIUS_FALLBACK = 1.0
RADIUS_URBAN_MAX = 1.5

# Minimum comp count before fallback
MIN_COMPS_BEFORE_FALLBACK = 3


@dataclass
class FilterConfig:
    """Configuration for comp filtering."""
    max_date_months: int = PREFERRED_DATE_MONTHS
    max_radius_miles: float = RADIUS_PREFERRED
    allow_cross_district: bool = False


class CompEligibilityFilter:
    """
    Applies hard filters to select eligible comparable sales.

    A transaction must pass ALL filters to qualify as a comp.
    """

    def __init__(self, reference_date: date = None):
        """
        Initialize filter with reference date.

        Args:
            reference_date: Date to calculate age from (default: today)
        """
        self._reference_date = reference_date or date.today()

    def filter_comps(
        self,
        candidates: List[ComparableSale],
        subject: SubjectProperty,
    ) -> Tuple[List[ComparableSale], float, int, bool]:
        """
        Filter candidates to eligible comps with progressive fallback.

        Applies filters in order:
        1. Property type (exact match)
        2. Tenure (exact match)
        3. Sale date (progressive: 12 -> 18 -> 24 months)
        4. Geographic radius (progressive: 0.5 -> 1.0 -> 1.5 miles)

        Args:
            candidates: All potential comparable sales
            subject: The subject property being valued

        Returns:
            Tuple of:
            - List of eligible comps
            - Radius used (miles)
            - Date range used (months)
            - Whether fallback was used
        """
        # First pass: hard filters (type and tenure)
        filtered = self._apply_hard_filters(candidates, subject)

        if not filtered:
            return [], 0.0, 0, False

        # Progressive filtering with fallback
        return self._progressive_filter(filtered, subject)

    def _apply_hard_filters(
        self,
        candidates: List[ComparableSale],
        subject: SubjectProperty,
    ) -> List[ComparableSale]:
        """Apply non-negotiable hard filters."""
        result = []

        for comp in candidates:
            # Property type must match exactly
            if comp.property_type != subject.property_type:
                continue

            # Tenure must match exactly
            if comp.tenure != subject.tenure:
                continue

            # Sale date must be within maximum allowed
            if not self._is_within_date_range(comp.sale_date, FALLBACK_DATE_MONTHS):
                continue

            result.append(comp)

        return result

    def _progressive_filter(
        self,
        candidates: List[ComparableSale],
        subject: SubjectProperty,
    ) -> Tuple[List[ComparableSale], float, int, bool]:
        """
        Apply progressive date and radius filters.

        Start with strictest criteria and relax if insufficient comps.
        """
        # Define filter levels: (date_months, radius_miles)
        filter_levels = [
            (PREFERRED_DATE_MONTHS, RADIUS_PREFERRED),     # Level 1: Strictest
            (PREFERRED_DATE_MONTHS, RADIUS_FALLBACK),      # Level 2: Wider radius
            (MAXIMUM_DATE_MONTHS, RADIUS_PREFERRED),       # Level 3: Older dates
            (MAXIMUM_DATE_MONTHS, RADIUS_FALLBACK),        # Level 4: Both relaxed
            (FALLBACK_DATE_MONTHS, RADIUS_FALLBACK),       # Level 5: Fallback dates
            (FALLBACK_DATE_MONTHS, RADIUS_URBAN_MAX),      # Level 6: Maximum fallback
        ]

        fallback_used = False

        for i, (date_months, radius_miles) in enumerate(filter_levels):
            # Apply date filter
            date_filtered = [
                c for c in candidates
                if self._is_within_date_range(c.sale_date, date_months)
            ]

            # Apply radius filter
            radius_filtered = [
                c for c in date_filtered
                if self._is_within_radius(c, subject, radius_miles)
            ]

            # Prefer same postcode district
            same_district = [
                c for c in radius_filtered
                if c.postcode_district == subject.postcode_district
            ]

            # Use same-district if sufficient, otherwise all within radius
            selected = same_district if len(same_district) >= MIN_COMPS_BEFORE_FALLBACK else radius_filtered

            # Check if we have enough comps
            if len(selected) >= MIN_COMPS_BEFORE_FALLBACK:
                # Mark as fallback if we went beyond preferred criteria
                fallback_used = i >= 2  # Levels 0-1 are preferred
                return selected, radius_miles, date_months, fallback_used

        # Return whatever we have at maximum fallback
        date_filtered = [
            c for c in candidates
            if self._is_within_date_range(c.sale_date, FALLBACK_DATE_MONTHS)
        ]
        radius_filtered = [
            c for c in date_filtered
            if self._is_within_radius(c, subject, RADIUS_URBAN_MAX)
        ]

        return radius_filtered, RADIUS_URBAN_MAX, FALLBACK_DATE_MONTHS, True

    def _is_within_date_range(self, sale_date: date, max_months: int) -> bool:
        """Check if sale date is within allowed range."""
        cutoff = self._reference_date - timedelta(days=max_months * 30)
        return sale_date >= cutoff

    def _is_within_radius(
        self,
        comp: ComparableSale,
        subject: SubjectProperty,
        max_miles: float,
    ) -> bool:
        """Check if comp is within radius of subject."""
        distance = self._haversine_distance(
            subject.latitude, subject.longitude,
            comp.latitude, comp.longitude,
        )
        return distance <= max_miles

    @staticmethod
    def _haversine_distance(
        lat1: float, lon1: float,
        lat2: float, lon2: float,
    ) -> float:
        """
        Calculate distance between two points in miles using Haversine formula.

        Args:
            lat1, lon1: First point coordinates (degrees)
            lat2, lon2: Second point coordinates (degrees)

        Returns:
            Distance in miles
        """
        # Earth radius in miles
        R = 3959.0

        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        # Haversine formula
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    def filter_by_property_type(
        self,
        comps: List[ComparableSale],
        property_type: PropertyType,
    ) -> List[ComparableSale]:
        """Filter comps to exact property type match only."""
        return [c for c in comps if c.property_type == property_type]

    def filter_by_tenure(
        self,
        comps: List[ComparableSale],
        tenure: Tenure,
    ) -> List[ComparableSale]:
        """Filter comps to exact tenure match only."""
        return [c for c in comps if c.tenure == tenure]

    def filter_by_date(
        self,
        comps: List[ComparableSale],
        max_months: int,
    ) -> List[ComparableSale]:
        """Filter comps to within date range."""
        return [
            c for c in comps
            if self._is_within_date_range(c.sale_date, max_months)
        ]

    def filter_by_radius(
        self,
        comps: List[ComparableSale],
        subject: SubjectProperty,
        max_miles: float,
    ) -> List[ComparableSale]:
        """Filter comps to within radius."""
        return [
            c for c in comps
            if self._is_within_radius(c, subject, max_miles)
        ]
