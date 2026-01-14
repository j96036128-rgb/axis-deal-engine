"""
BMV (Below Market Value) scoring logic.
"""

from typing import List

from .models import PropertyListing, DealAnalysis, SearchCriteria


class BMVScorer:
    """
    Calculates BMV scores and deal analysis for property listings.

    Scoring methodology:
    - BMV Score (40%): How far below market value
    - Urgency Score (25%): Days on market, indicating motivation
    - Location Score (20%): Area desirability (placeholder)
    - Value Score (15%): Price-to-value ratio
    """

    # Scoring weights
    WEIGHT_BMV = 0.40
    WEIGHT_URGENCY = 0.25
    WEIGHT_LOCATION = 0.20
    WEIGHT_VALUE = 0.15

    # Thresholds
    BMV_EXCELLENT = 20.0  # 20%+ below market = excellent
    BMV_GOOD = 10.0  # 10%+ = good
    BMV_FAIR = 5.0  # 5%+ = fair

    URGENCY_HIGH_DAYS = 90  # 90+ days = motivated seller
    URGENCY_MEDIUM_DAYS = 60

    def __init__(self):
        """Initialize scorer with default configuration."""
        pass

    def analyze(
        self,
        listing: PropertyListing,
        criteria: SearchCriteria,
    ) -> DealAnalysis:
        """
        Analyze a single listing and produce a deal analysis.

        Args:
            listing: The property listing to analyze.
            criteria: The search criteria used.

        Returns:
            DealAnalysis with scores and recommendation.
        """
        bmv_score = self._calculate_bmv_score(listing)
        urgency_score = self._calculate_urgency_score(listing)
        location_score = self._calculate_location_score(listing)
        value_score = self._calculate_value_score(listing, criteria)

        # Calculate weighted overall score
        overall_score = (
            bmv_score * self.WEIGHT_BMV
            + urgency_score * self.WEIGHT_URGENCY
            + location_score * self.WEIGHT_LOCATION
            + value_score * self.WEIGHT_VALUE
        )

        # Determine recommendation
        recommendation = self._get_recommendation(overall_score, listing.bmv_percent)

        # Generate notes
        notes = self._generate_notes(listing, bmv_score, urgency_score)

        return DealAnalysis(
            listing=listing,
            bmv_score=round(bmv_score, 1),
            bmv_percent=round(listing.bmv_percent, 1),
            urgency_score=round(urgency_score, 1),
            location_score=round(location_score, 1),
            value_score=round(value_score, 1),
            overall_score=round(overall_score, 1),
            recommendation=recommendation,
            notes=notes,
        )

    def analyze_batch(
        self,
        listings: List[PropertyListing],
        criteria: SearchCriteria,
    ) -> List[DealAnalysis]:
        """
        Analyze multiple listings.

        Args:
            listings: List of property listings.
            criteria: Search criteria used.

        Returns:
            List of DealAnalysis sorted by overall score (descending).
        """
        analyses = [self.analyze(listing, criteria) for listing in listings]
        return sorted(analyses, key=lambda x: x.overall_score, reverse=True)

    def _calculate_bmv_score(self, listing: PropertyListing) -> float:
        """
        Calculate BMV score (0-100).

        Higher score = better deal (more below market value).
        """
        bmv = listing.bmv_percent

        if bmv >= self.BMV_EXCELLENT:
            # 20%+ BMV = 80-100 score
            return min(100, 80 + (bmv - 20) * 2)
        elif bmv >= self.BMV_GOOD:
            # 10-20% BMV = 50-80 score
            return 50 + (bmv - 10) * 3
        elif bmv >= self.BMV_FAIR:
            # 5-10% BMV = 25-50 score
            return 25 + (bmv - 5) * 5
        elif bmv >= 0:
            # 0-5% BMV = 0-25 score
            return bmv * 5
        else:
            # Overpriced = negative score capped at 0
            return 0

    def _calculate_urgency_score(self, listing: PropertyListing) -> float:
        """
        Calculate urgency score (0-100).

        Longer time on market = more motivated seller.
        """
        days = listing.days_on_market

        if days >= self.URGENCY_HIGH_DAYS:
            # 90+ days = high urgency, 70-100 score
            return min(100, 70 + (days - 90) * 0.3)
        elif days >= self.URGENCY_MEDIUM_DAYS:
            # 60-90 days = medium urgency, 40-70 score
            return 40 + (days - 60) * 1
        elif days >= 30:
            # 30-60 days = low-medium, 20-40 score
            return 20 + (days - 30) * 0.67
        else:
            # <30 days = new listing, 0-20 score
            return days * 0.67

    def _calculate_location_score(self, listing: PropertyListing) -> float:
        """
        Calculate location score (0-100).

        Placeholder: Returns moderate score. Future versions will use
        actual location data, crime stats, school ratings, etc.
        """
        # Placeholder: return 50 (neutral) for all locations
        # TODO: Integrate actual location scoring data
        return 50.0

    def _calculate_value_score(
        self,
        listing: PropertyListing,
        criteria: SearchCriteria,
    ) -> float:
        """
        Calculate value score (0-100).

        Based on whether the deal meets target BMV criteria.
        """
        target = criteria.target_bmv_percent
        actual = listing.bmv_percent

        if actual >= target:
            # Meets or exceeds target = 70-100
            excess = actual - target
            return min(100, 70 + excess * 3)
        elif actual >= target * 0.5:
            # At least half target = 30-70
            ratio = actual / target
            return 30 + ratio * 40
        elif actual > 0:
            # Some discount = 0-30
            ratio = actual / (target * 0.5)
            return ratio * 30
        else:
            # No discount or overpriced
            return 0

    def _get_recommendation(self, overall_score: float, bmv_percent: float) -> str:
        """Determine deal recommendation based on scores."""
        if overall_score >= 70 and bmv_percent >= 10:
            return "strong"
        elif overall_score >= 50 or bmv_percent >= 15:
            return "moderate"
        elif overall_score >= 30 or bmv_percent >= 5:
            return "weak"
        else:
            return "avoid"

    def _generate_notes(
        self,
        listing: PropertyListing,
        bmv_score: float,
        urgency_score: float,
    ) -> List[str]:
        """Generate analysis notes for the listing."""
        notes = []

        # BMV notes
        if listing.bmv_percent >= 20:
            notes.append(f"Excellent BMV: {listing.bmv_percent:.1f}% below market")
        elif listing.bmv_percent >= 10:
            notes.append(f"Good BMV: {listing.bmv_percent:.1f}% below market")
        elif listing.bmv_percent < 0:
            notes.append(f"Overpriced by {abs(listing.bmv_percent):.1f}%")

        # Urgency notes
        if listing.days_on_market >= 90:
            notes.append(f"Long time on market ({listing.days_on_market} days) - motivated seller likely")
        elif listing.days_on_market <= 7:
            notes.append("New listing - may have competition")

        # Price notes
        if listing.asking_price < 100000:
            notes.append("Low price point - verify condition")
        elif listing.asking_price > 500000:
            notes.append("Higher price point - larger capital requirement")

        return notes
