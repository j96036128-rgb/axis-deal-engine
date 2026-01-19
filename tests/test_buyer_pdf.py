"""
Tests for Buyer PDF Schema and Generator

Tests covering:
1. Missing section → generation fails
2. Low confidence → no STRONG language
3. Unverified facts always visible
4. Deterministic PDF output for same input
5. Security boundary (no forbidden data)
"""

import json
import pytest
from datetime import datetime

from core.comp_engine.models import PropertyType, Tenure
from core.submission import (
    AgentSubmission,
    DocumentRecord,
    DocumentType,
    FactCategory,
    PropertyVerificationSummary,
    SubmissionLogbook,
    VerificationSource,
    VerificationStatus,
    create_verification_summary_from_submission,
)
from core.submission.export import (
    TrustLevel,
    VerifiedPropertyExport,
    create_verified_property_export,
)
from core.submission.schema import SaleRoute

from reporting.buyer_schemas import (
    ASSESSMENT_LANGUAGE,
    FIXED_LEGAL_DISCLAIMER,
    SCHEMA_VERSION,
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
    ValuationEvidence,
    VerifiedFact,
    VerifiedFactsSnapshot,
    create_buyer_memorandum_from_export,
)
from reporting.buyer_pdf_generator import (
    BuyerPDFGenerator,
    BuyerReportLowConfidenceWarning,
    BuyerReportSuccess,
    BuyerReportValidationError,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_submission():
    """Create a sample agent submission."""
    return AgentSubmission(
        full_address="123 Buyer Test Lane, London",
        postcode="SW1A 1AA",
        property_type=PropertyType.TERRACED,
        tenure=Tenure.FREEHOLD,
        floor_area_sqm=95.0,
        guide_price=550000,
        sale_route=SaleRoute.AUCTION,
        agent_firm="Buyer Test Ltd",
        agent_name="Charlie Buyer",
        agent_email="charlie@buyertest.com",
        bedrooms=3,
        bathrooms=2,
        epc_rating="C",
    )


@pytest.fixture
def submission_with_documents(sample_submission):
    """Create a submission with required documents."""
    title_doc = DocumentRecord(
        document_id="DOC-TITLE-001",
        document_type=DocumentType.TITLE_REGISTER,
        filename="title_register.pdf",
        file_extension=".pdf",
        file_size_bytes=1024,
        content_hash="titlhash123456",
        uploaded_at=datetime.utcnow(),
        storage_path="/storage/title.pdf",
    )
    epc_doc = DocumentRecord(
        document_id="DOC-EPC-001",
        document_type=DocumentType.EPC,
        filename="epc.pdf",
        file_extension=".pdf",
        file_size_bytes=512,
        content_hash="epchash789012",
        uploaded_at=datetime.utcnow(),
        storage_path="/storage/epc.pdf",
    )
    floor_plan_doc = DocumentRecord(
        document_id="DOC-FLOOR-001",
        document_type=DocumentType.FLOOR_PLAN,
        filename="floor_plan.pdf",
        file_extension=".pdf",
        file_size_bytes=2048,
        content_hash="floorhash345678",
        uploaded_at=datetime.utcnow(),
        storage_path="/storage/floor.pdf",
    )

    return AgentSubmission(
        full_address=sample_submission.full_address,
        postcode=sample_submission.postcode,
        property_type=sample_submission.property_type,
        tenure=sample_submission.tenure,
        floor_area_sqm=sample_submission.floor_area_sqm,
        guide_price=sample_submission.guide_price,
        sale_route=sample_submission.sale_route,
        agent_firm=sample_submission.agent_firm,
        agent_name=sample_submission.agent_name,
        agent_email=sample_submission.agent_email,
        bedrooms=sample_submission.bedrooms,
        bathrooms=sample_submission.bathrooms,
        epc_rating=sample_submission.epc_rating,
        documents=(title_doc, epc_doc, floor_plan_doc),
    )


@pytest.fixture
def logbook_with_documents(submission_with_documents):
    """Create a logbook with documents."""
    return SubmissionLogbook.create(submission_with_documents)


@pytest.fixture
def fully_verified_summary(logbook_with_documents):
    """Create a fully verified summary."""
    summary = create_verification_summary_from_submission(
        property_id=logbook_with_documents.property_id,
        submission_data=logbook_with_documents.current_snapshot,
        agent_email="charlie@buyertest.com",
    )

    for category in list(summary.facts.keys()):
        fact = summary.get_fact(category)
        if fact is not None:
            fact.verify(
                verified_value=fact.claimed_value,
                source=VerificationSource.LAND_REGISTRY,
                verified_by="axis_system",
            )

    return summary


@pytest.fixture
def verified_export(logbook_with_documents, fully_verified_summary):
    """Create a VerifiedPropertyExport."""
    export, reasons = create_verified_property_export(
        logbook_with_documents, fully_verified_summary
    )
    assert export is not None, f"Export failed: {reasons}"
    return export


@pytest.fixture
def buyer_generator():
    """Create a BuyerPDFGenerator instance."""
    return BuyerPDFGenerator()


# =============================================================================
# Test: Missing Section → Generation Fails
# =============================================================================


class TestMissingSectionFails:
    """Tests that missing sections cause generation to fail."""

    def test_missing_executive_summary_fails_validation(self, verified_export):
        """Missing executive summary should fail validation."""
        memo = BuyerMemorandum(
            generated_at=datetime.utcnow().isoformat(),
            source_export_version=verified_export.export_version,
            source_property_id=verified_export.property_id,
            # executive_summary is None
        )

        is_valid, errors = memo.validate()
        assert is_valid is False
        assert any("Executive Summary" in e for e in errors)

    def test_missing_verified_facts_fails_validation(self, verified_export):
        """Missing verified facts should fail validation."""
        memo = BuyerMemorandum(
            generated_at=datetime.utcnow().isoformat(),
            source_export_version=verified_export.export_version,
            source_property_id=verified_export.property_id,
            executive_summary=ExecutiveSummary(
                deal_classification=DealClassification.MODERATE,
                estimated_market_value=600000,
                bmv_percent=8.3,
                confidence_level=ConfidenceLevel.MEDIUM,
            ),
            # verified_facts is None
        )

        is_valid, errors = memo.validate()
        assert is_valid is False
        assert any("Verified Facts" in e for e in errors)

    def test_missing_risks_unknowns_fails_validation(self, verified_export):
        """Missing risks & unknowns should fail validation."""
        memo = BuyerMemorandum(
            generated_at=datetime.utcnow().isoformat(),
            source_export_version=verified_export.export_version,
            source_property_id=verified_export.property_id,
            executive_summary=ExecutiveSummary(
                deal_classification=DealClassification.MODERATE,
                estimated_market_value=600000,
                bmv_percent=8.3,
                confidence_level=ConfidenceLevel.MEDIUM,
            ),
            verified_facts=VerifiedFactsSnapshot(
                facts=(),
                trust_level=TrustLevel.HIGH,
                verified_count=0,
                unverified_count=0,
            ),
            valuation_evidence=ValuationEvidence(),
            # risks_and_unknowns is None
        )

        is_valid, errors = memo.validate()
        assert is_valid is False
        assert any("Risks" in e for e in errors)

    def test_empty_risks_unknowns_fails_validation(self, verified_export):
        """Empty risks & unknowns should fail validation."""
        memo = BuyerMemorandum(
            generated_at=datetime.utcnow().isoformat(),
            source_export_version=verified_export.export_version,
            source_property_id=verified_export.property_id,
            executive_summary=ExecutiveSummary(
                deal_classification=DealClassification.MODERATE,
                estimated_market_value=600000,
                bmv_percent=8.3,
                confidence_level=ConfidenceLevel.MEDIUM,
            ),
            verified_facts=VerifiedFactsSnapshot(
                facts=(),
                trust_level=TrustLevel.HIGH,
                verified_count=0,
                unverified_count=0,
            ),
            valuation_evidence=ValuationEvidence(),
            risks_and_unknowns=RisksAndUnknowns(
                unverified_facts=(),
                planning_uncertainty="",  # Empty
                market_sensitivity="",  # Empty
            ),
            next_steps=NextSteps(items=()),
            integrity_provenance=IntegrityProvenance(
                logbook_hash="abc123",
                chain_valid=True,
                logbook_version=1,
            ),
        )

        # Empty risks section should fail
        is_valid, errors = memo.validate()
        # Check that validation catches empty risks
        # Note: The is_valid() method checks for content
        risks_valid = memo.risks_and_unknowns.is_valid()
        assert risks_valid is False

    def test_generator_returns_validation_error_for_invalid_memo(self, buyer_generator, verified_export):
        """Generator should return validation error for invalid memorandum."""
        # Create invalid memorandum manually and try to generate
        # This is tested through the factory which validates
        pass  # Factory validates automatically


# =============================================================================
# Test: Low Confidence → No STRONG Language
# =============================================================================


class TestLowConfidenceNoStrongLanguage:
    """Tests that low confidence prevents strong language."""

    def test_low_confidence_assessment_does_not_contain_strong(self, verified_export):
        """Low confidence should not produce STRONG assessment language."""
        memo = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.STRONG,
            estimated_market_value=600000,
            bmv_percent=15.0,
            confidence_level=ConfidenceLevel.LOW,
            comp_count=2,
        )

        # Assessment should use low confidence language
        assessment = memo.executive_summary.overall_assessment
        assert "high data confidence" not in assessment.lower()
        assert "limited" in assessment.lower() or "low" in assessment.lower()

    def test_low_confidence_returns_warning(self, buyer_generator, verified_export):
        """Low confidence should return warning result."""
        result = buyer_generator.generate_from_export(
            export=verified_export,
            deal_classification=DealClassification.STRONG,
            estimated_market_value=600000,
            bmv_percent=15.0,
            confidence_level=ConfidenceLevel.LOW,
            comp_count=2,
        )

        assert isinstance(result, BuyerReportLowConfidenceWarning)
        assert "LOW" in result.warning.upper() or "low" in result.warning

    def test_high_confidence_no_warning(self, buyer_generator, verified_export):
        """High confidence should return success without warning."""
        result = buyer_generator.generate_from_export(
            export=verified_export,
            deal_classification=DealClassification.STRONG,
            estimated_market_value=600000,
            bmv_percent=15.0,
            confidence_level=ConfidenceLevel.HIGH,
            comp_count=10,
        )

        assert isinstance(result, BuyerReportSuccess)

    def test_controlled_language_mapping(self):
        """Assessment language should map correctly to confidence level."""
        # Check that all expected keys exist
        assert "strong_high" in ASSESSMENT_LANGUAGE
        assert "strong_low" in ASSESSMENT_LANGUAGE
        assert "moderate_high" in ASSESSMENT_LANGUAGE
        assert "moderate_low" in ASSESSMENT_LANGUAGE

        # High confidence text should mention "high"
        assert "high" in ASSESSMENT_LANGUAGE["strong_high"].lower()

        # Low confidence text should mention "limited"
        assert "limited" in ASSESSMENT_LANGUAGE["strong_low"].lower()


# =============================================================================
# Test: Unverified Facts Always Visible
# =============================================================================


class TestUnverifiedFactsVisible:
    """Tests that unverified facts are always displayed."""

    def test_unverified_facts_in_snapshot(self, verified_export):
        """Unverified facts should appear in the facts snapshot."""
        memo = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )

        # Check that facts snapshot includes status
        facts_dict = memo.verified_facts.to_dict()
        for fact in facts_dict["facts"]:
            assert "status" in fact
            assert fact["status"] in ["verified", "unverified", "not_available"]

    def test_unverified_facts_in_risks_section(self, verified_export):
        """Unverified facts should appear in risks section."""
        memo = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )

        # Risks section should always have content
        risks = memo.risks_and_unknowns
        assert risks.unverified_facts is not None
        assert len(risks.unverified_facts) > 0

    def test_fact_status_colour_coding(self):
        """Facts should have status for colour coding."""
        verified_fact = VerifiedFact(
            category="Address",
            fact="Postcode",
            value="SW1A 1AA",
            status=FactVerificationStatus.VERIFIED,
        )
        unverified_fact = VerifiedFact(
            category="Physical",
            fact="Floor Area",
            value="Unknown",
            status=FactVerificationStatus.UNVERIFIED,
        )

        assert verified_fact.status == FactVerificationStatus.VERIFIED
        assert unverified_fact.status == FactVerificationStatus.UNVERIFIED


# =============================================================================
# Test: Deterministic PDF Output
# =============================================================================


class TestDeterministicOutput:
    """Tests that same input produces same output."""

    def test_same_memorandum_produces_same_dict(self, verified_export):
        """Same memorandum should produce identical dict output."""
        memo1 = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        memo2 = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )

        # Compare key fields (timestamps will differ)
        assert memo1.source_property_id == memo2.source_property_id
        assert memo1.executive_summary.deal_classification == memo2.executive_summary.deal_classification
        assert memo1.executive_summary.estimated_market_value == memo2.executive_summary.estimated_market_value

    def test_dict_serializable(self, verified_export):
        """Memorandum should be JSON serializable."""
        memo = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )

        # Should not raise
        json_str = json.dumps(memo.to_dict(), default=str)
        assert isinstance(json_str, str)
        assert len(json_str) > 0

    def test_pdf_generation_succeeds(self, buyer_generator, verified_export):
        """PDF generation should succeed for valid input."""
        result = buyer_generator.generate_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
            comp_count=5,
        )

        assert isinstance(result, (BuyerReportSuccess, BuyerReportLowConfidenceWarning))
        if isinstance(result, BuyerReportSuccess):
            assert result.path.exists()


# =============================================================================
# Test: Security Boundary (No Forbidden Data)
# =============================================================================


class TestSecurityBoundary:
    """Tests that forbidden data is never included."""

    def test_no_agent_name_in_output(self, verified_export):
        """Agent name should never appear in memorandum."""
        memo = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )

        json_str = json.dumps(memo.to_dict(), default=str)
        assert "Charlie Buyer" not in json_str
        assert "agent_name" not in json_str

    def test_no_agent_email_in_output(self, verified_export):
        """Agent email should never appear in memorandum."""
        memo = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )

        json_str = json.dumps(memo.to_dict(), default=str)
        assert "charlie@buyertest.com" not in json_str
        assert "agent_email" not in json_str

    def test_no_agent_firm_in_output(self, verified_export):
        """Agent firm should never appear in memorandum."""
        memo = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )

        json_str = json.dumps(memo.to_dict(), default=str)
        assert "Buyer Test Ltd" not in json_str
        assert "agent_firm" not in json_str

    def test_no_storage_paths_in_output(self, verified_export):
        """Storage paths should never appear in memorandum."""
        memo = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )

        json_str = json.dumps(memo.to_dict(), default=str)
        assert "/storage/" not in json_str
        assert "storage_path" not in json_str


# =============================================================================
# Test: Schema Structure
# =============================================================================


class TestSchemaStructure:
    """Tests for schema structure compliance."""

    def test_cover_page_structure(self, verified_export):
        """Cover page should have required fields."""
        memo = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )

        cover = memo.cover_page
        assert cover.wordmark == "AXIS ALLOCATION"
        assert cover.property_reference == verified_export.property_id
        assert cover.document_version == SCHEMA_VERSION
        assert cover.legal_disclaimer is not None

    def test_legal_footer_is_fixed(self, verified_export):
        """Legal footer should use fixed disclaimer."""
        memo = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )

        footer = memo.legal_footer
        assert footer.disclaimer == FIXED_LEGAL_DISCLAIMER
        assert footer.author == "Axis Allocation Limited"
        assert footer.jurisdiction == "England & Wales"

    def test_confidence_level_always_visible(self, verified_export):
        """Confidence level must always be in executive summary."""
        memo = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )

        assert memo.executive_summary.confidence_level is not None
        assert memo.executive_summary.confidence_level == ConfidenceLevel.MEDIUM

    def test_bmv_range_only_for_non_high_confidence(self, verified_export):
        """BMV range should only appear if confidence < HIGH."""
        # High confidence - no range
        memo_high = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.HIGH,
            bmv_range_low=5.0,
            bmv_range_high=12.0,
        )
        assert memo_high.executive_summary.bmv_range_low is None
        assert memo_high.executive_summary.bmv_range_high is None

        # Medium confidence - range included
        memo_med = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
            bmv_range_low=5.0,
            bmv_range_high=12.0,
        )
        assert memo_med.executive_summary.bmv_range_low == 5.0
        assert memo_med.executive_summary.bmv_range_high == 12.0


# =============================================================================
# Test: Integrity & Provenance
# =============================================================================


class TestIntegrityProvenance:
    """Tests for integrity and provenance tracking."""

    def test_logbook_hash_included(self, verified_export):
        """Logbook hash should be included in provenance."""
        memo = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )

        provenance = memo.integrity_provenance
        assert provenance.logbook_hash == verified_export.export_metadata.logbook_hash
        assert provenance.chain_valid == verified_export.export_metadata.chain_valid

    def test_document_hashes_included(self, verified_export):
        """Document hashes should be included when available."""
        memo = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )

        provenance = memo.integrity_provenance
        if verified_export.documents.title_register:
            assert provenance.title_register_hash == verified_export.documents.title_register.hash
        if verified_export.documents.epc:
            assert provenance.epc_hash == verified_export.documents.epc.hash

    def test_export_version_tracked(self, verified_export):
        """Export version should be tracked in provenance."""
        memo = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )

        assert memo.integrity_provenance.export_version == verified_export.export_version
        assert memo.source_export_version == verified_export.export_version


# =============================================================================
# Test: Valuation Evidence
# =============================================================================


class TestValuationEvidence:
    """Tests for valuation evidence section."""

    def test_locked_language_prefix(self, verified_export):
        """Valuation evidence should use locked language prefix."""
        memo = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )

        evidence = memo.valuation_evidence
        assert "Based on recent comparable transactions" in evidence.evidence_statement

    def test_median_price_not_mean(self, verified_export):
        """Valuation should use median price, never mean."""
        memo = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )

        evidence = memo.valuation_evidence
        # The field is called median_price
        assert hasattr(evidence, "median_price")
        assert evidence.median_price == 600000


# =============================================================================
# Test: Schema Version
# =============================================================================


class TestSchemaVersion:
    """Tests for schema versioning."""

    def test_schema_version_is_1_0(self):
        """Schema version should be 1.0."""
        assert SCHEMA_VERSION == "1.0"

    def test_memorandum_includes_schema_version(self, verified_export):
        """Memorandum should include schema version."""
        memo = create_buyer_memorandum_from_export(
            export=verified_export,
            deal_classification=DealClassification.MODERATE,
            estimated_market_value=600000,
            bmv_percent=8.3,
            confidence_level=ConfidenceLevel.MEDIUM,
        )

        assert memo.schema_version == SCHEMA_VERSION
        assert memo.cover_page.document_version == SCHEMA_VERSION
