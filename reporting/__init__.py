"""
Reporting module for Axis Deal Engine.

Generates professional Capital Opportunity Memorandum PDFs
from mandate and deal analysis data.

Usage:
    from reporting import generate_report
    from reporting.schemas import create_sample_mandate

    mandate = create_sample_mandate()
    filepath = generate_report(mandate)

Buyer PDF (verification-aware):
    from reporting import BuyerPDFGenerator
    from reporting.buyer_schemas import create_buyer_memorandum_from_export

    generator = BuyerPDFGenerator()
    result = generator.generate_from_export(export, classification, emv, bmv, confidence)
"""

from .pdf_generator import ReportGenerator, generate_report
from .schemas import (
    Mandate,
    MandateParameters,
    OpportunityMemo,
    ScoreBreakdown,
    PlanningContext,
    UpliftScenario,
    ConvictionRating,
    PriorityLevel,
    create_sample_mandate,
)

# Buyer PDF exports (verification-aware)
from .buyer_schemas import (
    SCHEMA_VERSION as BUYER_SCHEMA_VERSION,
    BuyerMemorandum,
    BuyerMemorandumValidationError,
    ConfidenceLevel,
    CoverPage,
    DealClassification,
    ExecutiveSummary,
    FactVerificationStatus,
    IntegrityProvenance,
    LegalFooter,
    NextSteps,
    RisksAndUnknowns,
    ScenarioType,
    ValueCreationScenario,
    ValueCreationSection,
    ValuationEvidence,
    VerifiedFact,
    VerifiedFactsSnapshot,
    create_buyer_memorandum_from_export,
)
from .buyer_pdf_generator import (
    BuyerPDFGenerator,
    BuyerReportLowConfidenceWarning,
    BuyerReportResult,
    BuyerReportSuccess,
    BuyerReportValidationError,
)

__all__ = [
    # Generator (existing mandate-based)
    "ReportGenerator",
    "generate_report",
    # Schemas (existing mandate-based)
    "Mandate",
    "MandateParameters",
    "OpportunityMemo",
    "ScoreBreakdown",
    "PlanningContext",
    "UpliftScenario",
    "ConvictionRating",
    "PriorityLevel",
    "create_sample_mandate",
    # Buyer PDF Generator (verification-aware)
    "BuyerPDFGenerator",
    "BuyerReportSuccess",
    "BuyerReportValidationError",
    "BuyerReportLowConfidenceWarning",
    "BuyerReportResult",
    # Buyer Schemas
    "BUYER_SCHEMA_VERSION",
    "BuyerMemorandum",
    "BuyerMemorandumValidationError",
    "ConfidenceLevel",
    "DealClassification",
    "FactVerificationStatus",
    "ScenarioType",
    "CoverPage",
    "ExecutiveSummary",
    "VerifiedFact",
    "VerifiedFactsSnapshot",
    "ValuationEvidence",
    "ValueCreationScenario",
    "ValueCreationSection",
    "RisksAndUnknowns",
    "NextSteps",
    "IntegrityProvenance",
    "LegalFooter",
    "create_buyer_memorandum_from_export",
]
