"""
Tests for Trust Primitives

Tests covering:
1. Hash chain integrity and determinism
2. Verification status tracking
3. Deal Engine gating logic
4. Verified fact extraction
"""

import pytest
from datetime import datetime
from copy import deepcopy

from core.submission import (
    AgentSubmission,
    SubmissionLogbook,
    SubmissionStatus,
    VersionAction,
    VerificationStatus,
    VerificationSource,
    FactCategory,
    FactVerificationState,
    PropertyVerificationSummary,
    create_verification_summary_from_submission,
    DealEngineGatingResult,
    check_deal_engine_readiness,
    extract_verified_submission_data,
    verify_hash_chain,
    compute_version_hash,
)
from core.comp_engine.models import PropertyType, Tenure
from core.submission.schema import SaleRoute


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_submission():
    """Create a sample submission for testing."""
    return AgentSubmission(
        full_address="123 Trust Test Lane, London",
        postcode="SW1A 1AA",
        property_type=PropertyType.TERRACED,
        tenure=Tenure.FREEHOLD,
        floor_area_sqm=95,
        guide_price=550000,
        sale_route=SaleRoute.AUCTION,
        agent_firm="Trust Test Ltd",
        agent_name="Alice Trust",
        agent_email="alice@trusttest.com",
        bedrooms=3,
        bathrooms=2,
        epc_rating="C",
    )


@pytest.fixture
def sample_logbook(sample_submission):
    """Create a sample logbook with initial version."""
    return SubmissionLogbook.create(sample_submission)


@pytest.fixture
def sample_verification_summary(sample_logbook):
    """Create a sample verification summary."""
    return create_verification_summary_from_submission(
        property_id=sample_logbook.property_id,
        submission_data=sample_logbook.current_snapshot,
        agent_email="alice@trusttest.com",
    )


# =============================================================================
# Hash Chain Tests
# =============================================================================


class TestHashChain:
    """Tests for hash chain integrity and determinism."""

    def test_initial_version_has_no_previous_hash(self, sample_logbook):
        """First version should have previous_version_hash = None."""
        v1 = sample_logbook.get_version(1)
        assert v1.previous_version_hash is None

    def test_initial_version_has_valid_hash(self, sample_logbook):
        """First version should have a valid SHA-256 hash."""
        v1 = sample_logbook.get_version(1)
        assert v1.version_hash is not None
        assert len(v1.version_hash) == 64  # SHA-256 hex length
        assert v1.verify_hash() is True

    def test_subsequent_versions_link_to_previous(self, sample_logbook):
        """Each subsequent version should reference the previous hash."""
        sample_logbook.update_status(SubmissionStatus.SUBMITTED, "axis_system")
        sample_logbook.update_status(SubmissionStatus.UNDER_REVIEW, "axis_system")

        v1 = sample_logbook.get_version(1)
        v2 = sample_logbook.get_version(2)
        v3 = sample_logbook.get_version(3)

        assert v2.previous_version_hash == v1.version_hash
        assert v3.previous_version_hash == v2.version_hash

    def test_chain_integrity_valid(self, sample_logbook):
        """A properly formed chain should pass integrity check."""
        sample_logbook.update_status(SubmissionStatus.SUBMITTED, "axis_system")
        sample_logbook.update_status(SubmissionStatus.EVALUATED, "deal_engine")

        integrity = sample_logbook.verify_chain_integrity()
        assert integrity["valid"] is True
        assert integrity["broken_at"] is None
        assert integrity["error"] is None
        assert integrity["version_count"] == 3

    def test_is_chain_valid_convenience_method(self, sample_logbook):
        """is_chain_valid() should return True for valid chain."""
        assert sample_logbook.is_chain_valid() is True

    def test_hash_determinism_same_inputs(self):
        """Same inputs should always produce the same hash."""
        ts = datetime(2026, 1, 17, 12, 0, 0)
        snapshot = {"address": "123 Test", "price": 500000}

        hash1 = compute_version_hash(
            property_id="PROP-TEST",
            version_number=1,
            timestamp=ts,
            action="initial_submission",
            action_by="test@test.com",
            action_note=None,
            submission_snapshot=snapshot,
            status="draft",
            previous_version_hash=None,
        )

        hash2 = compute_version_hash(
            property_id="PROP-TEST",
            version_number=1,
            timestamp=ts,
            action="initial_submission",
            action_by="test@test.com",
            action_note=None,
            submission_snapshot=snapshot,
            status="draft",
            previous_version_hash=None,
        )

        assert hash1 == hash2

    def test_hash_determinism_dict_order_independent(self):
        """Hash should be the same regardless of dict key order."""
        ts = datetime(2026, 1, 17, 12, 0, 0)

        snapshot1 = {"z": 1, "a": 2, "m": 3}
        snapshot2 = {"a": 2, "m": 3, "z": 1}

        hash1 = compute_version_hash(
            property_id="PROP-TEST",
            version_number=1,
            timestamp=ts,
            action="initial_submission",
            action_by="test@test.com",
            action_note=None,
            submission_snapshot=snapshot1,
            status="draft",
            previous_version_hash=None,
        )

        hash2 = compute_version_hash(
            property_id="PROP-TEST",
            version_number=1,
            timestamp=ts,
            action="initial_submission",
            action_by="test@test.com",
            action_note=None,
            submission_snapshot=snapshot2,
            status="draft",
            previous_version_hash=None,
        )

        assert hash1 == hash2

    def test_hash_changes_with_different_input(self):
        """Different inputs should produce different hashes."""
        ts = datetime(2026, 1, 17, 12, 0, 0)
        snapshot = {"address": "123 Test"}

        hash1 = compute_version_hash(
            property_id="PROP-TEST",
            version_number=1,
            timestamp=ts,
            action="initial_submission",
            action_by="test@test.com",
            action_note=None,
            submission_snapshot=snapshot,
            status="draft",
            previous_version_hash=None,
        )

        hash2 = compute_version_hash(
            property_id="PROP-TEST",
            version_number=1,
            timestamp=ts,
            action="initial_submission",
            action_by="test@test.com",
            action_note="Added note",  # Different
            submission_snapshot=snapshot,
            status="draft",
            previous_version_hash=None,
        )

        assert hash1 != hash2

    def test_serialization_preserves_hashes(self, sample_logbook):
        """Serializing and deserializing should preserve hashes."""
        sample_logbook.update_status(SubmissionStatus.SUBMITTED, "axis_system")

        data = sample_logbook.to_dict()
        restored = SubmissionLogbook.from_dict(data)

        assert restored.is_chain_valid()
        for i in range(sample_logbook.version_count):
            orig = sample_logbook.get_version(i + 1)
            rest = restored.get_version(i + 1)
            assert orig.version_hash == rest.version_hash
            assert orig.previous_version_hash == rest.previous_version_hash


# =============================================================================
# Verification Status Tests
# =============================================================================


class TestVerificationStatus:
    """Tests for verification status tracking."""

    def test_initial_facts_are_unverified(self, sample_verification_summary):
        """All facts should start as UNVERIFIED."""
        for state in sample_verification_summary.facts.values():
            assert state.current_status == VerificationStatus.UNVERIFIED

    def test_verify_fact(self, sample_verification_summary):
        """Verifying a fact should update its status."""
        address_state = sample_verification_summary.get_fact(FactCategory.ADDRESS)

        address_state.verify(
            verified_value="123 Trust Test Lane, London",
            source=VerificationSource.LAND_REGISTRY,
            verified_by="axis_system",
        )

        assert address_state.current_status == VerificationStatus.VERIFIED
        assert address_state.is_verified is True
        assert len(address_state.history) == 2  # Initial + verify

    def test_dispute_fact(self, sample_verification_summary):
        """Disputing a fact should mark it as DISPUTED."""
        floor_area_state = sample_verification_summary.get_fact(FactCategory.FLOOR_AREA)

        floor_area_state.dispute(
            disputed_value=85,  # Different from 95
            source=VerificationSource.EPC_REGISTER,
            verified_by="axis_system",
            verification_note="EPC shows 85 sqm",
        )

        assert floor_area_state.current_status == VerificationStatus.DISPUTED
        assert floor_area_state.is_disputed is True
        assert floor_area_state.value_mismatch is True

    def test_reject_fact(self, sample_verification_summary):
        """Rejecting a fact should mark it as REJECTED."""
        epc_state = sample_verification_summary.get_fact(FactCategory.EPC_RATING)

        epc_state.reject(
            verified_by="axis_system",
            verification_note="EPC document appears forged",
        )

        assert epc_state.current_status == VerificationStatus.REJECTED
        assert epc_state.is_usable_by_deal_engine is False

    def test_document_submitted_status(self, sample_verification_summary):
        """Submitting a document should update status to SUBMITTED."""
        tenure_state = sample_verification_summary.get_fact(FactCategory.TENURE)

        tenure_state.mark_document_submitted(
            document_id="DOC-123456",
            verified_by="alice@trusttest.com",
        )

        assert tenure_state.current_status == VerificationStatus.SUBMITTED

    def test_verification_history_is_append_only(self, sample_verification_summary):
        """Verification history should only grow, not shrink."""
        address_state = sample_verification_summary.get_fact(FactCategory.ADDRESS)
        initial_count = len(address_state.history)

        address_state.mark_document_submitted("DOC-111", "agent")
        assert len(address_state.history) == initial_count + 1

        address_state.verify("123 Trust Test Lane, London", VerificationSource.DOCUMENT, "axis")
        assert len(address_state.history) == initial_count + 2

    def test_verification_summary_statistics(self, sample_verification_summary):
        """Summary should correctly calculate statistics."""
        # Initial state
        assert sample_verification_summary.unverified_count == sample_verification_summary.total_facts
        assert sample_verification_summary.verified_count == 0

        # Verify some facts
        sample_verification_summary.get_fact(FactCategory.ADDRESS).verify(
            "123 Trust Test Lane, London", VerificationSource.LAND_REGISTRY, "axis"
        )
        sample_verification_summary.get_fact(FactCategory.TENURE).verify(
            "freehold", VerificationSource.LAND_REGISTRY, "axis"
        )

        assert sample_verification_summary.verified_count == 2
        assert sample_verification_summary.verification_percentage == pytest.approx(
            (2 / sample_verification_summary.total_facts) * 100, rel=0.01
        )


# =============================================================================
# Deal Engine Gating Tests
# =============================================================================


class TestDealEngineGating:
    """Tests for Deal Engine gating logic."""

    def test_gating_passes_with_valid_integrity_no_disputes(
        self, sample_logbook, sample_verification_summary
    ):
        """Gating should pass when integrity is valid and no disputes."""
        chain_integrity = sample_logbook.verify_chain_integrity()

        result = check_deal_engine_readiness(
            chain_integrity=chain_integrity,
            verification_summary=sample_verification_summary,
            submission_complete=True,
        )

        assert result.can_evaluate is True
        assert len(result.reasons) == 0
        assert result.integrity_valid is True

    def test_gating_fails_with_broken_chain(self, sample_verification_summary):
        """Gating should fail when hash chain is broken."""
        broken_chain = {"valid": False, "error": "Hash mismatch at version 2"}

        result = check_deal_engine_readiness(
            chain_integrity=broken_chain,
            verification_summary=sample_verification_summary,
            submission_complete=True,
        )

        assert result.can_evaluate is False
        assert "integrity failure" in result.reasons[0].lower()

    def test_gating_fails_with_disputes(
        self, sample_logbook, sample_verification_summary
    ):
        """Gating should fail when there are disputed facts."""
        # Create a dispute
        sample_verification_summary.get_fact(FactCategory.FLOOR_AREA).dispute(
            disputed_value=75,
            source=VerificationSource.EPC_REGISTER,
            verified_by="axis_system",
        )

        chain_integrity = sample_logbook.verify_chain_integrity()

        result = check_deal_engine_readiness(
            chain_integrity=chain_integrity,
            verification_summary=sample_verification_summary,
            submission_complete=True,
        )

        assert result.can_evaluate is False
        assert result.has_disputes is True
        assert any("disputed" in r.lower() for r in result.reasons)

    def test_gating_fails_with_rejections(
        self, sample_logbook, sample_verification_summary
    ):
        """Gating should fail when there are rejected facts."""
        # Create a rejection
        sample_verification_summary.get_fact(FactCategory.EPC_RATING).reject(
            verified_by="axis_system",
            verification_note="Invalid document",
        )

        chain_integrity = sample_logbook.verify_chain_integrity()

        result = check_deal_engine_readiness(
            chain_integrity=chain_integrity,
            verification_summary=sample_verification_summary,
            submission_complete=True,
        )

        assert result.can_evaluate is False
        assert result.has_rejections is True

    def test_gating_fails_with_incomplete_submission(
        self, sample_logbook, sample_verification_summary
    ):
        """Gating should fail when submission is incomplete."""
        chain_integrity = sample_logbook.verify_chain_integrity()

        result = check_deal_engine_readiness(
            chain_integrity=chain_integrity,
            verification_summary=sample_verification_summary,
            submission_complete=False,  # Incomplete
        )

        assert result.can_evaluate is False
        assert any("incomplete" in r.lower() for r in result.reasons)

    def test_gating_with_full_verification_required(
        self, sample_logbook, sample_verification_summary
    ):
        """Gating should fail when full verification is required but not met."""
        chain_integrity = sample_logbook.verify_chain_integrity()

        result = check_deal_engine_readiness(
            chain_integrity=chain_integrity,
            verification_summary=sample_verification_summary,
            submission_complete=True,
            require_full_verification=True,
        )

        assert result.can_evaluate is False
        assert any("not fully verified" in r.lower() for r in result.reasons)

    def test_gating_extracts_only_verified_facts(
        self, sample_logbook, sample_verification_summary
    ):
        """Gating result should only include verified facts."""
        # Verify some facts
        sample_verification_summary.get_fact(FactCategory.ADDRESS).verify(
            "123 Trust Test Lane, London", VerificationSource.LAND_REGISTRY, "axis"
        )
        sample_verification_summary.get_fact(FactCategory.TENURE).verify(
            "freehold", VerificationSource.LAND_REGISTRY, "axis"
        )

        chain_integrity = sample_logbook.verify_chain_integrity()

        result = check_deal_engine_readiness(
            chain_integrity=chain_integrity,
            verification_summary=sample_verification_summary,
            submission_complete=True,
        )

        assert "address" in result.verified_facts
        assert "tenure" in result.verified_facts
        assert "guide_price" not in result.verified_facts  # Not verified


# =============================================================================
# Verified Data Extraction Tests
# =============================================================================


class TestVerifiedDataExtraction:
    """Tests for extracting only verified data."""

    def test_unverified_facts_are_nulled(
        self, sample_logbook, sample_verification_summary
    ):
        """Unverified facts should be set to None."""
        verified_data = extract_verified_submission_data(
            submission_data=sample_logbook.current_snapshot,
            verification_summary=sample_verification_summary,
        )

        # All facts are unverified, so verifiable fields should be None
        assert verified_data["full_address"] is None
        assert verified_data["postcode"] is None
        assert verified_data["guide_price"] is None

    def test_verified_facts_are_preserved(
        self, sample_logbook, sample_verification_summary
    ):
        """Verified facts should retain their values."""
        # Verify some facts
        sample_verification_summary.get_fact(FactCategory.ADDRESS).verify(
            "123 Trust Test Lane, London", VerificationSource.LAND_REGISTRY, "axis"
        )
        sample_verification_summary.get_fact(FactCategory.FLOOR_AREA).verify(
            95, VerificationSource.EPC_REGISTER, "axis"
        )

        verified_data = extract_verified_submission_data(
            submission_data=sample_logbook.current_snapshot,
            verification_summary=sample_verification_summary,
        )

        assert verified_data["full_address"] == "123 Trust Test Lane, London"
        assert verified_data["floor_area_sqm"] == 95
        assert verified_data["guide_price"] is None  # Not verified

    def test_verified_value_overrides_claimed(
        self, sample_logbook, sample_verification_summary
    ):
        """If verified value differs from claimed, use verified."""
        # Verify with a corrected value
        sample_verification_summary.get_fact(FactCategory.FLOOR_AREA).verify(
            85,  # Different from claimed 95
            VerificationSource.EPC_REGISTER,
            "axis"
        )

        verified_data = extract_verified_submission_data(
            submission_data=sample_logbook.current_snapshot,
            verification_summary=sample_verification_summary,
        )

        assert verified_data["floor_area_sqm"] == 85  # Uses verified value

    def test_verification_metadata_included(
        self, sample_logbook, sample_verification_summary
    ):
        """Verification metadata should be included in the output."""
        verified_data = extract_verified_submission_data(
            submission_data=sample_logbook.current_snapshot,
            verification_summary=sample_verification_summary,
        )

        assert "_verification" in verified_data
        assert "verified_fact_count" in verified_data["_verification"]
        assert "total_fact_count" in verified_data["_verification"]
        assert "is_fully_verified" in verified_data["_verification"]


# =============================================================================
# Integration Tests
# =============================================================================


class TestTrustPrimitivesIntegration:
    """Integration tests for the complete trust primitive workflow."""

    def test_full_workflow(self, sample_submission):
        """Test complete workflow from submission to verified export."""
        # 1. Create logbook
        logbook = SubmissionLogbook.create(sample_submission)
        assert logbook.is_chain_valid()

        # 2. Create verification summary
        summary = create_verification_summary_from_submission(
            property_id=logbook.property_id,
            submission_data=logbook.current_snapshot,
            agent_email=sample_submission.agent_email,
        )
        assert summary.unverified_count == summary.total_facts

        # 3. Verify some facts
        summary.get_fact(FactCategory.ADDRESS).verify(
            sample_submission.full_address,
            VerificationSource.LAND_REGISTRY,
            "axis_system",
        )
        summary.get_fact(FactCategory.TENURE).verify(
            sample_submission.tenure.value,
            VerificationSource.LAND_REGISTRY,
            "axis_system",
        )

        # 4. Check Deal Engine readiness
        result = check_deal_engine_readiness(
            chain_integrity=logbook.verify_chain_integrity(),
            verification_summary=summary,
            submission_complete=True,
        )
        assert result.can_evaluate is True
        assert len(result.verified_facts) == 2

        # 5. Extract verified data
        verified_data = extract_verified_submission_data(
            submission_data=logbook.current_snapshot,
            verification_summary=summary,
        )
        assert verified_data["full_address"] is not None
        assert verified_data["tenure"] is not None
        assert verified_data["guide_price"] is None  # Not verified

        # 6. Update status and verify chain still valid
        logbook.update_status(SubmissionStatus.EVALUATED, "deal_engine")
        assert logbook.is_chain_valid()
        assert logbook.version_count == 2

    def test_workflow_with_disputed_fact(self, sample_submission):
        """Test workflow when a fact is disputed."""
        logbook = SubmissionLogbook.create(sample_submission)
        summary = create_verification_summary_from_submission(
            property_id=logbook.property_id,
            submission_data=logbook.current_snapshot,
            agent_email=sample_submission.agent_email,
        )

        # Dispute floor area
        summary.get_fact(FactCategory.FLOOR_AREA).dispute(
            disputed_value=75,
            source=VerificationSource.EPC_REGISTER,
            verified_by="axis_system",
            verification_note="EPC shows 75 sqm, not 95",
        )

        result = check_deal_engine_readiness(
            chain_integrity=logbook.verify_chain_integrity(),
            verification_summary=summary,
            submission_complete=True,
        )

        assert result.can_evaluate is False
        assert result.has_disputes is True
        assert summary.get_disputed_facts()[0][0] == FactCategory.FLOOR_AREA


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
