"""
Submission Validation - Validation Logic for Agent Submissions

Implements strict validation for property submissions.
No fallback, mock, or inferred data is ever inserted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from core.comp_engine.models import PropertyType, Tenure
from core.submission.schema import (
    AgentSubmission,
    SaleRoute,
    DocumentType,
    SubmissionStatus,
    REQUIRED_SUBMISSION_FIELDS,
    REQUIRED_DOCUMENTS,
    LEASEHOLD_REQUIRED_DOCUMENTS,
    validate_uk_postcode,
)


# =============================================================================
# Validation Result
# =============================================================================


@dataclass(frozen=True)
class SubmissionValidationResult:
    """
    Result of submission validation.

    Contains validation outcome, missing items, and error messages.
    """

    valid: bool
    missing_fields: tuple[str, ...]
    missing_documents: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        """Check if submission is complete (no missing items)."""
        return self.valid and not self.missing_fields and not self.missing_documents

    @property
    def can_submit(self) -> bool:
        """Check if submission can proceed (valid but may have missing docs)."""
        return self.valid

    @property
    def is_blocked(self) -> bool:
        """Check if submission is blocked due to validation errors."""
        return not self.valid

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "valid": self.valid,
            "is_complete": self.is_complete,
            "can_submit": self.can_submit,
            "is_blocked": self.is_blocked,
            "missing_fields": list(self.missing_fields),
            "missing_documents": list(self.missing_documents),
            "errors": list(self.errors),
        }


# =============================================================================
# Validation Functions
# =============================================================================


def validate_submission_data(data: dict[str, Any]) -> SubmissionValidationResult:
    """
    Validate raw submission data before creating AgentSubmission.

    Args:
        data: Raw submission data dictionary

    Returns:
        SubmissionValidationResult with validation outcome
    """
    errors: list[str] = []
    missing_fields: list[str] = []
    missing_documents: list[str] = []

    # === Check required fields ===
    # Error messages are written in plain English for agent-facing display

    # full_address
    full_address = data.get("full_address", "")
    if not full_address or not str(full_address).strip():
        missing_fields.append("full_address")
        errors.append("Please provide the full property address")

    # postcode
    postcode = data.get("postcode", "")
    if not postcode or not str(postcode).strip():
        missing_fields.append("postcode")
        errors.append("Please provide the property postcode")
    elif not validate_uk_postcode(str(postcode)):
        errors.append("Please enter a valid UK postcode (e.g., SW1A 1AA)")

    # property_type
    property_type = data.get("property_type")
    if property_type is None:
        missing_fields.append("property_type")
        errors.append("Please select a property type")
    elif isinstance(property_type, str):
        try:
            PropertyType(property_type.replace("_", "-"))
        except ValueError:
            errors.append("Please select a valid property type from the list")
    elif not isinstance(property_type, PropertyType):
        errors.append("Please select a valid property type from the list")

    # tenure
    tenure = data.get("tenure")
    is_leasehold = False
    if tenure is None:
        missing_fields.append("tenure")
        errors.append("Please select freehold or leasehold")
    elif isinstance(tenure, str):
        try:
            tenure_enum = Tenure(tenure)
            is_leasehold = tenure_enum == Tenure.LEASEHOLD
        except ValueError:
            errors.append("Please select freehold or leasehold")
    elif isinstance(tenure, Tenure):
        is_leasehold = tenure == Tenure.LEASEHOLD
    else:
        errors.append("Please select freehold or leasehold")

    # floor_area_sqm
    floor_area = data.get("floor_area_sqm")
    if floor_area is None:
        missing_fields.append("floor_area_sqm")
        errors.append("Please provide the floor area in square metres")
    else:
        try:
            area = int(floor_area)
            if area <= 0:
                errors.append("Floor area must be greater than zero")
        except (ValueError, TypeError):
            errors.append("Please enter a valid number for floor area")

    # guide_price
    guide_price = data.get("guide_price")
    if guide_price is None:
        missing_fields.append("guide_price")
        errors.append("Please provide the guide price")
    else:
        try:
            price = int(guide_price)
            if price <= 0:
                errors.append("Guide price must be greater than zero")
        except (ValueError, TypeError):
            errors.append("Please enter a valid number for guide price")

    # sale_route
    sale_route = data.get("sale_route")
    if sale_route is None:
        missing_fields.append("sale_route")
        errors.append("Please select a sale route")
    elif isinstance(sale_route, str):
        try:
            SaleRoute(sale_route)
        except ValueError:
            errors.append("Please select a valid sale route from the list")
    elif not isinstance(sale_route, SaleRoute):
        errors.append("Please select a valid sale route from the list")

    # agent_firm
    agent_firm = data.get("agent_firm", "")
    if not agent_firm or not str(agent_firm).strip():
        missing_fields.append("agent_firm")
        errors.append("Agent firm is required")

    # agent_name
    agent_name = data.get("agent_name", "")
    if not agent_name or not str(agent_name).strip():
        missing_fields.append("agent_name")
        errors.append("Please provide your name")

    # agent_email
    agent_email = data.get("agent_email", "")
    if not agent_email or not str(agent_email).strip():
        missing_fields.append("agent_email")
        errors.append("Agent email is required")
    elif "@" not in agent_email:
        errors.append("Please enter a valid email address")

    # === Check documents ===
    documents = data.get("documents", [])
    uploaded_types = set()

    for doc in documents:
        doc_type = doc.get("document_type")
        if isinstance(doc_type, str):
            try:
                uploaded_types.add(DocumentType(doc_type))
            except ValueError:
                pass
        elif isinstance(doc_type, DocumentType):
            uploaded_types.add(doc_type)

    # Check required documents
    for required_type in REQUIRED_DOCUMENTS:
        if required_type not in uploaded_types:
            missing_documents.append(required_type.value)

    # Check leasehold-specific documents
    if is_leasehold:
        for required_type in LEASEHOLD_REQUIRED_DOCUMENTS:
            if required_type not in uploaded_types:
                missing_documents.append(required_type.value)

    # Determine validity (fields must be present, documents can be uploaded later)
    valid = len(missing_fields) == 0 and len([e for e in errors if "missing" not in e.lower()]) == 0

    return SubmissionValidationResult(
        valid=valid,
        missing_fields=tuple(missing_fields),
        missing_documents=tuple(missing_documents),
        errors=tuple(errors),
    )


def validate_submission(submission: AgentSubmission) -> SubmissionValidationResult:
    """
    Validate an existing AgentSubmission instance.

    Args:
        submission: AgentSubmission to validate

    Returns:
        SubmissionValidationResult with validation outcome
    """
    return validate_submission_data(submission.to_dict())


# =============================================================================
# Submission Creation
# =============================================================================


def create_submission(
    data: dict[str, Any],
) -> tuple[Optional[AgentSubmission], SubmissionValidationResult]:
    """
    Create an AgentSubmission from raw data with validation.

    Args:
        data: Raw submission data dictionary

    Returns:
        Tuple of (AgentSubmission or None, SubmissionValidationResult)
    """
    # Validate data
    validation = validate_submission_data(data)

    # If blocked (missing required fields), don't create submission
    if validation.is_blocked:
        return None, validation

    # Parse enums
    property_type = data.get("property_type")
    if isinstance(property_type, str):
        property_type = PropertyType(property_type.replace("_", "-"))

    tenure = data.get("tenure")
    if isinstance(tenure, str):
        tenure = Tenure(tenure)

    sale_route = data.get("sale_route")
    if isinstance(sale_route, str):
        sale_route = SaleRoute(sale_route)

    # Create submission
    try:
        submission = AgentSubmission(
            full_address=data["full_address"],
            postcode=data["postcode"],
            property_type=property_type,
            tenure=tenure,
            floor_area_sqm=int(data["floor_area_sqm"]),
            guide_price=int(data["guide_price"]),
            sale_route=sale_route,
            agent_firm=data["agent_firm"],
            agent_name=data["agent_name"],
            agent_email=data["agent_email"],
            bedrooms=data.get("bedrooms"),
            bathrooms=data.get("bathrooms"),
            year_built=data.get("year_built"),
            council_tax_band=data.get("council_tax_band"),
            epc_rating=data.get("epc_rating"),
            lease_years_remaining=data.get("lease_years_remaining"),
            ground_rent_annual=data.get("ground_rent_annual"),
            service_charge_annual=data.get("service_charge_annual"),
            property_id=data.get("property_id"),
            submission_id=data.get("submission_id"),
        )

        # Set status based on document completeness
        if validation.missing_documents:
            object.__setattr__(submission, "status", SubmissionStatus.INCOMPLETE)
        else:
            object.__setattr__(submission, "status", SubmissionStatus.SUBMITTED)

        return submission, validation

    except (ValueError, TypeError, KeyError) as e:
        error_result = SubmissionValidationResult(
            valid=False,
            missing_fields=validation.missing_fields,
            missing_documents=validation.missing_documents,
            errors=tuple(list(validation.errors) + [str(e)]),
        )
        return None, error_result
