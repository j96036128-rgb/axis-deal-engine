"""
Deal Analyzer - Integrated Comp Engine Pipeline

Replaces heuristic BMV calculations with Land Registry-based valuations.
All BMV% and recommendations now come from the Comp Engine.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from .models import PropertyListing, DealAnalysis, SearchCriteria
from .comp_engine import (
    CompValuationEngine,
    SubjectProperty,
    PropertyType,
    Tenure,
    ValuationResult,
    Confidence,
    Recommendation,
    ComparableSale,
)
from .land_registry import get_land_registry_service


# =============================================================================
# Configuration
# =============================================================================

# Scoring weights (adjusted for comp-based analysis)
WEIGHT_BMV = 0.50  # Increased weight for comp-based BMV
WEIGHT_URGENCY = 0.20
WEIGHT_LOCATION = 0.15
WEIGHT_VALUE = 0.15

# Urgency thresholds
URGENCY_HIGH_DAYS = 90
URGENCY_MEDIUM_DAYS = 60


@dataclass
class EnrichedAnalysis:
    """
    Deal analysis enriched with Comp Engine valuation.

    Contains both the original analysis fields and the full
    ValuationResult from the Comp Engine.
    """
    listing: PropertyListing
    valuation: Optional[ValuationResult]

    # Scores (derived from Comp Engine)
    bmv_score: float
    urgency_score: float
    location_score: float
    value_score: float
    overall_score: float

    # Recommendation from Comp Engine
    recommendation: str
    confidence: str

    # Notes and analysis
    notes: List[str] = field(default_factory=list)

    # Planning context (optional, attached later)
    planning: Optional[object] = None
    combined_opportunity: bool = False

    @property
    def bmv_percent(self) -> float:
        """BMV percentage from Comp Engine."""
        if self.valuation:
            return self.valuation.bmv_percentage
        return 0.0

    @property
    def estimated_value(self) -> int:
        """Estimated market value from Comp Engine."""
        if self.valuation:
            return int(self.valuation.estimated_market_value)
        return self.listing.asking_price  # Fallback to asking if no comps

    @property
    def potential_profit(self) -> int:
        """Potential profit based on comp-derived EMV."""
        return self.estimated_value - self.listing.asking_price

    @property
    def roi_percent(self) -> float:
        """ROI based on comp-derived EMV."""
        if self.listing.asking_price <= 0:
            return 0.0
        return (self.potential_profit / self.listing.asking_price) * 100

    @property
    def comps_used(self) -> int:
        """Number of comps used in valuation."""
        if self.valuation:
            return self.valuation.comps_used
        return 0

    @property
    def comp_prices(self) -> List[int]:
        """Prices of comps used."""
        if self.valuation:
            return self.valuation.comp_prices
        return []

    @property
    def valuation_statement(self) -> str:
        """Client-safe valuation statement."""
        if self.valuation:
            return self.valuation.valuation_statement
        return ""


class DealAnalyzer:
    """
    Integrated deal analyzer using Comp Engine for all valuations.

    Replaces the old BMVScorer heuristics with factual,
    Land Registry-based comparable sales analysis.
    """

    def __init__(self, reference_date: date = None):
        """
        Initialize the deal analyzer.

        Args:
            reference_date: Reference date for comp filtering (default: today)
        """
        self._reference_date = reference_date or date.today()
        self._comp_engine = CompValuationEngine(reference_date=self._reference_date)
        self._land_registry = get_land_registry_service()

    def analyze(
        self,
        listing: PropertyListing,
        criteria: SearchCriteria,
        comparable_sales: List[ComparableSale] = None,
    ) -> EnrichedAnalysis:
        """
        Analyze a single listing using the Comp Engine.

        Args:
            listing: The property listing to analyze
            criteria: Search criteria for context
            comparable_sales: Optional pre-fetched comps (fetched if not provided)

        Returns:
            EnrichedAnalysis with Comp Engine valuation
        """
        # Build SubjectProperty from listing
        subject = self._listing_to_subject(listing)

        # Fetch comps if not provided
        if comparable_sales is None:
            comparable_sales = self._land_registry.fetch_comparables_for_subject(
                subject, self._reference_date
            )

        # Run Comp Engine valuation
        valuation = self._comp_engine.valuate(subject, comparable_sales)

        # Calculate component scores
        bmv_score = self._calculate_bmv_score(valuation)
        urgency_score = self._calculate_urgency_score(listing)
        location_score = self._calculate_location_score(listing)
        value_score = self._calculate_value_score(valuation, criteria)

        # Calculate weighted overall score
        overall_score = (
            bmv_score * WEIGHT_BMV
            + urgency_score * WEIGHT_URGENCY
            + location_score * WEIGHT_LOCATION
            + value_score * WEIGHT_VALUE
        )

        # Generate notes
        notes = self._generate_notes(listing, valuation)

        return EnrichedAnalysis(
            listing=listing,
            valuation=valuation,
            bmv_score=round(bmv_score, 1),
            urgency_score=round(urgency_score, 1),
            location_score=round(location_score, 1),
            value_score=round(value_score, 1),
            overall_score=round(overall_score, 1),
            recommendation=valuation.recommendation.value,
            confidence=valuation.confidence.value,
            notes=notes,
        )

    def analyze_batch(
        self,
        listings: List[PropertyListing],
        criteria: SearchCriteria,
    ) -> List[EnrichedAnalysis]:
        """
        Analyze multiple listings.

        Args:
            listings: List of property listings
            criteria: Search criteria

        Returns:
            List of EnrichedAnalysis sorted by overall score (descending)
        """
        analyses = [self.analyze(listing, criteria) for listing in listings]

        # Sort by overall score, then by BMV%
        return sorted(
            analyses,
            key=lambda x: (x.overall_score, x.bmv_percent),
            reverse=True,
        )

    def _listing_to_subject(self, listing: PropertyListing) -> SubjectProperty:
        """
        Convert a PropertyListing to a SubjectProperty.

        Args:
            listing: The property listing

        Returns:
            SubjectProperty for Comp Engine
        """
        # Map property type string to enum
        property_type = self._map_property_type(listing.property_type)

        # Infer tenure from property type (flats typically leasehold, houses freehold)
        # In production, this should come from listing data
        tenure = self._infer_tenure(listing.property_type)

        # Get coordinates from postcode
        # In production, this would use a geocoding service
        lat, lon = self._get_coordinates(listing.postcode)

        return SubjectProperty(
            postcode=listing.postcode,
            property_type=property_type,
            tenure=tenure,
            latitude=lat,
            longitude=lon,
            guide_price=listing.asking_price,
            address=listing.address,
        )

    def _map_property_type(self, property_type_str: str) -> PropertyType:
        """Map listing property type string to PropertyType enum."""
        mapping = {
            "flat": PropertyType.FLAT,
            "apartment": PropertyType.FLAT,
            "maisonette": PropertyType.MAISONETTE,
            "terraced": PropertyType.TERRACED,
            "terrace": PropertyType.TERRACED,
            "end terrace": PropertyType.TERRACED,
            "mid terrace": PropertyType.TERRACED,
            "semi-detached": PropertyType.SEMI_DETACHED,
            "semi detached": PropertyType.SEMI_DETACHED,
            "semi": PropertyType.SEMI_DETACHED,
            "detached": PropertyType.DETACHED,
            "bungalow": PropertyType.DETACHED,  # Approximate
            "house": PropertyType.SEMI_DETACHED,  # Default for generic "house"
        }

        normalized = property_type_str.lower().strip()
        return mapping.get(normalized, PropertyType.TERRACED)  # Default to terraced

    def _infer_tenure(self, property_type_str: str) -> Tenure:
        """Infer tenure from property type."""
        # Flats are typically leasehold, houses typically freehold
        normalized = property_type_str.lower().strip()
        if normalized in ("flat", "apartment", "maisonette"):
            return Tenure.LEASEHOLD
        return Tenure.FREEHOLD

    def _get_coordinates(self, postcode: str) -> tuple[float, float]:
        """
        Get coordinates for a postcode.

        In production, this would use a geocoding service.
        For now, returns approximate London coordinates.
        """
        # Stub: return central London coordinates
        # In production, use OS Places API or similar
        return (51.5074, -0.1278)

    def _calculate_bmv_score(self, valuation: ValuationResult) -> float:
        """
        Calculate BMV score (0-100) from Comp Engine valuation.

        Based on BMV% and confidence level.
        """
        bmv = valuation.bmv_percentage

        # Base score from BMV%
        if bmv >= 20:
            base_score = min(100, 80 + (bmv - 20) * 2)
        elif bmv >= 15:
            base_score = 60 + (bmv - 15) * 4
        elif bmv >= 10:
            base_score = 40 + (bmv - 10) * 4
        elif bmv >= 5:
            base_score = 20 + (bmv - 5) * 4
        elif bmv >= 0:
            base_score = bmv * 4
        else:
            base_score = 0

        # Apply confidence modifier
        confidence_modifier = {
            Confidence.HIGH: 1.0,
            Confidence.MEDIUM: 0.85,
            Confidence.LOW: 0.7,
        }
        modifier = confidence_modifier.get(valuation.confidence, 0.7)

        return base_score * modifier

    def _calculate_urgency_score(self, listing: PropertyListing) -> float:
        """Calculate urgency score based on days on market."""
        days = listing.days_on_market

        if days >= URGENCY_HIGH_DAYS:
            return min(100, 70 + (days - 90) * 0.3)
        elif days >= URGENCY_MEDIUM_DAYS:
            return 40 + (days - 60) * 1
        elif days >= 30:
            return 20 + (days - 30) * 0.67
        else:
            return days * 0.67

    def _calculate_location_score(self, listing: PropertyListing) -> float:
        """
        Calculate location score.

        Placeholder - returns neutral score.
        Future: integrate location data, crime stats, schools, etc.
        """
        return 50.0

    def _calculate_value_score(
        self,
        valuation: ValuationResult,
        criteria: SearchCriteria,
    ) -> float:
        """
        Calculate value score based on meeting target BMV.
        """
        target = criteria.target_bmv_percent
        actual = valuation.bmv_percentage

        if actual >= target:
            excess = actual - target
            return min(100, 70 + excess * 3)
        elif actual >= target * 0.5:
            ratio = actual / target
            return 30 + ratio * 40
        elif actual > 0:
            ratio = actual / (target * 0.5)
            return ratio * 30
        else:
            return 0

    def _generate_notes(
        self,
        listing: PropertyListing,
        valuation: ValuationResult,
    ) -> List[str]:
        """Generate analysis notes."""
        notes = []

        # BMV notes from Comp Engine
        bmv = valuation.bmv_percentage
        if bmv >= 15:
            notes.append(f"Strong BMV: {bmv:.1f}% below comparable sales")
        elif bmv >= 8:
            notes.append(f"Good BMV: {bmv:.1f}% below comparable sales")
        elif bmv >= 3:
            notes.append(f"Marginal BMV: {bmv:.1f}% below comparable sales")
        elif bmv < 0:
            notes.append(f"Overpriced by {abs(bmv):.1f}% vs comparable sales")

        # Confidence notes
        if valuation.confidence == Confidence.HIGH:
            notes.append(f"High confidence ({valuation.comps_used} comps)")
        elif valuation.confidence == Confidence.MEDIUM:
            notes.append(f"Medium confidence ({valuation.comps_used} comps)")
        else:
            notes.append(f"Low confidence - limited comparable data ({valuation.comps_used} comps)")

        # Urgency notes
        if listing.days_on_market >= 90:
            notes.append(f"Long time on market ({listing.days_on_market} days) - motivated seller likely")
        elif listing.days_on_market <= 7:
            notes.append("New listing - may have competition")

        # Valuation statement (if available)
        if valuation.valuation_statement:
            notes.append(valuation.statement if hasattr(valuation, 'statement') else "")

        return [n for n in notes if n]  # Filter empty notes
