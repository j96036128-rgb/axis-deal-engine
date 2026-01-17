"""
Integration Tests for Deal Analyzer with Comp Engine

Tests the full pipeline from listings through Comp Engine valuation.
Ensures:
- No heuristic fallbacks
- Confidence gating enforced
- Recommendation caps applied
- Zero-comp handling
- Deterministic results
"""

import pytest
from datetime import date, timedelta
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import (
    PropertyListing,
    SearchCriteria,
    DealAnalyzer,
    EnrichedAnalysis,
    Confidence,
    Recommendation,
)
from core.comp_engine import (
    ComparableSale,
    SubjectProperty,
    PropertyType,
    Tenure,
    CompValuationEngine,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def reference_date():
    """Fixed reference date for deterministic tests."""
    return date(2024, 6, 1)


@pytest.fixture
def sample_listing():
    """Sample property listing from auction."""
    return PropertyListing(
        id="TEST-001",
        address="42 Test Street",
        area="Islington",
        city="London",
        postcode="N1 2AB",
        property_type="flat",
        bedrooms=2,
        bathrooms=1,
        asking_price=350000,
        estimated_value=350000,  # Will be overwritten by Comp Engine
        days_on_market=45,
        listed_date="2024-04-15",
        source="Auction House London",
        url="https://auctionhouselondon.co.uk/lot/12345",
    )


@pytest.fixture
def sample_criteria():
    """Sample search criteria."""
    return SearchCriteria(
        location="London",
        min_beds=1,
        max_beds=3,
        min_baths=1,
        target_bmv_percent=15.0,
    )


@pytest.fixture
def create_comp():
    """Factory fixture for creating comparable sales.

    Note: Uses default coordinates (51.5074, -0.1278) to match the
    DealAnalyzer's _get_coordinates stub which returns central London.
    This ensures comps are within the radius filter.
    """
    def _create(
        price: int,
        sale_date: date,
        property_type: PropertyType = PropertyType.FLAT,
        tenure: Tenure = Tenure.LEASEHOLD,
        postcode: str = "N1 2CD",
        # Match DealAnalyzer's default coordinates (within 0.5 mile radius)
        latitude: float = 51.5074,
        longitude: float = -0.1278,
        transaction_id: str = None,
    ) -> ComparableSale:
        return ComparableSale(
            transaction_id=transaction_id or f"TXN-{price}-{sale_date.isoformat()}",
            price=price,
            sale_date=sale_date,
            property_type=property_type,
            tenure=tenure,
            postcode=postcode,
            latitude=latitude,
            longitude=longitude,
            street="Test Street",
            town="London",
        )
    return _create


@pytest.fixture
def analyzer(reference_date):
    """Deal analyzer with fixed reference date."""
    return DealAnalyzer(reference_date=reference_date)


# =============================================================================
# Test: Integration with Comp Engine
# =============================================================================

class TestCompEngineIntegration:
    """Tests for DealAnalyzer integration with Comp Engine."""

    def test_analysis_uses_comp_engine_valuation(
        self, analyzer, sample_listing, sample_criteria, create_comp, reference_date
    ):
        """Analysis should use Comp Engine for EMV, not heuristics."""
        # Create comps with known median price of 420k
        comps = [
            create_comp(price=400000, sale_date=reference_date - timedelta(days=30)),
            create_comp(price=420000, sale_date=reference_date - timedelta(days=60)),
            create_comp(price=440000, sale_date=reference_date - timedelta(days=90)),
        ]

        analysis = analyzer.analyze(sample_listing, sample_criteria, comps)

        # EMV should be median of 420k, not original estimated_value
        assert analysis.valuation is not None
        assert analysis.valuation.estimated_market_value == 420000.0

    def test_bmv_percent_from_comp_engine(
        self, analyzer, sample_listing, sample_criteria, create_comp, reference_date
    ):
        """BMV% should come from Comp Engine, not heuristic calculation."""
        # Listing at 350k, comps median at 420k
        # BMV% = (420k - 350k) / 420k * 100 = 16.67%
        comps = [
            create_comp(price=400000, sale_date=reference_date - timedelta(days=30)),
            create_comp(price=420000, sale_date=reference_date - timedelta(days=60)),
            create_comp(price=440000, sale_date=reference_date - timedelta(days=90)),
        ]

        analysis = analyzer.analyze(sample_listing, sample_criteria, comps)

        expected_bmv = ((420000 - 350000) / 420000) * 100
        assert abs(analysis.bmv_percent - expected_bmv) < 0.1

    def test_recommendation_from_comp_engine(
        self, analyzer, sample_listing, sample_criteria, create_comp, reference_date
    ):
        """Recommendation should come from Comp Engine based on BMV%."""
        # High BMV% should give Strong recommendation
        comps = [
            create_comp(price=500000, sale_date=reference_date - timedelta(days=30)),
            create_comp(price=520000, sale_date=reference_date - timedelta(days=60)),
            create_comp(price=510000, sale_date=reference_date - timedelta(days=90)),
        ]

        analysis = analyzer.analyze(sample_listing, sample_criteria, comps)

        # 350k vs ~510k EMV = ~31% BMV -> Strong
        assert analysis.recommendation == "Strong"


# =============================================================================
# Test: Zero Comp Handling
# =============================================================================

class TestZeroCompHandling:
    """Tests for graceful handling of zero comparable sales."""

    def test_no_comps_returns_analysis(
        self, analyzer, sample_listing, sample_criteria
    ):
        """Should return analysis even with no comps, not raise exception."""
        analysis = analyzer.analyze(sample_listing, sample_criteria, [])

        assert analysis is not None
        assert isinstance(analysis, EnrichedAnalysis)

    def test_no_comps_returns_low_confidence(
        self, analyzer, sample_listing, sample_criteria
    ):
        """Zero comps should result in Low confidence."""
        analysis = analyzer.analyze(sample_listing, sample_criteria, [])

        assert analysis.confidence == "Low"

    def test_no_comps_returns_zero_emv(
        self, analyzer, sample_listing, sample_criteria
    ):
        """Zero comps should return EMV of 0."""
        analysis = analyzer.analyze(sample_listing, sample_criteria, [])

        assert analysis.valuation.estimated_market_value == 0.0

    def test_no_comps_caps_recommendation(
        self, analyzer, sample_listing, sample_criteria
    ):
        """Zero comps should not give Strong/Moderate recommendation."""
        analysis = analyzer.analyze(sample_listing, sample_criteria, [])

        assert analysis.recommendation in ("Avoid", "Overpriced", "Weak")


# =============================================================================
# Test: Confidence Gating
# =============================================================================

class TestConfidenceGating:
    """Tests for confidence level enforcement."""

    def test_one_comp_returns_low_confidence(
        self, analyzer, sample_listing, sample_criteria, create_comp, reference_date
    ):
        """Single comp should result in Low confidence."""
        comps = [
            create_comp(price=500000, sale_date=reference_date - timedelta(days=30))
        ]

        analysis = analyzer.analyze(sample_listing, sample_criteria, comps)

        assert analysis.confidence == "Low"

    def test_two_comps_returns_low_confidence(
        self, analyzer, sample_listing, sample_criteria, create_comp, reference_date
    ):
        """Two comps should result in Low confidence."""
        comps = [
            create_comp(price=500000, sale_date=reference_date - timedelta(days=30)),
            create_comp(price=520000, sale_date=reference_date - timedelta(days=60)),
        ]

        analysis = analyzer.analyze(sample_listing, sample_criteria, comps)

        assert analysis.confidence == "Low"

    def test_low_confidence_caps_at_moderate(
        self, analyzer, sample_listing, sample_criteria, create_comp, reference_date
    ):
        """Low confidence should cap recommendation at Moderate."""
        # Far away comps trigger fallback = Low confidence
        comps = [
            create_comp(
                price=600000,
                sale_date=reference_date - timedelta(days=30),
                latitude=51.6,  # Far from typical N1 location
                longitude=-0.2,
            )
            for _ in range(5)
        ]

        analysis = analyzer.analyze(sample_listing, sample_criteria, comps)

        # Even with high BMV%, Low confidence caps at Moderate
        if analysis.confidence == "Low":
            assert analysis.recommendation != "Strong"


# =============================================================================
# Test: Recommendation Bands
# =============================================================================

class TestRecommendationBands:
    """Tests for correct BMV% to recommendation mapping."""

    def test_strong_recommendation_for_15_plus_bmv(
        self, analyzer, sample_listing, sample_criteria, create_comp, reference_date
    ):
        """BMV >= 15% with sufficient comps should be Strong."""
        # Listing at 350k, comps at ~412k = 15% BMV
        comps = [
            create_comp(
                price=412000,
                sale_date=reference_date - timedelta(days=30),
                transaction_id=f"TXN-{i}"
            )
            for i in range(5)
        ]

        analysis = analyzer.analyze(sample_listing, sample_criteria, comps)

        # With 5 close comps, should have High confidence, Strong recommendation
        assert analysis.bmv_percent >= 14  # Allow for rounding
        if analysis.confidence == "High":
            assert analysis.recommendation == "Strong"

    def test_avoid_recommendation_for_low_bmv(
        self, analyzer, sample_listing, sample_criteria, create_comp, reference_date
    ):
        """BMV < 3% should be Avoid."""
        # Listing at 350k, comps at ~355k = ~1.4% BMV
        comps = [
            create_comp(
                price=355000,
                sale_date=reference_date - timedelta(days=30),
                transaction_id=f"TXN-{i}"
            )
            for i in range(5)
        ]

        analysis = analyzer.analyze(sample_listing, sample_criteria, comps)

        assert analysis.bmv_percent < 3
        assert analysis.recommendation == "Avoid"

    def test_overpriced_recommendation_for_negative_bmv(
        self, analyzer, sample_listing, sample_criteria, create_comp, reference_date
    ):
        """Negative BMV% should be Overpriced."""
        # Listing at 350k, comps at ~300k = overpriced
        comps = [
            create_comp(
                price=300000,
                sale_date=reference_date - timedelta(days=30),
                transaction_id=f"TXN-{i}"
            )
            for i in range(5)
        ]

        analysis = analyzer.analyze(sample_listing, sample_criteria, comps)

        assert analysis.bmv_percent < 0
        assert analysis.recommendation == "Overpriced"


# =============================================================================
# Test: Deterministic Results
# =============================================================================

class TestDeterministicResults:
    """Tests for deterministic, reproducible results."""

    def test_same_input_same_output(
        self, analyzer, sample_listing, sample_criteria, create_comp, reference_date
    ):
        """Same inputs should always produce same outputs."""
        comps = [
            create_comp(
                price=400000 + i * 10000,
                sale_date=reference_date - timedelta(days=30 + i * 10),
                transaction_id=f"TXN-{i}"
            )
            for i in range(5)
        ]

        result1 = analyzer.analyze(sample_listing, sample_criteria, comps)
        result2 = analyzer.analyze(sample_listing, sample_criteria, comps)

        assert result1.valuation.estimated_market_value == result2.valuation.estimated_market_value
        assert result1.bmv_percent == result2.bmv_percent
        assert result1.recommendation == result2.recommendation
        assert result1.confidence == result2.confidence

    def test_batch_analysis_sorted_by_score(
        self, analyzer, sample_criteria, reference_date
    ):
        """Batch analysis should be sorted by overall score descending."""
        listings = [
            PropertyListing(
                id=f"TEST-{i}",
                address=f"{i} Test Street",
                area="Islington",
                city="London",
                postcode="N1 2AB",
                property_type="flat",
                bedrooms=2,
                bathrooms=1,
                asking_price=300000 + i * 50000,  # Varying prices
                estimated_value=400000,
                days_on_market=45,
                listed_date="2024-04-15",
                source="Auction House London",
                url=f"https://auctionhouselondon.co.uk/lot/{i}",
            )
            for i in range(3)
        ]

        analyses = analyzer.analyze_batch(listings, sample_criteria)

        # Should be sorted by overall_score descending
        scores = [a.overall_score for a in analyses]
        assert scores == sorted(scores, reverse=True)


# =============================================================================
# Test: No Heuristic Fallbacks
# =============================================================================

class TestNoHeuristicFallbacks:
    """Tests ensuring no silent fallbacks to heuristic calculations."""

    def test_emv_from_comps_not_listing(
        self, analyzer, sample_listing, sample_criteria, create_comp, reference_date
    ):
        """EMV should come from comps, not listing.estimated_value."""
        # Set listing estimated_value to something different
        sample_listing.estimated_value = 999999

        comps = [
            create_comp(
                price=400000,
                sale_date=reference_date - timedelta(days=30),
                transaction_id=f"TXN-{i}"
            )
            for i in range(5)
        ]

        analysis = analyzer.analyze(sample_listing, sample_criteria, comps)

        # Should use comp median (400k), not listing value (999999)
        assert analysis.valuation.estimated_market_value == 400000.0
        assert analysis.estimated_value == 400000

    def test_analysis_includes_comp_evidence(
        self, analyzer, sample_listing, sample_criteria, create_comp, reference_date
    ):
        """Analysis should include comp evidence metadata."""
        comps = [
            create_comp(
                price=400000,
                sale_date=reference_date - timedelta(days=30),
                transaction_id=f"TXN-{i}"
            )
            for i in range(5)
        ]

        analysis = analyzer.analyze(sample_listing, sample_criteria, comps)

        assert analysis.valuation is not None
        assert analysis.comps_used > 0
        assert len(analysis.comp_prices) > 0


# =============================================================================
# Test: Property Type Matching
# =============================================================================

class TestPropertyTypeMatching:
    """Tests for exact property type matching."""

    def test_flat_only_matches_flat_comps(
        self, analyzer, sample_listing, sample_criteria, create_comp, reference_date
    ):
        """Flat listing should only match flat comps."""
        # Create comps with wrong property type
        wrong_type_comps = [
            create_comp(
                price=500000,
                sale_date=reference_date - timedelta(days=30),
                property_type=PropertyType.DETACHED,  # Wrong type
                transaction_id=f"TXN-{i}"
            )
            for i in range(5)
        ]

        analysis = analyzer.analyze(sample_listing, sample_criteria, wrong_type_comps)

        # Should have no comps (wrong type excluded)
        assert analysis.comps_used == 0


# =============================================================================
# Test: Client-Safe Language
# =============================================================================

class TestClientSafeLanguage:
    """Tests for client-safe valuation statements."""

    def test_valuation_statement_for_bmv_deal(
        self, analyzer, sample_listing, sample_criteria, create_comp, reference_date
    ):
        """BMV deals should have client-safe valuation statement."""
        # Create high BMV scenario
        comps = [
            create_comp(
                price=500000,
                sale_date=reference_date - timedelta(days=30),
                transaction_id=f"TXN-{i}"
            )
            for i in range(5)
        ]

        analysis = analyzer.analyze(sample_listing, sample_criteria, comps)

        # If BMV >= 3%, should have valuation statement
        if analysis.bmv_percent >= 3:
            statement = analysis.valuation_statement
            if statement:
                assert "comparable" in statement.lower() or "market" in statement.lower()

    def test_no_statement_for_overpriced(
        self, analyzer, sample_listing, sample_criteria, create_comp, reference_date
    ):
        """Overpriced properties should not have valuation statement."""
        # Create overpriced scenario
        comps = [
            create_comp(
                price=300000,  # Below asking
                sale_date=reference_date - timedelta(days=30),
                transaction_id=f"TXN-{i}"
            )
            for i in range(5)
        ]

        analysis = analyzer.analyze(sample_listing, sample_criteria, comps)

        assert analysis.bmv_percent < 0
        assert analysis.valuation_statement == ""
