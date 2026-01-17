"""
Valuation Engine for Comp Engine v1.0

Implements:
- Quality controls (outlier removal, minimum comp count)
- EMV calculation using median
- BMV% calculation
- Recommendation bands
- Confidence rating
"""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from .models import (
    ComparableSale,
    SubjectProperty,
    CompSelectionResult,
    ValuationResult,
    Confidence,
    Recommendation,
)
from .filters import (
    CompEligibilityFilter,
    PREFERRED_DATE_MONTHS,
    RADIUS_PREFERRED,
)


# =============================================================================
# Configuration Constants
# =============================================================================

# Outlier removal percentiles
OUTLIER_BOTTOM_PERCENTILE = 10
OUTLIER_TOP_PERCENTILE = 90

# Minimum comp counts
MIN_COMPS_TARGET = 5
MIN_COMPS_ACCEPTABLE = 3

# Client-safe valuation statement (locked)
VALUATION_STATEMENT = (
    "Based on recent comparable sales within the immediate area, "
    "this property appears to be priced materially below prevailing market levels."
)


@dataclass
class QualityMetrics:
    """Quality metrics for comp selection."""
    initial_count: int
    after_outlier_removal: int
    outliers_removed: int
    is_sufficient: bool


class CompValuationEngine:
    """
    Complete valuation pipeline for comparable sales analysis.

    Pipeline order:
    1. FILTER - Apply eligibility filters
    2. QUALITY CONTROL - Remove outliers, validate count
    3. VALUATE - Calculate EMV using median
    4. RECOMMEND - Determine recommendation and confidence
    """

    def __init__(self, reference_date: date = None):
        """
        Initialize valuation engine.

        Args:
            reference_date: Reference date for calculations (default: today)
        """
        self._reference_date = reference_date or date.today()
        self._filter = CompEligibilityFilter(reference_date=self._reference_date)

    def valuate(
        self,
        subject: SubjectProperty,
        candidates: List[ComparableSale],
    ) -> ValuationResult:
        """
        Perform complete valuation for a subject property.

        Args:
            subject: The property being valued
            candidates: All potential comparable sales from Land Registry

        Returns:
            ValuationResult with EMV, BMV%, recommendation, confidence
        """
        # Step 1: Filter to eligible comps
        filtered_comps, radius_miles, date_months, fallback_used = (
            self._filter.filter_comps(candidates, subject)
        )

        # Step 2: Apply quality controls (outlier removal)
        quality_comps, quality_metrics = self._apply_quality_controls(filtered_comps)

        # Step 3: Calculate EMV using median
        emv = self._calculate_emv(quality_comps)

        # Step 4: Calculate BMV%
        bmv_percent = self._calculate_bmv_percent(emv, subject.guide_price)

        # Step 5: Determine confidence
        confidence = self._determine_confidence(
            comp_count=len(quality_comps),
            date_months=date_months,
            radius_miles=radius_miles,
            fallback_used=fallback_used,
        )

        # Step 6: Determine recommendation (with confidence caps)
        recommendation = self._determine_recommendation(
            bmv_percent=bmv_percent,
            confidence=confidence,
            comp_count=len(quality_comps),
        )

        # Step 7: Generate valuation statement
        valuation_statement = ""
        if bmv_percent >= 3 and len(quality_comps) >= MIN_COMPS_ACCEPTABLE:
            valuation_statement = VALUATION_STATEMENT

        return ValuationResult(
            estimated_market_value=emv,
            bmv_percentage=round(bmv_percent, 2),
            recommendation=recommendation,
            confidence=confidence,
            comps_used=len(quality_comps),
            comp_radius_miles=radius_miles,
            comp_date_range_months=date_months,
            comp_prices=[c.price for c in quality_comps],
            valuation_statement=valuation_statement,
        )

    def _apply_quality_controls(
        self,
        comps: List[ComparableSale],
    ) -> tuple[List[ComparableSale], QualityMetrics]:
        """
        Apply quality controls to comp selection.

        Removes top 10% and bottom 10% outliers by price.

        Args:
            comps: Filtered comparable sales

        Returns:
            Tuple of (cleaned comps, quality metrics)
        """
        initial_count = len(comps)

        if initial_count == 0:
            return [], QualityMetrics(
                initial_count=0,
                after_outlier_removal=0,
                outliers_removed=0,
                is_sufficient=False,
            )

        # Need at least 5 comps to remove outliers meaningfully
        if initial_count < 5:
            return comps, QualityMetrics(
                initial_count=initial_count,
                after_outlier_removal=initial_count,
                outliers_removed=0,
                is_sufficient=initial_count >= MIN_COMPS_ACCEPTABLE,
            )

        # Sort by price
        sorted_comps = sorted(comps, key=lambda c: c.price)

        # Calculate outlier indices
        bottom_cutoff = int(len(sorted_comps) * OUTLIER_BOTTOM_PERCENTILE / 100)
        top_cutoff = int(len(sorted_comps) * (100 - OUTLIER_TOP_PERCENTILE) / 100)

        # Remove outliers (bottom 10% and top 10%)
        if bottom_cutoff == 0:
            bottom_cutoff = 1 if len(sorted_comps) > 3 else 0
        if top_cutoff == 0:
            top_cutoff = 1 if len(sorted_comps) > 3 else 0

        cleaned = sorted_comps[bottom_cutoff:len(sorted_comps) - top_cutoff] if top_cutoff > 0 else sorted_comps[bottom_cutoff:]

        outliers_removed = initial_count - len(cleaned)

        return cleaned, QualityMetrics(
            initial_count=initial_count,
            after_outlier_removal=len(cleaned),
            outliers_removed=outliers_removed,
            is_sufficient=len(cleaned) >= MIN_COMPS_ACCEPTABLE,
        )

    def _calculate_emv(self, comps: List[ComparableSale]) -> float:
        """
        Calculate Estimated Market Value using median.

        EMV = Median(comp_prices)
        Do NOT use mean.

        Args:
            comps: Cleaned comparable sales

        Returns:
            Estimated Market Value (0 if no comps)
        """
        if not comps:
            return 0.0

        prices = sorted([c.price for c in comps])
        n = len(prices)

        if n % 2 == 1:
            # Odd number: middle element
            return float(prices[n // 2])
        else:
            # Even number: average of two middle elements
            mid = n // 2
            return float(prices[mid - 1] + prices[mid]) / 2

    def _calculate_bmv_percent(self, emv: float, guide_price: int) -> float:
        """
        Calculate Below Market Value percentage.

        BMV% = (EMV - Guide Price) / EMV * 100

        Args:
            emv: Estimated Market Value
            guide_price: Asking/guide price

        Returns:
            BMV percentage (negative if overpriced)
        """
        if emv <= 0:
            return 0.0

        return ((emv - guide_price) / emv) * 100

    def _determine_confidence(
        self,
        comp_count: int,
        date_months: int,
        radius_miles: float,
        fallback_used: bool,
    ) -> Confidence:
        """
        Determine confidence rating.

        High: >= 5 comps, <= 12 months, <= 0.5 miles
        Medium: 3-4 comps OR <= 18 months
        Low: Fallback radius/date used

        Args:
            comp_count: Number of comps used
            date_months: Date range used
            radius_miles: Radius used
            fallback_used: Whether fallback criteria were used

        Returns:
            Confidence rating
        """
        # Low confidence if fallback was used
        if fallback_used:
            return Confidence.LOW

        # Low confidence if fewer than minimum comps
        if comp_count < MIN_COMPS_ACCEPTABLE:
            return Confidence.LOW

        # High confidence requires all criteria met
        if (
            comp_count >= MIN_COMPS_TARGET
            and date_months <= PREFERRED_DATE_MONTHS
            and radius_miles <= RADIUS_PREFERRED
        ):
            return Confidence.HIGH

        # Medium confidence for acceptable but not ideal
        return Confidence.MEDIUM

    def _determine_recommendation(
        self,
        bmv_percent: float,
        confidence: Confidence,
        comp_count: int,
    ) -> Recommendation:
        """
        Determine deal recommendation based on BMV%.

        Bands:
        - >= 15%: Strong
        - 8-14%: Moderate
        - 3-7%: Weak
        - < 3%: Avoid
        - < 0%: Overpriced

        Caps:
        - If confidence = Low: Cannot exceed Moderate
        - If comps < 3: Cannot exceed Weak

        Args:
            bmv_percent: BMV percentage
            confidence: Confidence rating
            comp_count: Number of comps

        Returns:
            Recommendation
        """
        # Determine base recommendation from BMV%
        if bmv_percent < 0:
            base_rec = Recommendation.OVERPRICED
        elif bmv_percent < 3:
            base_rec = Recommendation.AVOID
        elif bmv_percent < 8:
            base_rec = Recommendation.WEAK
        elif bmv_percent < 15:
            base_rec = Recommendation.MODERATE
        else:
            base_rec = Recommendation.STRONG

        # Apply caps based on confidence and comp count

        # Cap 1: If comps < 3, cannot exceed Weak
        if comp_count < MIN_COMPS_ACCEPTABLE:
            if base_rec in (Recommendation.STRONG, Recommendation.MODERATE):
                return Recommendation.WEAK

        # Cap 2: If confidence = Low, cannot exceed Moderate
        if confidence == Confidence.LOW:
            if base_rec == Recommendation.STRONG:
                return Recommendation.MODERATE

        return base_rec

    def select_comps(
        self,
        subject: SubjectProperty,
        candidates: List[ComparableSale],
    ) -> CompSelectionResult:
        """
        Select and filter comps without full valuation.

        Useful for auditing/debugging the selection process.

        Args:
            subject: Subject property
            candidates: All potential comps

        Returns:
            CompSelectionResult with selected comps and metadata
        """
        filtered_comps, radius_miles, date_months, fallback_used = (
            self._filter.filter_comps(candidates, subject)
        )

        cleaned_comps, quality_metrics = self._apply_quality_controls(filtered_comps)

        return CompSelectionResult(
            comps=cleaned_comps,
            radius_miles=radius_miles,
            date_range_months=date_months,
            initial_count=quality_metrics.initial_count,
            outliers_removed=quality_metrics.outliers_removed,
            fallback_used=fallback_used,
        )
