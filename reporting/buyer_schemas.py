"""
Buyer PDF Schema - Axis Allocation Capital Opportunity Memorandum

LOCKED SCHEMA - Do not modify without explicit versioning (v1.1+).

This schema defines the exact structure for client-facing PDF output.
All content must derive from VerifiedPropertyExport only.

Principles:
- Conservative: No superlatives, no guarantees
- Transparent: All confidence levels visible
- Verification-aware: Explicit unverified flags
- Non-advisory: No investment advice
- Deterministic: Same input = same output

Schema Version: 1.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Final, List, Optional

from core.submission.export import TrustLevel, VerifiedPropertyExport


# =============================================================================
# Constants (LOCKED)
# =============================================================================

SCHEMA_VERSION: Final[str] = "1.0"

# Controlled language for assessments (no superlatives)
ASSESSMENT_LANGUAGE: Final[dict[str, str]] = {
    "strong_high": "Opportunity meets core criteria with high data confidence.",
    "strong_medium": "Opportunity meets core criteria. Data confidence is moderate.",
    "strong_low": "Opportunity meets core criteria. Data confidence is limited.",
    "moderate_high": "Opportunity partially meets criteria with high data confidence.",
    "moderate_medium": "Opportunity partially meets criteria. Data confidence is moderate.",
    "moderate_low": "Opportunity partially meets criteria. Data confidence is limited.",
    "weak_high": "Opportunity has limited alignment with criteria.",
    "weak_low": "Opportunity has limited alignment with criteria. Data confidence is limited.",
}

# Fixed legal disclaimer text (NEVER CHANGE WITHOUT LEGAL REVIEW)
FIXED_LEGAL_DISCLAIMER: Final[str] = """
This document has been prepared by Axis Allocation Limited for informational purposes only.
It does not constitute investment advice, financial advice, legal advice, tax advice,
or a recommendation to buy, sell, or hold any asset.

Axis Allocation is not authorised or regulated by the Financial Conduct Authority.
No representation or warranty, express or implied, is made as to the accuracy, completeness,
or reliability of the information contained herein.

Any decision to proceed with a transaction must be based on the recipient's own independent
investigation and assessment. Recipients should seek professional advice from qualified
advisors before making any investment decisions.

Past performance is not indicative of future results. Property values may go down as well
as up. All investments carry risk.

Jurisdiction: England & Wales
"""

# Fixed document authorship
DOCUMENT_AUTHOR: Final[str] = "Axis Allocation Limited"
JURISDICTION: Final[str] = "England & Wales"


# =============================================================================
# Enums
# =============================================================================


class DealClassification(Enum):
    """Deal classification from Deal Engine only."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    AVOID = "avoid"


class ConfidenceLevel(Enum):
    """Confidence level for valuations and assessments."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FactVerificationStatus(Enum):
    """Verification status for individual facts."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    NOT_AVAILABLE = "not_available"


class ScenarioType(Enum):
    """Types of value creation scenarios."""

    PLANNING_UPLIFT = "planning_uplift"
    REFURBISHMENT = "refurbishment"
    CHANGE_OF_USE = "change_of_use"
    EXTENSION = "extension"


# =============================================================================
# Section 1: Cover Page Schema
# =============================================================================


@dataclass(frozen=True)
class CoverPage:
    """
    Cover page content (Section 1).

    Rules:
    - No photos
    - No superlatives
    - No centering
    """

    # Wordmark (fixed)
    wordmark: str = "AXIS ALLOCATION"

    # Property reference (from VerifiedPropertyExport)
    property_reference: str = ""

    # Client name (optional)
    client_name: Optional[str] = None

    # Document date
    document_date: str = ""  # ISO-8601

    # Document version (locked)
    document_version: str = SCHEMA_VERSION

    # Fixed legal disclaimer (never changes)
    legal_disclaimer: str = (
        "This document has been prepared by Axis Allocation for discussion purposes only. "
        "It does not constitute investment advice, a recommendation, or an offer to buy or sell any asset."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "wordmark": self.wordmark,
            "property_reference": self.property_reference,
            "client_name": self.client_name,
            "document_date": self.document_date,
            "document_version": self.document_version,
            "legal_disclaimer": self.legal_disclaimer,
        }


# =============================================================================
# Section 2: Executive Summary Schema
# =============================================================================


@dataclass(frozen=True)
class ExecutiveSummary:
    """
    Executive summary content (Section 2, max 1 page).

    All fields derived from Deal Engine output only.

    Forbidden:
    - Guarantees
    - Buy/sell language
    - ROI claims
    """

    # Deal classification (from Deal Engine only)
    deal_classification: DealClassification

    # Estimated Market Value (comps-based only)
    estimated_market_value: int

    # BMV percentage
    bmv_percent: float

    # BMV range (if confidence < HIGH)
    bmv_range_low: Optional[float] = None
    bmv_range_high: Optional[float] = None

    # Confidence level (MANDATORY)
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW

    # Planning upside (only if verified)
    planning_upside_verified: bool = False
    planning_upside_description: Optional[str] = None

    # Overall assessment (controlled language only)
    overall_assessment: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "deal_classification": self.deal_classification.value,
            "estimated_market_value": self.estimated_market_value,
            "bmv_percent": self.bmv_percent,
            "bmv_range_low": self.bmv_range_low,
            "bmv_range_high": self.bmv_range_high,
            "confidence_level": self.confidence_level.value,
            "planning_upside_verified": self.planning_upside_verified,
            "planning_upside_description": self.planning_upside_description,
            "overall_assessment": self.overall_assessment,
        }


# =============================================================================
# Section 3: Verified Facts Snapshot Schema
# =============================================================================


@dataclass(frozen=True)
class VerifiedFact:
    """Single verified fact entry for the snapshot table."""

    category: str
    fact: str
    value: str
    status: FactVerificationStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "fact": self.fact,
            "value": self.value,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class VerifiedFactsSnapshot:
    """
    Verified facts table (Section 3).

    Rules:
    - Explicit unverified flags
    - Colour-coded trust indicators
    - No assumptions
    """

    facts: tuple[VerifiedFact, ...]
    trust_level: TrustLevel
    verified_count: int
    unverified_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "facts": [f.to_dict() for f in self.facts],
            "trust_level": self.trust_level.value,
            "verified_count": self.verified_count,
            "unverified_count": self.unverified_count,
        }


# =============================================================================
# Section 4: Valuation Evidence Schema
# =============================================================================


@dataclass(frozen=True)
class ValuationEvidence:
    """
    Comparable sales evidence (Section 4).

    Required fields:
    - Comp count
    - Radius
    - Date range
    - Median price (never mean)

    Locked language prefix:
    "Based on recent comparable transactions within the immediate area..."
    """

    # Locked language prefix
    evidence_statement: str = "Based on recent comparable transactions within the immediate area"

    # Required comp data
    comp_count: int = 0
    radius_miles: float = 0.0
    date_range_months: int = 0

    # Median price (NEVER mean)
    median_price: int = 0

    # Confidence indicator
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW

    # Individual comp hashes for audit trail
    comp_transaction_references: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_statement": self.evidence_statement,
            "comp_count": self.comp_count,
            "radius_miles": self.radius_miles,
            "date_range_months": self.date_range_months,
            "median_price": self.median_price,
            "confidence_level": self.confidence_level.value,
            "comp_transaction_references": list(self.comp_transaction_references),
        }


# =============================================================================
# Section 5: Value Creation Scenarios Schema
# =============================================================================


@dataclass(frozen=True)
class ValueCreationScenario:
    """
    Single value creation scenario.

    Forbidden:
    - ROI projections
    - Guarantees
    """

    scenario_type: ScenarioType
    description: str
    preconditions: tuple[str, ...]
    risks: tuple[str, ...]
    verification_dependencies: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_type": self.scenario_type.value,
            "description": self.description,
            "preconditions": list(self.preconditions),
            "risks": list(self.risks),
            "verification_dependencies": list(self.verification_dependencies),
        }


@dataclass(frozen=True)
class ValueCreationSection:
    """Value creation scenarios (Section 5)."""

    scenarios: tuple[ValueCreationScenario, ...]
    has_verified_planning: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenarios": [s.to_dict() for s in self.scenarios],
            "has_verified_planning": self.has_verified_planning,
        }


# =============================================================================
# Section 6: Risks & Unknowns Schema
# =============================================================================


@dataclass(frozen=True)
class RisksAndUnknowns:
    """
    Risks & unknowns section (Section 6, MANDATORY).

    This section can NEVER be empty.

    Must include:
    - Unverified facts
    - Planning uncertainty
    - Market sensitivity
    """

    # Unverified facts (always present if any unverified)
    unverified_facts: tuple[str, ...]

    # Planning uncertainty (always present)
    planning_uncertainty: str

    # Market sensitivity (always present)
    market_sensitivity: str

    # Additional risks
    additional_risks: tuple[str, ...] = ()

    def is_valid(self) -> bool:
        """Section must never be empty."""
        return bool(
            self.unverified_facts
            or self.planning_uncertainty
            or self.market_sensitivity
            or self.additional_risks
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "unverified_facts": list(self.unverified_facts),
            "planning_uncertainty": self.planning_uncertainty,
            "market_sensitivity": self.market_sensitivity,
            "additional_risks": list(self.additional_risks),
        }


# =============================================================================
# Section 7: Next Steps Schema
# =============================================================================


@dataclass(frozen=True)
class NextSteps:
    """
    Next steps section (Section 7, NON-ADVISORY).

    Allowed:
    - "Further diligence recommended"
    - "Specialist advice required"

    Forbidden:
    - Investment advice
    - Calls to transact
    """

    # Controlled next step items
    items: tuple[str, ...]

    # All items must be non-advisory
    ALLOWED_PHRASES: tuple[str, ...] = (
        "Further diligence recommended",
        "Specialist advice required",
        "Professional survey recommended",
        "Legal review of title recommended",
        "Planning consultation recommended",
        "Independent valuation recommended",
        "Lease review required for leasehold properties",
        "Environmental assessment may be required",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": list(self.items),
        }


# =============================================================================
# Section 8: Integrity & Provenance Schema
# =============================================================================


@dataclass(frozen=True)
class IntegrityProvenance:
    """
    Integrity & provenance section (Section 8).

    Table contents:
    - Logbook hash chain status
    - Document hashes
    - Evaluation timestamp
    """

    # Logbook hash chain
    logbook_hash: str
    chain_valid: bool
    logbook_version: int

    # Document hashes
    title_register_hash: Optional[str] = None
    epc_hash: Optional[str] = None

    # Evaluation timestamp
    evaluation_timestamp: str = ""  # ISO-8601

    # Export version
    export_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "logbook_hash": self.logbook_hash,
            "chain_valid": self.chain_valid,
            "logbook_version": self.logbook_version,
            "title_register_hash": self.title_register_hash,
            "epc_hash": self.epc_hash,
            "evaluation_timestamp": self.evaluation_timestamp,
            "export_version": self.export_version,
        }


# =============================================================================
# Section 9: Legal Footer Schema
# =============================================================================


@dataclass(frozen=True)
class LegalFooter:
    """
    Legal footer (Section 9, FIXED).

    Includes:
    - Non-advisory disclaimer
    - Generic data sources
    - Authorship: Axis Allocation
    - Jurisdiction: England & Wales
    """

    # Fixed disclaimer (NEVER CHANGE)
    disclaimer: str = FIXED_LEGAL_DISCLAIMER

    # Data sources (generic)
    data_sources: str = "UK Land Registry Price Paid Data, EPC Register, and other public sources"

    # Authorship
    author: str = DOCUMENT_AUTHOR

    # Jurisdiction
    jurisdiction: str = JURISDICTION

    def to_dict(self) -> dict[str, Any]:
        return {
            "disclaimer": self.disclaimer,
            "data_sources": self.data_sources,
            "author": self.author,
            "jurisdiction": self.jurisdiction,
        }


# =============================================================================
# Root Document Schema
# =============================================================================


@dataclass(frozen=True)
class BuyerMemorandum:
    """
    Complete Buyer PDF document schema.

    All content MUST derive from VerifiedPropertyExport.

    Rules:
    - PDF content must be derived only from VerifiedPropertyExport
    - Confidence level must always be visible
    - Missing sections = hard error
    - Layout must fit within page limits (no spillover)
    """

    # Document metadata
    schema_version: str = SCHEMA_VERSION
    generated_at: str = ""  # ISO-8601

    # Source data reference
    source_export_version: str = ""
    source_property_id: str = ""

    # Section 1: Cover Page
    cover_page: CoverPage = field(default_factory=CoverPage)

    # Section 2: Executive Summary
    executive_summary: Optional[ExecutiveSummary] = None

    # Section 3: Verified Facts Snapshot
    verified_facts: Optional[VerifiedFactsSnapshot] = None

    # Section 4: Valuation Evidence
    valuation_evidence: Optional[ValuationEvidence] = None

    # Section 5: Value Creation Scenarios
    value_creation: Optional[ValueCreationSection] = None

    # Section 6: Risks & Unknowns (MANDATORY)
    risks_and_unknowns: Optional[RisksAndUnknowns] = None

    # Section 7: Next Steps
    next_steps: Optional[NextSteps] = None

    # Section 8: Integrity & Provenance
    integrity_provenance: Optional[IntegrityProvenance] = None

    # Section 9: Legal Footer
    legal_footer: LegalFooter = field(default_factory=LegalFooter)

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate that all required sections are present.

        Returns (is_valid, list_of_errors).
        """
        errors = []

        # All sections must be present
        if self.executive_summary is None:
            errors.append("Missing required section: Executive Summary")
        if self.verified_facts is None:
            errors.append("Missing required section: Verified Facts Snapshot")
        if self.valuation_evidence is None:
            errors.append("Missing required section: Valuation Evidence")
        if self.risks_and_unknowns is None:
            errors.append("Missing required section: Risks & Unknowns")
        elif not self.risks_and_unknowns.is_valid():
            errors.append("Risks & Unknowns section cannot be empty")
        if self.next_steps is None:
            errors.append("Missing required section: Next Steps")
        if self.integrity_provenance is None:
            errors.append("Missing required section: Integrity & Provenance")

        # Confidence level must be visible
        if self.executive_summary and self.executive_summary.confidence_level is None:
            errors.append("Confidence level must be visible in Executive Summary")

        return (len(errors) == 0, errors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "source_export_version": self.source_export_version,
            "source_property_id": self.source_property_id,
            "cover_page": self.cover_page.to_dict(),
            "executive_summary": self.executive_summary.to_dict() if self.executive_summary else None,
            "verified_facts": self.verified_facts.to_dict() if self.verified_facts else None,
            "valuation_evidence": self.valuation_evidence.to_dict() if self.valuation_evidence else None,
            "value_creation": self.value_creation.to_dict() if self.value_creation else None,
            "risks_and_unknowns": self.risks_and_unknowns.to_dict() if self.risks_and_unknowns else None,
            "next_steps": self.next_steps.to_dict() if self.next_steps else None,
            "integrity_provenance": self.integrity_provenance.to_dict() if self.integrity_provenance else None,
            "legal_footer": self.legal_footer.to_dict(),
        }


# =============================================================================
# Validation Error
# =============================================================================


class BuyerMemorandumValidationError(Exception):
    """Raised when memorandum validation fails."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Memorandum validation failed: {'; '.join(errors)}")


# =============================================================================
# Factory Function
# =============================================================================


def create_buyer_memorandum_from_export(
    export: VerifiedPropertyExport,
    deal_classification: DealClassification,
    estimated_market_value: int,
    bmv_percent: float,
    confidence_level: ConfidenceLevel,
    comp_count: int = 0,
    comp_radius_miles: float = 0.0,
    comp_date_range_months: int = 0,
    client_name: Optional[str] = None,
    bmv_range_low: Optional[float] = None,
    bmv_range_high: Optional[float] = None,
) -> BuyerMemorandum:
    """
    Create a BuyerMemorandum from a VerifiedPropertyExport.

    This factory ensures all content derives from verified data only.

    Args:
        export: The VerifiedPropertyExport source
        deal_classification: Classification from Deal Engine
        estimated_market_value: EMV from comp-based valuation
        bmv_percent: Below market value percentage
        confidence_level: Valuation confidence
        comp_count: Number of comparable sales used
        comp_radius_miles: Radius for comp search
        comp_date_range_months: Date range for comps
        client_name: Optional client name for cover page
        bmv_range_low: Low end of BMV range (if confidence < HIGH)
        bmv_range_high: High end of BMV range (if confidence < HIGH)

    Returns:
        BuyerMemorandum ready for PDF generation
    """
    now = datetime.utcnow()

    # Build cover page
    cover_page = CoverPage(
        property_reference=export.property_id,
        client_name=client_name,
        document_date=now.strftime("%Y-%m-%d"),
    )

    # Build executive summary with controlled language
    assessment_key = f"{deal_classification.value}_{confidence_level.value}"
    overall_assessment = ASSESSMENT_LANGUAGE.get(
        assessment_key,
        "Opportunity requires further evaluation.",
    )

    # Only include planning upside if verified
    planning_verified = export.property_facts.planning.existing_permissions is not None

    executive_summary = ExecutiveSummary(
        deal_classification=deal_classification,
        estimated_market_value=estimated_market_value,
        bmv_percent=bmv_percent,
        bmv_range_low=bmv_range_low if confidence_level != ConfidenceLevel.HIGH else None,
        bmv_range_high=bmv_range_high if confidence_level != ConfidenceLevel.HIGH else None,
        confidence_level=confidence_level,
        planning_upside_verified=planning_verified,
        planning_upside_description=None if not planning_verified else "Planning status verified",
        overall_assessment=overall_assessment,
    )

    # Build verified facts snapshot
    facts_list = []

    # Address facts
    facts_list.append(VerifiedFact(
        category="Address",
        fact="Full Address",
        value=export.property_facts.address.full_address,
        status=FactVerificationStatus.VERIFIED if export.property_facts.address.verified else FactVerificationStatus.UNVERIFIED,
    ))
    facts_list.append(VerifiedFact(
        category="Address",
        fact="Postcode",
        value=export.property_facts.address.postcode,
        status=FactVerificationStatus.VERIFIED if export.property_facts.address.verified else FactVerificationStatus.UNVERIFIED,
    ))

    # Physical facts
    facts_list.append(VerifiedFact(
        category="Physical",
        fact="Property Type",
        value=export.property_facts.physical.property_type.value,
        status=FactVerificationStatus.VERIFIED,  # Always from verified export
    ))

    if export.property_facts.physical.floor_area_sqm is not None:
        facts_list.append(VerifiedFact(
            category="Physical",
            fact="Floor Area",
            value=f"{export.property_facts.physical.floor_area_sqm} sqm",
            status=FactVerificationStatus.VERIFIED,
        ))
    else:
        facts_list.append(VerifiedFact(
            category="Physical",
            fact="Floor Area",
            value="Not available",
            status=FactVerificationStatus.NOT_AVAILABLE,
        ))

    if export.property_facts.physical.bedrooms is not None:
        facts_list.append(VerifiedFact(
            category="Physical",
            fact="Bedrooms",
            value=str(export.property_facts.physical.bedrooms),
            status=FactVerificationStatus.VERIFIED,
        ))

    if export.property_facts.physical.bathrooms is not None:
        facts_list.append(VerifiedFact(
            category="Physical",
            fact="Bathrooms",
            value=str(export.property_facts.physical.bathrooms),
            status=FactVerificationStatus.VERIFIED,
        ))

    # Tenure facts
    facts_list.append(VerifiedFact(
        category="Tenure",
        fact="Tenure Type",
        value=export.property_facts.tenure.tenure_type.value,
        status=FactVerificationStatus.VERIFIED,
    ))

    if export.property_facts.tenure.lease_years_remaining is not None:
        facts_list.append(VerifiedFact(
            category="Tenure",
            fact="Lease Years Remaining",
            value=str(export.property_facts.tenure.lease_years_remaining),
            status=FactVerificationStatus.VERIFIED,
        ))

    # Financial facts
    facts_list.append(VerifiedFact(
        category="Financial",
        fact="Guide Price",
        value=f"£{export.property_facts.financial.guide_price:,}",
        status=FactVerificationStatus.VERIFIED,  # Guide price must be verified to pass export
    ))
    facts_list.append(VerifiedFact(
        category="Financial",
        fact="Sale Route",
        value=export.property_facts.financial.sale_route.value,
        status=FactVerificationStatus.VERIFIED,
    ))

    # Count verified/unverified
    verified_count = sum(1 for f in facts_list if f.status == FactVerificationStatus.VERIFIED)
    unverified_count = sum(1 for f in facts_list if f.status == FactVerificationStatus.UNVERIFIED)

    verified_facts = VerifiedFactsSnapshot(
        facts=tuple(facts_list),
        trust_level=export.verification_summary.trust_level,
        verified_count=verified_count,
        unverified_count=unverified_count,
    )

    # Build valuation evidence
    valuation_evidence = ValuationEvidence(
        comp_count=comp_count,
        radius_miles=comp_radius_miles,
        date_range_months=comp_date_range_months,
        median_price=estimated_market_value,
        confidence_level=confidence_level,
    )

    # Build value creation section (empty if no verified planning)
    value_creation = ValueCreationSection(
        scenarios=(),
        has_verified_planning=planning_verified,
    )

    # Build risks & unknowns (MANDATORY - never empty)
    unverified_fact_names = [f.fact for f in facts_list if f.status == FactVerificationStatus.UNVERIFIED]
    not_available_fact_names = [f.fact for f in facts_list if f.status == FactVerificationStatus.NOT_AVAILABLE]
    all_unknown_facts = tuple(unverified_fact_names + not_available_fact_names)

    # Always include these standard risks
    planning_uncertainty = "Planning permission is not guaranteed. All planning-related assessments are indicative only."
    market_sensitivity = "Property values are subject to market conditions and may decrease as well as increase."

    additional_risks = []
    if confidence_level == ConfidenceLevel.LOW:
        additional_risks.append("Limited comparable sales data available. Valuation confidence is low.")
    if export.verification_summary.trust_level == TrustLevel.LOW:
        additional_risks.append("Less than 70% of facts are verified. Additional due diligence strongly recommended.")

    risks_and_unknowns = RisksAndUnknowns(
        unverified_facts=all_unknown_facts if all_unknown_facts else ("All primary facts verified",),
        planning_uncertainty=planning_uncertainty,
        market_sensitivity=market_sensitivity,
        additional_risks=tuple(additional_risks),
    )

    # Build next steps (non-advisory)
    next_steps_items = [
        "Further diligence recommended",
        "Professional survey recommended",
        "Legal review of title recommended",
    ]
    if export.property_facts.tenure.tenure_type.value == "leasehold":
        next_steps_items.append("Lease review required for leasehold properties")
    if confidence_level != ConfidenceLevel.HIGH:
        next_steps_items.append("Independent valuation recommended")

    next_steps = NextSteps(items=tuple(next_steps_items))

    # Build integrity & provenance
    integrity_provenance = IntegrityProvenance(
        logbook_hash=export.export_metadata.logbook_hash,
        chain_valid=export.export_metadata.chain_valid,
        logbook_version=export.export_metadata.logbook_version,
        title_register_hash=export.documents.title_register.hash if export.documents.title_register else None,
        epc_hash=export.documents.epc.hash if export.documents.epc else None,
        evaluation_timestamp=now.isoformat(),
        export_version=export.export_version,
    )

    # Create final memorandum
    memorandum = BuyerMemorandum(
        generated_at=now.isoformat(),
        source_export_version=export.export_version,
        source_property_id=export.property_id,
        cover_page=cover_page,
        executive_summary=executive_summary,
        verified_facts=verified_facts,
        valuation_evidence=valuation_evidence,
        value_creation=value_creation,
        risks_and_unknowns=risks_and_unknowns,
        next_steps=next_steps,
        integrity_provenance=integrity_provenance,
    )

    # Validate before returning
    is_valid, errors = memorandum.validate()
    if not is_valid:
        raise BuyerMemorandumValidationError(errors)

    return memorandum
