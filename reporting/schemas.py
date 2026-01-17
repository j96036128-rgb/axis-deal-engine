"""
Canonical schemas for Capital Opportunity Memorandum generation.

These schemas define the exact structure expected by the PDF generator
for producing client-ready deliverables.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class ConvictionRating(Enum):
    """
    Conviction levels reflecting confidence in the opportunity assessment.
    Based on data quality, market conditions, and risk factors.
    """
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PriorityLevel(Enum):
    """Priority ranking for opportunities within a mandate."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"


class PlanningLabel(Enum):
    """Planning potential assessment labels."""
    EXCEPTIONAL = "exceptional"
    STRONG = "strong"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class PlanningContext:
    """
    Planning assessment for an opportunity.
    Contains scoring and factors affecting development potential.
    """
    score: int  # 0-100
    label: str  # exceptional, strong, medium, low
    uplift_percent_low: float
    uplift_percent_high: float
    positive_factors: List[str] = field(default_factory=list)
    negative_factors: List[str] = field(default_factory=list)
    rationale: str = ""

    @property
    def has_upside(self) -> bool:
        """Returns True if planning score indicates meaningful upside."""
        return self.score >= 60


@dataclass
class UpliftScenario:
    """
    Value uplift projections for an opportunity.
    Three scenarios: conservative, base, and upside.
    """
    conservative_percent: float
    conservative_value: int
    base_percent: float
    base_value: int
    upside_percent: float
    upside_value: int


@dataclass
class ScoreBreakdown:
    """Detailed score breakdown for an opportunity."""
    bmv_score: float
    urgency_score: float
    location_score: float
    value_score: float
    overall_score: float


@dataclass
class CompEvidence:
    """
    Comparable sales evidence from UK Land Registry Price Paid Data.
    Provides factual basis for EMV calculation.
    """
    comps_used: int = 0
    comp_radius_miles: float = 0.0
    comp_date_range_months: int = 0
    comp_prices: List[int] = field(default_factory=list)
    valuation_statement: str = ""

    @property
    def has_evidence(self) -> bool:
        """Returns True if there is comparable sales evidence."""
        return self.comps_used > 0


@dataclass
class OpportunityMemo:
    """
    Complete opportunity data for the Capital Opportunity Memorandum.
    Contains all information needed for the two-page opportunity detail section.
    """
    # Identity
    opportunity_id: str
    address: str
    area: str
    city: str
    postcode: str
    property_type: str

    # Financials
    asking_price: int
    estimated_value: int
    bmv_percent: float
    potential_profit: int
    roi_percent: float

    # Property details
    bedrooms: int
    bathrooms: int
    days_on_market: int

    # Scoring
    scores: ScoreBreakdown
    recommendation: str  # strong, moderate, weak, avoid, overpriced
    conviction: ConvictionRating
    priority: PriorityLevel = PriorityLevel.SECONDARY

    # Analysis
    investment_thesis: str = ""
    pricing_insight: str = ""
    key_risks: List[str] = field(default_factory=list)
    key_strengths: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    # Comp Engine evidence (v1.0)
    comp_evidence: Optional[CompEvidence] = None

    # Planning (optional)
    planning: Optional[PlanningContext] = None

    # Uplift scenarios (optional, for value creation page)
    uplift_scenarios: Optional[UpliftScenario] = None

    @property
    def is_combined_opportunity(self) -> bool:
        """Returns True if this is both a BMV deal and has planning upside."""
        if self.planning is None:
            return False
        return self.bmv_percent >= 10 and self.planning.has_upside

    @property
    def has_comp_evidence(self) -> bool:
        """Returns True if EMV is backed by comparable sales evidence."""
        return self.comp_evidence is not None and self.comp_evidence.has_evidence


@dataclass
class MandateParameters:
    """
    The mandate parameters as specified by the client.
    Echoed back in the 'Your Mandate' section.
    """
    location: str
    min_beds: int
    max_beds: Optional[int]
    min_baths: int
    max_price: Optional[int]
    min_price: Optional[int] = None
    target_bmv_percent: float = 15.0
    strategy: str = "BMV + Planning"
    property_types: List[str] = field(default_factory=list)
    additional_filters: List[str] = field(default_factory=list)


@dataclass
class Mandate:
    """
    Complete mandate data for report generation.
    This is the top-level input schema for the PDF generator.
    """
    # Identification
    reference_id: str  # Format: AXA-YYYYMMDD-XXX
    client_name: str
    client_entity: Optional[str] = None
    report_date: str = ""  # ISO format: YYYY-MM-DD
    generated_at: str = ""  # ISO format timestamp

    # Mandate specification
    parameters: MandateParameters = None

    # Summary statistics
    total_properties_screened: int = 0
    opportunities_identified: int = 0
    average_bmv_percent: float = 0.0
    total_potential_value: int = 0
    capital_range_low: int = 0
    capital_range_high: int = 0

    # Executive summary narrative
    executive_summary: str = ""

    # The opportunities (3-4 typically)
    opportunities: List[OpportunityMemo] = field(default_factory=list)

    # Report metadata
    disclaimer_version: str = "1.0"
    report_version: str = "1.0"


# =============================================================================
# Factory Functions
# =============================================================================

def create_sample_mandate() -> Mandate:
    """
    Create a sample mandate for testing PDF generation.
    Uses realistic mock data for demonstration purposes.
    """
    from datetime import datetime

    return Mandate(
        reference_id="AXA-20240115-001",
        client_name="Meridian Property Holdings",
        client_entity="Meridian Property Holdings Ltd",
        report_date="2024-01-15",
        generated_at=datetime.now().isoformat(),
        parameters=MandateParameters(
            location="Greater Manchester",
            min_beds=2,
            max_beds=4,
            min_baths=1,
            min_price=150000,
            max_price=400000,
            target_bmv_percent=15.0,
            strategy="BMV + Planning",
            property_types=["terraced", "semi-detached", "flat"],
            additional_filters=[
                "Minimum 60 days on market",
                "Freehold or long leasehold (80+ years)",
            ],
        ),
        total_properties_screened=127,
        opportunities_identified=3,
        average_bmv_percent=16.0,
        total_potential_value=135000,
        capital_range_low=175000,
        capital_range_high=310000,
        executive_summary=(
            "This mandate focused on identifying below-market-value residential "
            "opportunities in Greater Manchester with potential for value creation "
            "through planning-led strategies. From 127 properties screened, three "
            "opportunities met the specified criteria, offering a combined potential "
            "value of £135,000 across varying capital requirements and risk profiles."
        ),
        opportunities=[
            OpportunityMemo(
                opportunity_id="OPP-001",
                address="42 Victoria Street",
                area="Salford",
                city="Manchester",
                postcode="M3 5FS",
                property_type="terraced",
                asking_price=225000,
                estimated_value=275000,
                bmv_percent=18.2,
                potential_profit=50000,
                roi_percent=22.2,
                bedrooms=3,
                bathrooms=1,
                days_on_market=94,
                scores=ScoreBreakdown(
                    bmv_score=74.0,
                    urgency_score=71.2,
                    location_score=50.0,
                    value_score=79.6,
                    overall_score=68.9,
                ),
                recommendation="strong",
                conviction=ConvictionRating.HIGH,
                priority=PriorityLevel.PRIMARY,
                investment_thesis=(
                    "Extended time on market suggests motivated seller. Strong BMV "
                    "with solid fundamentals in an established residential area showing "
                    "signs of improvement. Planning potential for loft conversion adds "
                    "further value creation opportunity."
                ),
                pricing_insight=(
                    "Current asking price of £225,000 represents an 18.2% discount to "
                    "estimated market value. Comparable sales in the immediate area over "
                    "the past 6 months support the £275,000 valuation. Extended marketing "
                    "period suggests room for negotiation."
                ),
                key_strengths=[
                    "18.2% below estimated market value",
                    "94 days on market indicates seller motivation",
                    "3-bed terraced in established residential area",
                    "Strong planning potential for loft conversion",
                ],
                key_risks=[
                    "Property condition unknown - survey essential",
                    "Competition from other investors possible",
                    "Planning permission not guaranteed",
                ],
                notes=[
                    "Victorian terrace with period features",
                    "Close to transport links",
                    "Freehold tenure confirmed",
                ],
                planning=PlanningContext(
                    score=72,
                    label="strong",
                    uplift_percent_low=8.0,
                    uplift_percent_high=15.0,
                    positive_factors=[
                        "Suitable property type for extensions",
                        "Freehold ownership allows full control",
                        "No conservation area restrictions",
                        "Precedent for similar works in street",
                    ],
                    negative_factors=[
                        "May require party wall agreement",
                    ],
                    rationale=(
                        "Victorian terraced property with loft conversion potential. "
                        "Similar conversions completed on the street provide positive precedent."
                    ),
                ),
                uplift_scenarios=UpliftScenario(
                    conservative_percent=8.0,
                    conservative_value=22000,
                    base_percent=12.0,
                    base_value=33000,
                    upside_percent=15.0,
                    upside_value=41000,
                ),
            ),
            OpportunityMemo(
                opportunity_id="OPP-002",
                address="15 Oak Lane",
                area="Didsbury",
                city="Manchester",
                postcode="M20 2EF",
                property_type="semi-detached",
                asking_price=310000,
                estimated_value=365000,
                bmv_percent=15.1,
                potential_profit=55000,
                roi_percent=17.7,
                bedrooms=4,
                bathrooms=2,
                days_on_market=67,
                scores=ScoreBreakdown(
                    bmv_score=65.3,
                    urgency_score=47.0,
                    location_score=50.0,
                    value_score=70.3,
                    overall_score=59.1,
                ),
                recommendation="moderate",
                conviction=ConvictionRating.MEDIUM,
                priority=PriorityLevel.SECONDARY,
                investment_thesis=(
                    "Quality family home in desirable South Manchester suburb. "
                    "Moderate time on market with solid BMV indicates good value. "
                    "Strong rental demand provides alternative exit strategy."
                ),
                pricing_insight=(
                    "Asking price of £310,000 is 15.1% below estimated market value. "
                    "Didsbury commands premium prices but this property appears "
                    "competitively positioned. Higher capital requirement but lower "
                    "execution risk given property condition."
                ),
                key_strengths=[
                    "15.1% below estimated market value",
                    "4-bed semi in prime Didsbury location",
                    "Strong rental demand in area",
                    "Good condition reduces refurbishment risk",
                ],
                key_risks=[
                    "Higher capital requirement (£310,000)",
                    "Competitive market in this price bracket",
                    "Limited planning upside without major works",
                ],
                notes=[
                    "Extended kitchen completed 2021",
                    "South-facing garden",
                    "Off-street parking for 2 vehicles",
                ],
                planning=None,
                uplift_scenarios=None,
            ),
            OpportunityMemo(
                opportunity_id="OPP-003",
                address="8 Canal Street",
                area="Ancoats",
                city="Manchester",
                postcode="M4 6AB",
                property_type="flat",
                asking_price=175000,
                estimated_value=205000,
                bmv_percent=14.6,
                potential_profit=30000,
                roi_percent=17.1,
                bedrooms=2,
                bathrooms=1,
                days_on_market=45,
                scores=ScoreBreakdown(
                    bmv_score=63.0,
                    urgency_score=30.1,
                    location_score=50.0,
                    value_score=68.0,
                    overall_score=53.5,
                ),
                recommendation="moderate",
                conviction=ConvictionRating.MEDIUM,
                priority=PriorityLevel.TERTIARY,
                investment_thesis=(
                    "Modern flat in regeneration area with strong rental potential. "
                    "Lower entry point suits portfolio building or first-time investors. "
                    "Ancoats continues to benefit from urban regeneration."
                ),
                pricing_insight=(
                    "At £175,000, this represents a 14.6% discount to estimated value. "
                    "New build premium has depreciated since 2019 construction, creating "
                    "the buying opportunity. Service charges require verification."
                ),
                key_strengths=[
                    "14.6% below estimated market value",
                    "Strong rental yields in Ancoats (5.5-6%)",
                    "Lower capital requirement",
                    "Modern specification reduces maintenance",
                ],
                key_risks=[
                    "Leasehold - verify ground rent and service charges",
                    "Service charges may impact net returns",
                    "Flat market more sensitive to interest rates",
                ],
                notes=[
                    "New build completed 2019",
                    "Allocated parking space included",
                    "Concierge and gym facilities",
                ],
                planning=None,
                uplift_scenarios=None,
            ),
        ],
    )
