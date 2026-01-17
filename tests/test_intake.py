"""
Tests for Property Intake Module

Step 1: Mandatory Upfront Information Gate
Step 2: Digital Property Logbook

Tests cover:
- Missing required fields
- Partial disclosures
- Full compliance
- Logbook version immutability
"""

import copy
import pytest
from datetime import datetime, timedelta

from core.comp_engine.models import PropertyType, Tenure
from core.intake import (
    PropertyIntake,
    Disclosures,
    IntakeStatus,
    ListingSource,
    PropertyLogbook,
    LogbookVersion,
    SubmittedBy,
    LogbookStatus,
    validate_intake,
    validate_disclosures,
    create_intake,
    REQUIRED_INTAKE_FIELDS,
    REQUIRED_DISCLOSURE_FIELDS,
)
from core.intake.validation import validate_intake_data, create_logbook_from_intake


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def complete_disclosures():
    """Disclosures with all required fields provided."""
    return Disclosures(
        epc_available=True,
        epc_rating="C",
        title_number_available=True,
        title_number="ABC123",
        planning_constraints_known=True,
        planning_constraints_detail="None known",
        known_issues_disclosed=True,
        known_issues_detail="No issues",
    )


@pytest.fixture
def complete_leasehold_disclosures():
    """Disclosures with all fields including leasehold-specific."""
    return Disclosures(
        epc_available=True,
        epc_rating="B",
        title_number_available=True,
        title_number="XYZ789",
        planning_constraints_known=False,
        known_issues_disclosed=False,
        lease_length_known=True,
        lease_years_remaining=85,
        ground_rent=250,
        service_charge=1500,
    )


@pytest.fixture
def partial_disclosures():
    """Disclosures with some required fields missing."""
    return Disclosures(
        epc_available=True,
        title_number_available=None,  # Missing
        planning_constraints_known=True,
        known_issues_disclosed=None,  # Missing
    )


@pytest.fixture
def complete_intake_data(complete_disclosures):
    """Complete intake data dictionary."""
    return {
        "full_address": "123 Test Street, London",
        "postcode": "SW1A 1AA",
        "property_type": "flat",
        "tenure": "leasehold",
        "asking_price": 450000,
        "listing_source": "agent",
        "disclosures": complete_disclosures.to_dict(),
        "bedrooms": 2,
        "bathrooms": 1,
    }


@pytest.fixture
def minimal_intake_data():
    """Minimal valid intake data (required fields only)."""
    return {
        "full_address": "456 Minimal Road, Manchester",
        "postcode": "M1 1AA",
        "property_type": "terraced",
        "tenure": "freehold",
        "asking_price": 250000,
        "listing_source": "seller",
        "disclosures": {
            "epc_available": False,
            "title_number_available": False,
            "planning_constraints_known": False,
            "known_issues_disclosed": False,
        },
    }


# =============================================================================
# STEP 1 TESTS - Mandatory Upfront Information Gate
# =============================================================================


class TestRequiredFields:
    """Tests for required field validation."""

    def test_missing_full_address_rejected(self):
        """Submission rejected if full_address is missing."""
        data = {
            "postcode": "SW1A 1AA",
            "property_type": "flat",
            "tenure": "freehold",
            "asking_price": 300000,
            "listing_source": "agent",
            "disclosures": {},
        }

        result = validate_intake_data(data)

        assert result.is_blocked
        assert result.status == IntakeStatus.INFORMATION_MISSING
        assert "full_address" in result.missing_required_fields

    def test_missing_postcode_rejected(self):
        """Submission rejected if postcode is missing."""
        data = {
            "full_address": "123 Test Street",
            "property_type": "flat",
            "tenure": "freehold",
            "asking_price": 300000,
            "listing_source": "agent",
            "disclosures": {},
        }

        result = validate_intake_data(data)

        assert result.is_blocked
        assert "postcode" in result.missing_required_fields

    def test_invalid_postcode_format_rejected(self):
        """Submission rejected if postcode format is invalid."""
        data = {
            "full_address": "123 Test Street",
            "postcode": "INVALID",
            "property_type": "flat",
            "tenure": "freehold",
            "asking_price": 300000,
            "listing_source": "agent",
            "disclosures": {},
        }

        result = validate_intake_data(data)

        assert "Invalid UK postcode format" in str(result.errors)

    def test_missing_property_type_rejected(self):
        """Submission rejected if property_type is missing."""
        data = {
            "full_address": "123 Test Street",
            "postcode": "SW1A 1AA",
            "tenure": "freehold",
            "asking_price": 300000,
            "listing_source": "agent",
            "disclosures": {},
        }

        result = validate_intake_data(data)

        assert result.is_blocked
        assert "property_type" in result.missing_required_fields

    def test_missing_tenure_rejected(self):
        """Submission rejected if tenure is missing."""
        data = {
            "full_address": "123 Test Street",
            "postcode": "SW1A 1AA",
            "property_type": "flat",
            "asking_price": 300000,
            "listing_source": "agent",
            "disclosures": {},
        }

        result = validate_intake_data(data)

        assert result.is_blocked
        assert "tenure" in result.missing_required_fields

    def test_missing_asking_price_rejected(self):
        """Submission rejected if asking_price is missing."""
        data = {
            "full_address": "123 Test Street",
            "postcode": "SW1A 1AA",
            "property_type": "flat",
            "tenure": "freehold",
            "listing_source": "agent",
            "disclosures": {},
        }

        result = validate_intake_data(data)

        assert result.is_blocked
        assert "asking_price" in result.missing_required_fields

    def test_zero_asking_price_rejected(self):
        """Submission rejected if asking_price is zero."""
        data = {
            "full_address": "123 Test Street",
            "postcode": "SW1A 1AA",
            "property_type": "flat",
            "tenure": "freehold",
            "asking_price": 0,
            "listing_source": "agent",
            "disclosures": {},
        }

        result = validate_intake_data(data)

        assert "asking_price must be positive" in str(result.errors)

    def test_negative_asking_price_rejected(self):
        """Submission rejected if asking_price is negative."""
        data = {
            "full_address": "123 Test Street",
            "postcode": "SW1A 1AA",
            "property_type": "flat",
            "tenure": "freehold",
            "asking_price": -100000,
            "listing_source": "agent",
            "disclosures": {},
        }

        result = validate_intake_data(data)

        assert "asking_price must be positive" in str(result.errors)

    def test_missing_listing_source_rejected(self):
        """Submission rejected if listing_source is missing."""
        data = {
            "full_address": "123 Test Street",
            "postcode": "SW1A 1AA",
            "property_type": "flat",
            "tenure": "freehold",
            "asking_price": 300000,
            "disclosures": {},
        }

        result = validate_intake_data(data)

        assert result.is_blocked
        assert "listing_source" in result.missing_required_fields

    def test_all_required_fields_missing_lists_all(self):
        """All missing required fields are listed."""
        data = {"disclosures": {}}

        result = validate_intake_data(data)

        assert result.is_blocked
        assert len(result.missing_required_fields) == 6
        for field in REQUIRED_INTAKE_FIELDS:
            assert field in result.missing_required_fields


class TestDisclosures:
    """Tests for disclosure validation."""

    def test_partial_disclosures_allowed_but_flagged(self, minimal_intake_data):
        """Partial disclosures allow submission but mark as PARTIAL."""
        data = copy.deepcopy(minimal_intake_data)
        # Remove some disclosures
        data["disclosures"]["epc_available"] = None
        data["disclosures"]["title_number_available"] = None

        result = validate_intake_data(data)

        assert result.can_proceed  # Not blocked
        assert result.status == IntakeStatus.INFORMATION_PARTIAL
        assert "epc_available" in result.missing_disclosures
        assert "title_number_available" in result.missing_disclosures

    def test_missing_disclosures_blocks_if_required_fields_ok(self, minimal_intake_data):
        """Missing disclosures result in PARTIAL status."""
        data = copy.deepcopy(minimal_intake_data)
        data["disclosures"] = {}  # All disclosures missing

        result = validate_intake_data(data)

        assert result.can_proceed  # Not blocked (required fields present)
        assert result.status == IntakeStatus.INFORMATION_PARTIAL
        assert len(result.missing_disclosures) >= 4

    def test_leasehold_requires_lease_length_disclosure(self):
        """Leasehold properties require lease_length_known disclosure."""
        data = {
            "full_address": "Flat 1, Test House",
            "postcode": "SW1A 1AA",
            "property_type": "flat",
            "tenure": "leasehold",
            "asking_price": 300000,
            "listing_source": "agent",
            "disclosures": {
                "epc_available": True,
                "title_number_available": True,
                "planning_constraints_known": True,
                "known_issues_disclosed": True,
                # lease_length_known missing
            },
        }

        result = validate_intake_data(data)

        assert result.status == IntakeStatus.INFORMATION_PARTIAL
        assert "lease_length_known" in result.missing_disclosures

    def test_freehold_does_not_require_lease_disclosure(self):
        """Freehold properties do not require lease_length_known."""
        data = {
            "full_address": "123 Test House",
            "postcode": "SW1A 1AA",
            "property_type": "detached",
            "tenure": "freehold",
            "asking_price": 500000,
            "listing_source": "agent",
            "disclosures": {
                "epc_available": True,
                "title_number_available": True,
                "planning_constraints_known": True,
                "known_issues_disclosed": True,
            },
        }

        result = validate_intake_data(data)

        assert result.status == IntakeStatus.INFORMATION_COMPLETE
        assert "lease_length_known" not in result.missing_disclosures

    def test_complete_disclosures_returns_complete_status(self, complete_intake_data):
        """Complete disclosures result in INFORMATION_COMPLETE."""
        # Add leasehold disclosure since the fixture is leasehold
        complete_intake_data["disclosures"]["lease_length_known"] = True

        result = validate_intake_data(complete_intake_data)

        assert result.status == IntakeStatus.INFORMATION_COMPLETE
        assert len(result.missing_disclosures) == 0


class TestIntakeCreation:
    """Tests for PropertyIntake creation."""

    def test_create_intake_with_complete_data(self, complete_intake_data):
        """Create intake with complete data succeeds."""
        complete_intake_data["disclosures"]["lease_length_known"] = True

        intake, result = create_intake(complete_intake_data)

        assert intake is not None
        assert result.status == IntakeStatus.INFORMATION_COMPLETE
        assert intake.is_complete

    def test_create_intake_with_missing_required_returns_none(self):
        """Create intake with missing required fields returns None."""
        data = {"full_address": "123 Test Street"}

        intake, result = create_intake(data)

        assert intake is None
        assert result.is_blocked
        assert result.status == IntakeStatus.INFORMATION_MISSING

    def test_create_intake_with_partial_disclosures_succeeds(self, minimal_intake_data):
        """Create intake with partial disclosures succeeds but flagged."""
        minimal_intake_data["disclosures"]["epc_available"] = None

        intake, result = create_intake(minimal_intake_data)

        assert intake is not None
        assert result.status == IntakeStatus.INFORMATION_PARTIAL
        assert not intake.is_complete

    def test_intake_postcode_normalised(self):
        """Postcode is normalised on creation."""
        data = {
            "full_address": "123 Test Street",
            "postcode": "sw1a1aa",  # lowercase, no space
            "property_type": "flat",
            "tenure": "freehold",
            "asking_price": 300000,
            "listing_source": "agent",
            "disclosures": {
                "epc_available": True,
                "title_number_available": True,
                "planning_constraints_known": True,
                "known_issues_disclosed": True,
            },
        }

        intake, _ = create_intake(data)

        assert intake is not None
        assert intake.postcode == "SW1A 1AA"

    def test_no_fallback_data_inserted(self, minimal_intake_data):
        """No fallback or mock data is inserted for missing optional fields."""
        intake, _ = create_intake(minimal_intake_data)

        assert intake is not None
        assert intake.bedrooms is None  # Not inferred
        assert intake.bathrooms is None  # Not inferred
        assert intake.square_feet is None  # Not inferred
        assert intake.description is None  # Not inferred


class TestIntakeStatusLabels:
    """Tests for status labels."""

    def test_information_complete_status(self, complete_intake_data):
        """INFORMATION_COMPLETE when all required and disclosures provided."""
        complete_intake_data["disclosures"]["lease_length_known"] = True

        intake, result = create_intake(complete_intake_data)

        assert intake.status == IntakeStatus.INFORMATION_COMPLETE

    def test_information_partial_status(self, minimal_intake_data):
        """INFORMATION_PARTIAL when disclosures incomplete."""
        minimal_intake_data["disclosures"]["epc_available"] = None

        intake, result = create_intake(minimal_intake_data)

        assert intake.status == IntakeStatus.INFORMATION_PARTIAL

    def test_information_missing_blocks_creation(self):
        """INFORMATION_MISSING is a hard stop - no intake created."""
        data = {"full_address": "123 Test"}

        intake, result = create_intake(data)

        assert intake is None
        assert result.status == IntakeStatus.INFORMATION_MISSING
        assert result.is_blocked
        assert not result.can_proceed


# =============================================================================
# STEP 2 TESTS - Digital Property Logbook
# =============================================================================


class TestLogbookCreation:
    """Tests for PropertyLogbook creation."""

    def test_create_logbook_from_intake(self, complete_intake_data):
        """Create logbook from intake creates initial version."""
        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)

        logbook = create_logbook_from_intake(intake, SubmittedBy.AGENT)

        assert logbook is not None
        assert logbook.property_id is not None
        assert logbook.version_count == 1
        assert logbook.current_status == LogbookStatus.SUBMITTED

    def test_logbook_initial_version_has_correct_data(self, complete_intake_data):
        """Initial version contains correct snapshot data."""
        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)

        logbook = create_logbook_from_intake(intake, SubmittedBy.SELLER)

        version = logbook.current_version
        assert version is not None
        assert version.version_number == 1
        assert version.submitted_by == SubmittedBy.SELLER
        assert version.intake_snapshot["full_address"] == intake.full_address


class TestLogbookVersionImmutability:
    """Tests for version immutability."""

    def test_version_is_frozen_dataclass(self, complete_intake_data):
        """LogbookVersion is immutable (frozen)."""
        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)
        logbook = create_logbook_from_intake(intake, SubmittedBy.AGENT)

        version = logbook.current_version

        with pytest.raises(AttributeError):
            version.version_number = 999

    def test_versions_tuple_prevents_modification(self, complete_intake_data):
        """Versions property returns tuple (immutable)."""
        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)
        logbook = create_logbook_from_intake(intake, SubmittedBy.AGENT)

        versions = logbook.versions

        assert isinstance(versions, tuple)
        # Tuple is immutable, no append method
        assert not hasattr(versions, "append")

    def test_snapshot_is_deep_copied(self, complete_intake_data):
        """Snapshot is deep copied to prevent external modification."""
        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)
        logbook = create_logbook_from_intake(intake, SubmittedBy.AGENT)

        # Get snapshot
        snapshot = logbook.current_snapshot

        # Modify the returned snapshot
        snapshot["full_address"] = "MODIFIED ADDRESS"

        # Original should be unchanged
        assert logbook.current_snapshot["full_address"] != "MODIFIED ADDRESS"

    def test_adding_version_does_not_modify_existing(self, complete_intake_data):
        """Adding a new version does not modify existing versions."""
        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)
        logbook = create_logbook_from_intake(intake, SubmittedBy.AGENT)

        # Get v1 before adding v2
        v1 = logbook.get_version(1)
        v1_address = v1.intake_snapshot["full_address"]

        # Add new version with different address
        new_snapshot = logbook.current_snapshot
        new_snapshot["full_address"] = "999 New Address"
        logbook.add_version(new_snapshot, SubmittedBy.SELLER)

        # V1 should be unchanged
        v1_after = logbook.get_version(1)
        assert v1_after.intake_snapshot["full_address"] == v1_address
        assert v1_after.intake_snapshot["full_address"] != "999 New Address"


class TestLogbookAppendOnly:
    """Tests for append-only behavior."""

    def test_no_delete_method_exists(self, complete_intake_data):
        """No method exists to delete versions."""
        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)
        logbook = create_logbook_from_intake(intake, SubmittedBy.AGENT)

        assert not hasattr(logbook, "delete_version")
        assert not hasattr(logbook, "remove_version")

    def test_no_edit_method_exists(self, complete_intake_data):
        """No method exists to edit existing versions."""
        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)
        logbook = create_logbook_from_intake(intake, SubmittedBy.AGENT)

        assert not hasattr(logbook, "edit_version")
        assert not hasattr(logbook, "update_version")

    def test_version_count_only_increases(self, complete_intake_data):
        """Version count only increases, never decreases."""
        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)
        logbook = create_logbook_from_intake(intake, SubmittedBy.AGENT)

        counts = [logbook.version_count]

        # Add versions
        for i in range(3):
            snapshot = logbook.current_snapshot
            logbook.add_version(snapshot, SubmittedBy.AXIS)
            counts.append(logbook.version_count)

        # Verify monotonically increasing
        for i in range(len(counts) - 1):
            assert counts[i + 1] > counts[i]

    def test_analysis_creates_new_version(self, complete_intake_data):
        """Adding analysis creates a new version, not modifying existing."""
        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)
        logbook = create_logbook_from_intake(intake, SubmittedBy.AGENT)

        initial_count = logbook.version_count

        # Add analysis
        analysis = {"emv": 500000, "bmv_percent": 10.0}
        logbook.add_analysis(analysis, analysed_by="analyst_1")

        assert logbook.version_count == initial_count + 1

    def test_status_update_creates_new_version(self, complete_intake_data):
        """Status update creates a new version."""
        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)
        logbook = create_logbook_from_intake(intake, SubmittedBy.AGENT)

        initial_count = logbook.version_count

        logbook.update_status(LogbookStatus.UNDER_REVIEW, notes="Starting review")

        assert logbook.version_count == initial_count + 1


class TestLogbookHistory:
    """Tests for viewing history."""

    def test_get_history_returns_all_versions(self, complete_intake_data):
        """get_history returns summary of all versions."""
        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)
        logbook = create_logbook_from_intake(intake, SubmittedBy.AGENT)

        # Add more versions
        logbook.add_version(logbook.current_snapshot, SubmittedBy.SELLER)
        logbook.add_version(logbook.current_snapshot, SubmittedBy.AXIS)

        history = logbook.get_history()

        assert len(history) == 3
        assert history[0]["version_number"] == 1
        assert history[1]["version_number"] == 2
        assert history[2]["version_number"] == 3

    def test_get_version_by_number(self, complete_intake_data):
        """Can retrieve specific version by number."""
        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)
        logbook = create_logbook_from_intake(intake, SubmittedBy.AGENT)

        logbook.add_version(logbook.current_snapshot, SubmittedBy.SELLER)

        v1 = logbook.get_version(1)
        v2 = logbook.get_version(2)

        assert v1.version_number == 1
        assert v2.version_number == 2
        assert v1.submitted_by == SubmittedBy.AGENT
        assert v2.submitted_by == SubmittedBy.SELLER

    def test_get_version_invalid_returns_none(self, complete_intake_data):
        """get_version with invalid number returns None."""
        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)
        logbook = create_logbook_from_intake(intake, SubmittedBy.AGENT)

        assert logbook.get_version(0) is None
        assert logbook.get_version(99) is None


class TestLogbookAnalysis:
    """Tests for Axis analysis on logbook."""

    def test_analysis_references_specific_version(self, complete_intake_data):
        """Analysis is attached to a specific version."""
        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)
        logbook = create_logbook_from_intake(intake, SubmittedBy.AGENT)

        analysis = {"emv": 480000, "bmv_percent": 6.25, "recommendation": "moderate"}
        analysis_version = logbook.add_analysis(analysis, analysed_by="analyst_1")

        assert analysis_version.axis_analysis == analysis
        assert analysis_version.analysed_by == "analyst_1"
        assert analysis_version.analysis_timestamp is not None

    def test_latest_analysis_returns_most_recent(self, complete_intake_data):
        """latest_analysis returns most recent analysis."""
        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)
        logbook = create_logbook_from_intake(intake, SubmittedBy.AGENT)

        # Add first analysis
        analysis1 = {"emv": 480000, "version": 1}
        logbook.add_analysis(analysis1, analysed_by="analyst_1")

        # Add update and new analysis
        logbook.add_version(logbook.current_snapshot, SubmittedBy.SELLER)
        analysis2 = {"emv": 490000, "version": 2}
        logbook.add_analysis(analysis2, analysed_by="analyst_2")

        latest = logbook.latest_analysis
        assert latest["version"] == 2
        assert latest["emv"] == 490000


class TestLogbookExport:
    """Tests for export functionality."""

    def test_export_for_pdf_contains_required_fields(self, complete_intake_data):
        """export_for_pdf contains all required fields."""
        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)
        logbook = create_logbook_from_intake(intake, SubmittedBy.AGENT)

        export = logbook.export_for_pdf()

        assert "property_id" in export
        assert "created_at" in export
        assert "current_status" in export
        assert "version_count" in export
        assert "current_snapshot" in export
        assert "history" in export
        assert "all_versions" in export

    def test_to_dict_serializable(self, complete_intake_data):
        """to_dict returns JSON-serializable data."""
        import json

        complete_intake_data["disclosures"]["lease_length_known"] = True
        intake, _ = create_intake(complete_intake_data)
        logbook = create_logbook_from_intake(intake, SubmittedBy.AGENT)

        data = logbook.to_dict()

        # Should not raise
        json_str = json.dumps(data)
        assert json_str is not None


# =============================================================================
# GUARDRAIL TESTS
# =============================================================================


class TestNoFallbackData:
    """Tests ensuring no fallback/mock/inferred data."""

    def test_missing_optional_fields_stay_none(self, minimal_intake_data):
        """Optional fields not provided remain None - no inference."""
        intake, _ = create_intake(minimal_intake_data)

        assert intake.bedrooms is None
        assert intake.bathrooms is None
        assert intake.square_feet is None
        assert intake.description is None

    def test_disclosures_not_auto_completed(self, minimal_intake_data):
        """Disclosures are not auto-completed with defaults."""
        # Remove one disclosure
        del minimal_intake_data["disclosures"]["epc_available"]

        intake, result = create_intake(minimal_intake_data)

        assert intake is not None
        assert intake.disclosures.epc_available is None
        assert "epc_available" in result.missing_disclosures

    def test_property_type_not_inferred(self):
        """Property type is not inferred from other fields."""
        data = {
            "full_address": "123 Test Street",
            "postcode": "SW1A 1AA",
            # property_type missing - should not be inferred from address
            "tenure": "freehold",
            "asking_price": 300000,
            "listing_source": "agent",
            "disclosures": {},
        }

        intake, result = create_intake(data)

        assert intake is None
        assert "property_type" in result.missing_required_fields

    def test_tenure_not_inferred(self):
        """Tenure is not inferred from property type."""
        data = {
            "full_address": "Flat 1, Test House",
            "postcode": "SW1A 1AA",
            "property_type": "flat",  # Flats are often leasehold
            # tenure missing - should not be inferred
            "asking_price": 300000,
            "listing_source": "agent",
            "disclosures": {},
        }

        intake, result = create_intake(data)

        assert intake is None
        assert "tenure" in result.missing_required_fields
