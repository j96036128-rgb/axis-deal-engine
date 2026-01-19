"""
Automatic Buyer PDF Generation Service

This module provides the SINGLE SOURCE OF TRUTH for automatic PDF generation.
Buyer PDFs are generated ONLY when:
1. export_verified_contract() succeeds
2. check_deal_engine_readiness() returns can_evaluate=True

NO OTHER CODE PATH may generate Buyer PDFs.

Safety Rules (Non-Negotiable):
- No PDFs for LOW trust level
- No PDFs for disputed facts
- No PDFs for broken hash chain
- No agent data in PDFs
- PDFs must be reproducible and auditable
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, Optional, Union

from core.submission.export import (
    ExportBlockedError,
    TrustLevel,
    VerifiedPropertyExport,
    compute_export_hash,
    create_verified_property_export,
)
from core.submission.logbook import SubmissionLogbook
from core.submission.schema import SubmissionStatus
from core.submission.verification import (
    DealEngineGatingResult,
    PropertyVerificationSummary,
    check_deal_engine_readiness,
)

# Lazy import to avoid circular dependency
# BuyerPDFGenerator is imported at runtime


# =============================================================================
# Constants
# =============================================================================

# Output directory structure: reports/buyers/{property_id}/{export_hash}.pdf
BUYER_PDF_BASE_DIR: Final[Path] = Path("reports/buyers")

# Trust levels that BLOCK PDF generation (safety rule)
BLOCKED_TRUST_LEVELS: Final[frozenset[TrustLevel]] = frozenset({TrustLevel.LOW})


# =============================================================================
# Result Types
# =============================================================================


@dataclass(frozen=True)
class AutoPublishSuccess:
    """Returned when automatic PDF generation succeeds."""

    property_id: str
    pdf_path: Path
    export_hash: str
    trust_level: TrustLevel
    low_confidence_warning: Optional[str] = None


@dataclass(frozen=True)
class AutoPublishBlocked:
    """Returned when PDF generation is blocked by safety rules."""

    property_id: str
    reason: str
    blocking_rule: str  # Which safety rule blocked it


@dataclass(frozen=True)
class AutoPublishGatingFailed:
    """Returned when Deal Engine gating fails."""

    property_id: str
    reasons: list[str]
    gating_result: DealEngineGatingResult


@dataclass(frozen=True)
class AutoPublishExportFailed:
    """Returned when export_verified_contract() fails."""

    property_id: str
    reasons: list[str]


@dataclass(frozen=True)
class AutoPublishValidationError:
    """Returned when PDF validation fails."""

    property_id: str
    errors: list[str]


AutoPublishResult = Union[
    AutoPublishSuccess,
    AutoPublishBlocked,
    AutoPublishGatingFailed,
    AutoPublishExportFailed,
    AutoPublishValidationError,
]


# =============================================================================
# Core Service
# =============================================================================


class AutoPublishService:
    """
    Automatic Buyer PDF generation service.

    This is the SINGLE SOURCE OF TRUTH for Buyer PDF generation.
    PDFs are generated ONLY through this service.

    Usage:
        service = AutoPublishService()
        result = service.try_publish(logbook, verification_summary)

        if isinstance(result, AutoPublishSuccess):
            # PDF generated at result.pdf_path
            # Update submission status to EVALUATED_AND_PUBLISHED
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize the auto-publish service.

        Args:
            output_dir: Override default output directory (for testing)
        """
        self._output_dir = output_dir or BUYER_PDF_BASE_DIR

    def try_publish(
        self,
        logbook: SubmissionLogbook,
        verification_summary: PropertyVerificationSummary,
        deal_classification: str = "moderate",
        estimated_market_value: int = 0,
        bmv_percent: float = 0.0,
        confidence_level: str = "medium",
        comp_count: int = 0,
        comp_radius_miles: float = 0.0,
        comp_date_range_months: int = 0,
    ) -> AutoPublishResult:
        """
        Attempt to automatically generate a Buyer PDF.

        This method enforces ALL safety rules and gating requirements.
        It is the ONLY entry point for Buyer PDF generation.

        Args:
            logbook: The property submission logbook
            verification_summary: Verification status for all facts
            deal_classification: Deal Engine classification (strong/moderate/weak)
            estimated_market_value: Comps-based EMV
            bmv_percent: Below market value percentage
            confidence_level: Valuation confidence (high/medium/low)
            comp_count: Number of comps used
            comp_radius_miles: Comp search radius
            comp_date_range_months: Comp date range

        Returns:
            AutoPublishSuccess if PDF generated
            AutoPublishBlocked if safety rules block generation
            AutoPublishGatingFailed if Deal Engine gating fails
            AutoPublishExportFailed if export_verified_contract() fails
            AutoPublishValidationError if PDF validation fails
        """
        property_id = logbook.property_id

        # =====================================================================
        # STEP 1: Check Deal Engine Gating (MANDATORY)
        # =====================================================================

        chain_integrity = logbook.verify_chain_integrity()
        current_submission = logbook.current_submission

        if current_submission is None:
            return AutoPublishGatingFailed(
                property_id=property_id,
                reasons=["No submission found in logbook"],
                gating_result=DealEngineGatingResult.blocked("No submission"),
            )

        gating_result = check_deal_engine_readiness(
            chain_integrity=chain_integrity,
            verification_summary=verification_summary,
            submission_complete=current_submission.is_complete,
            require_full_verification=False,
        )

        if not gating_result.can_evaluate:
            return AutoPublishGatingFailed(
                property_id=property_id,
                reasons=gating_result.reasons,
                gating_result=gating_result,
            )

        # =====================================================================
        # STEP 2: Try export_verified_contract() (MANDATORY)
        # =====================================================================

        try:
            export = logbook.export_verified_contract(verification_summary)
        except ExportBlockedError as e:
            return AutoPublishExportFailed(
                property_id=property_id,
                reasons=e.reasons,
            )

        # =====================================================================
        # STEP 3: Check Safety Rules (NON-NEGOTIABLE)
        # =====================================================================

        # Safety Rule: No PDFs for LOW trust level
        if export.verification_summary.trust_level in BLOCKED_TRUST_LEVELS:
            return AutoPublishBlocked(
                property_id=property_id,
                reason=f"Trust level {export.verification_summary.trust_level.value} is below threshold",
                blocking_rule="LOW_TRUST_LEVEL",
            )

        # Safety Rule: No PDFs for disputed facts (should be caught by gating, but double-check)
        if export.verification_summary.disputed_fact_count > 0:
            return AutoPublishBlocked(
                property_id=property_id,
                reason=f"Submission has {export.verification_summary.disputed_fact_count} disputed facts",
                blocking_rule="DISPUTED_FACTS",
            )

        # Safety Rule: No PDFs for broken hash chain (should be caught by gating, but double-check)
        if not export.export_metadata.chain_valid:
            return AutoPublishBlocked(
                property_id=property_id,
                reason="Hash chain is invalid",
                blocking_rule="BROKEN_HASH_CHAIN",
            )

        # =====================================================================
        # STEP 4: Generate PDF
        # =====================================================================

        return self._generate_pdf(
            export=export,
            deal_classification=deal_classification,
            estimated_market_value=estimated_market_value,
            bmv_percent=bmv_percent,
            confidence_level=confidence_level,
            comp_count=comp_count,
            comp_radius_miles=comp_radius_miles,
            comp_date_range_months=comp_date_range_months,
        )

    def _generate_pdf(
        self,
        export: VerifiedPropertyExport,
        deal_classification: str,
        estimated_market_value: int,
        bmv_percent: float,
        confidence_level: str,
        comp_count: int,
        comp_radius_miles: float,
        comp_date_range_months: int,
    ) -> AutoPublishResult:
        """
        Generate the Buyer PDF from a verified export.

        Internal method - all safety checks have passed.
        """
        # Lazy import to avoid circular dependency
        from reporting.buyer_pdf_generator import (
            BuyerPDFGenerator,
            BuyerReportLowConfidenceWarning,
            BuyerReportSuccess,
            BuyerReportValidationError,
        )
        from reporting.buyer_schemas import ConfidenceLevel, DealClassification

        property_id = export.property_id

        # Compute deterministic export hash for filename
        export_hash = compute_export_hash(export)

        # Determine output path: reports/buyers/{property_id}/{export_hash}.pdf
        property_dir = self._output_dir / property_id
        property_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = property_dir / f"{export_hash}.pdf"

        # If file already exists with same hash, return existing path (deterministic)
        if pdf_path.exists():
            return AutoPublishSuccess(
                property_id=property_id,
                pdf_path=pdf_path,
                export_hash=export_hash,
                trust_level=export.verification_summary.trust_level,
                low_confidence_warning=None,
            )

        # Map string classifications to enums
        classification_map = {
            "strong": DealClassification.STRONG,
            "moderate": DealClassification.MODERATE,
            "weak": DealClassification.WEAK,
            "avoid": DealClassification.AVOID,
        }
        confidence_map = {
            "high": ConfidenceLevel.HIGH,
            "medium": ConfidenceLevel.MEDIUM,
            "low": ConfidenceLevel.LOW,
        }

        deal_class = classification_map.get(deal_classification.lower(), DealClassification.MODERATE)
        confidence = confidence_map.get(confidence_level.lower(), ConfidenceLevel.MEDIUM)

        # Create generator with custom output directory
        generator = BuyerPDFGenerator()
        # Override the output directory temporarily
        original_output_dir = generator.OUTPUT_DIR
        generator.OUTPUT_DIR = property_dir

        try:
            result = generator.generate_from_export(
                export=export,
                deal_classification=deal_class,
                estimated_market_value=estimated_market_value or export.property_facts.financial.guide_price,
                bmv_percent=bmv_percent,
                confidence_level=confidence,
                comp_count=comp_count,
                comp_radius_miles=comp_radius_miles,
                comp_date_range_months=comp_date_range_months,
            )
        finally:
            generator.OUTPUT_DIR = original_output_dir

        if isinstance(result, BuyerReportValidationError):
            return AutoPublishValidationError(
                property_id=property_id,
                errors=result.errors,
            )

        # Get the generated path
        generated_path = result.path

        # Rename to hash-based filename for determinism
        if generated_path.exists() and generated_path != pdf_path:
            generated_path.rename(pdf_path)

        low_confidence_warning = None
        if isinstance(result, BuyerReportLowConfidenceWarning):
            low_confidence_warning = result.warning

        return AutoPublishSuccess(
            property_id=property_id,
            pdf_path=pdf_path,
            export_hash=export_hash,
            trust_level=export.verification_summary.trust_level,
            low_confidence_warning=low_confidence_warning,
        )

    def get_pdf_path(self, property_id: str, export_hash: str) -> Path:
        """
        Get the deterministic PDF path for a property/export combination.

        Args:
            property_id: The property ID
            export_hash: The export hash

        Returns:
            Path where the PDF would be stored
        """
        return self._output_dir / property_id / f"{export_hash}.pdf"

    def pdf_exists(self, property_id: str, export_hash: str) -> bool:
        """
        Check if a PDF already exists for this property/export combination.

        Args:
            property_id: The property ID
            export_hash: The export hash

        Returns:
            True if PDF exists, False otherwise
        """
        return self.get_pdf_path(property_id, export_hash).exists()


# =============================================================================
# Repository Integration
# =============================================================================


@dataclass
class PublishRecord:
    """
    Record of a successful PDF publication.

    Stored in the repository alongside the submission.
    """

    property_id: str
    pdf_path: str
    export_hash: str
    trust_level: str
    published_at: str  # ISO-8601
    low_confidence_warning: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "property_id": self.property_id,
            "pdf_path": self.pdf_path,
            "export_hash": self.export_hash,
            "trust_level": self.trust_level,
            "published_at": self.published_at,
            "low_confidence_warning": self.low_confidence_warning,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PublishRecord":
        return cls(
            property_id=data["property_id"],
            pdf_path=data["pdf_path"],
            export_hash=data["export_hash"],
            trust_level=data["trust_level"],
            published_at=data["published_at"],
            low_confidence_warning=data.get("low_confidence_warning"),
        )

    @classmethod
    def from_success(cls, result: AutoPublishSuccess) -> "PublishRecord":
        """Create a publish record from a successful result."""
        return cls(
            property_id=result.property_id,
            pdf_path=str(result.pdf_path),
            export_hash=result.export_hash,
            trust_level=result.trust_level.value,
            published_at=datetime.utcnow().isoformat(),
            low_confidence_warning=result.low_confidence_warning,
        )


# =============================================================================
# Convenience Function
# =============================================================================


def try_auto_publish(
    logbook: SubmissionLogbook,
    verification_summary: PropertyVerificationSummary,
    deal_classification: str = "moderate",
    estimated_market_value: int = 0,
    bmv_percent: float = 0.0,
    confidence_level: str = "medium",
    comp_count: int = 0,
    comp_radius_miles: float = 0.0,
    comp_date_range_months: int = 0,
) -> AutoPublishResult:
    """
    Convenience function for automatic PDF generation.

    This is the SINGLE entry point for Buyer PDF generation.
    """
    service = AutoPublishService()
    return service.try_publish(
        logbook=logbook,
        verification_summary=verification_summary,
        deal_classification=deal_classification,
        estimated_market_value=estimated_market_value,
        bmv_percent=bmv_percent,
        confidence_level=confidence_level,
        comp_count=comp_count,
        comp_radius_miles=comp_radius_miles,
        comp_date_range_months=comp_date_range_months,
    )
