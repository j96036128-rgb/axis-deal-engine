"""
Intake Validation - Submission Rules and Failure States

Implements validation logic for property intake with explicit failure states.
No fallback, mock, or inferred data is ever inserted.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from core.comp_engine.models import PropertyType, Tenure
from core.intake.schema import (
    Disclosures,
    IntakeStatus,
    IntakeValidationResult,
    ListingSource,
    PropertyIntake,
    REQUIRED_INTAKE_FIELDS,
    validate_uk_postcode,
)
from core.intake.logbook import PropertyLogbook, SubmittedBy


# =============================================================================
# Validation Functions
# =============================================================================


def validate_intake_data(data: dict[str, Any]) -> IntakeValidationResult:
    """
    Validate raw intake data before creating PropertyIntake.

    This is the primary validation function that checks all required fields
    and disclosures. It returns a detailed validation result with all errors.

    Args:
        data: Raw intake data dictionary

    Returns:
        IntakeValidationResult with validation outcome
    """
    errors: list[str] = []
    missing_required: list[str] = []
    missing_disclosures: list[str] = []

    # === Check required fields ===

    # full_address
    full_address = data.get("full_address", "")
    if not full_address or not str(full_address).strip():
        missing_required.append("full_address")
        errors.append("full_address is required and cannot be empty")

    # postcode
    postcode = data.get("postcode", "")
    if not postcode or not str(postcode).strip():
        missing_required.append("postcode")
        errors.append("postcode is required and cannot be empty")
    elif not validate_uk_postcode(str(postcode)):
        errors.append(f"Invalid UK postcode format: {postcode}")

    # property_type
    property_type = data.get("property_type")
    if property_type is None:
        missing_required.append("property_type")
        errors.append("property_type is required")
    elif isinstance(property_type, str):
        normalised = property_type.lower().strip().replace("_", "-")
        if normalised not in [pt.value for pt in PropertyType]:
            errors.append(f"Invalid property_type: {property_type}")
    elif not isinstance(property_type, PropertyType):
        errors.append(f"Invalid property_type: {property_type}")

    # tenure
    tenure = data.get("tenure")
    if tenure is None:
        missing_required.append("tenure")
        errors.append("tenure is required")
    elif isinstance(tenure, str):
        normalised = tenure.lower().strip()
        if normalised not in [t.value for t in Tenure]:
            errors.append(f"Invalid tenure: {tenure}")
    elif not isinstance(tenure, Tenure):
        errors.append(f"Invalid tenure: {tenure}")

    # Determine if leasehold for disclosure validation
    is_leasehold = False
    if isinstance(tenure, Tenure):
        is_leasehold = tenure == Tenure.LEASEHOLD
    elif isinstance(tenure, str):
        is_leasehold = tenure.lower().strip() == "leasehold"

    # asking_price
    asking_price = data.get("asking_price")
    if asking_price is None:
        missing_required.append("asking_price")
        errors.append("asking_price is required")
    else:
        try:
            price = int(asking_price)
            if price <= 0:
                errors.append("asking_price must be positive")
        except (ValueError, TypeError):
            errors.append(f"asking_price must be a valid integer: {asking_price}")

    # listing_source
    listing_source = data.get("listing_source")
    if listing_source is None:
        missing_required.append("listing_source")
        errors.append("listing_source is required")
    elif isinstance(listing_source, str):
        normalised = listing_source.lower().strip()
        if normalised not in [ls.value for ls in ListingSource]:
            errors.append(f"Invalid listing_source: {listing_source}")
    elif not isinstance(listing_source, ListingSource):
        errors.append(f"Invalid listing_source: {listing_source}")

    # === Check disclosures ===
    disclosures_data = data.get("disclosures", {})
    if not isinstance(disclosures_data, dict):
        disclosures_data = {}

    # Check required disclosure fields
    if disclosures_data.get("epc_available") is None:
        missing_disclosures.append("epc_available")
    if disclosures_data.get("title_number_available") is None:
        missing_disclosures.append("title_number_available")
    if disclosures_data.get("planning_constraints_known") is None:
        missing_disclosures.append("planning_constraints_known")
    if disclosures_data.get("known_issues_disclosed") is None:
        missing_disclosures.append("known_issues_disclosed")

    # Leasehold-specific disclosures
    if is_leasehold and disclosures_data.get("lease_length_known") is None:
        missing_disclosures.append("lease_length_known")

    # === Determine status ===
    if missing_required:
        status = IntakeStatus.INFORMATION_MISSING
        valid = False
    elif missing_disclosures:
        status = IntakeStatus.INFORMATION_PARTIAL
        valid = True  # Can proceed but flagged
    else:
        status = IntakeStatus.INFORMATION_COMPLETE
        valid = True

    return IntakeValidationResult(
        valid=valid,
        status=status,
        missing_required_fields=tuple(missing_required),
        missing_disclosures=tuple(missing_disclosures),
        errors=tuple(errors),
    )


def validate_intake(intake: PropertyIntake) -> IntakeValidationResult:
    """
    Validate an existing PropertyIntake instance.

    Args:
        intake: PropertyIntake to validate

    Returns:
        IntakeValidationResult with validation outcome
    """
    # Convert intake to dict and validate
    return validate_intake_data(intake.to_dict())


def validate_disclosures(
    disclosures: Disclosures,
    is_leasehold: bool = False,
) -> tuple[bool, list[str]]:
    """
    Validate disclosures separately.

    Args:
        disclosures: Disclosures to validate
        is_leasehold: Whether property is leasehold

    Returns:
        Tuple of (is_complete, missing_fields)
    """
    missing = disclosures.get_missing_disclosures(is_leasehold)
    return len(missing) == 0, missing


# =============================================================================
# Intake Creation
# =============================================================================


def create_intake(
    data: dict[str, Any],
    validate_first: bool = True,
) -> tuple[Optional[PropertyIntake], IntakeValidationResult]:
    """
    Create a PropertyIntake from raw data with validation.

    This is the primary factory function for creating intakes. It validates
    the data first and only creates the intake if required fields are present.

    Args:
        data: Raw intake data dictionary
        validate_first: Whether to validate before creating (default True)

    Returns:
        Tuple of (PropertyIntake or None, IntakeValidationResult)

    Raises:
        ValueError: If validate_first=False and data is invalid
    """
    # Validate data
    validation = validate_intake_data(data)

    # If blocked (missing required fields), don't create intake
    if validation.is_blocked:
        return None, validation

    # Parse enums from strings if needed
    property_type = data.get("property_type")
    if isinstance(property_type, str):
        property_type = PropertyType.from_string(property_type)
        if property_type is None:
            # Fallback to exact match
            normalised = data["property_type"].lower().strip().replace("_", "-")
            for pt in PropertyType:
                if pt.value == normalised:
                    property_type = pt
                    break

    tenure = data.get("tenure")
    if isinstance(tenure, str):
        tenure = Tenure.from_string(tenure)
        if tenure is None:
            normalised = data["tenure"].lower().strip()
            for t in Tenure:
                if t.value == normalised:
                    tenure = t
                    break

    listing_source = data.get("listing_source")
    if isinstance(listing_source, str):
        normalised = listing_source.lower().strip()
        for ls in ListingSource:
            if ls.value == normalised:
                listing_source = ls
                break

    # Build disclosures
    disclosures_data = data.get("disclosures", {})
    disclosures = Disclosures.from_dict(disclosures_data)

    # Create intake
    try:
        intake = PropertyIntake(
            full_address=data["full_address"],
            postcode=data["postcode"],
            property_type=property_type,
            tenure=tenure,
            asking_price=int(data["asking_price"]),
            listing_source=listing_source,
            disclosures=disclosures,
            bedrooms=data.get("bedrooms"),
            bathrooms=data.get("bathrooms"),
            square_feet=data.get("square_feet"),
            description=data.get("description"),
            contact_name=data.get("contact_name"),
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
            intake_id=str(uuid.uuid4()),
            submitted_at=datetime.utcnow(),
        )
        return intake, validation
    except (ValueError, TypeError, KeyError) as e:
        # This shouldn't happen if validation passed, but handle gracefully
        error_result = IntakeValidationResult(
            valid=False,
            status=IntakeStatus.INFORMATION_MISSING,
            missing_required_fields=validation.missing_required_fields,
            missing_disclosures=validation.missing_disclosures,
            errors=tuple(list(validation.errors) + [str(e)]),
        )
        return None, error_result


# =============================================================================
# Logbook Creation
# =============================================================================


def create_logbook_from_intake(
    intake: PropertyIntake,
    submitted_by: SubmittedBy,
) -> PropertyLogbook:
    """
    Create a PropertyLogbook from a validated intake.

    Args:
        intake: Validated PropertyIntake
        submitted_by: Who submitted the intake

    Returns:
        New PropertyLogbook with initial version
    """
    snapshot = intake.to_dict()
    return PropertyLogbook.create(
        intake_snapshot=snapshot,
        submitted_by=submitted_by,
    )


def intake_to_logbook(
    data: dict[str, Any],
    submitted_by: SubmittedBy,
) -> tuple[Optional[PropertyLogbook], IntakeValidationResult]:
    """
    Validate intake data and create logbook in one step.

    This is a convenience function that validates, creates intake,
    and creates logbook in a single call.

    Args:
        data: Raw intake data
        submitted_by: Who submitted the intake

    Returns:
        Tuple of (PropertyLogbook or None, IntakeValidationResult)
    """
    intake, validation = create_intake(data)

    if intake is None:
        return None, validation

    logbook = create_logbook_from_intake(intake, submitted_by)
    return logbook, validation
