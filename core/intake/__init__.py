"""
Axis Deal Engine - Property Intake Module

Step 1: Mandatory Upfront Information Gate
Step 2: Digital Property Logbook

This module enforces mandatory property information collection at submission
time and maintains an immutable audit trail via append-only logbooks.

NO fallback, mock, or inferred data is ever inserted.
"""

from core.intake.schema import (
    PropertyIntake,
    DisclosureStatus,
    IntakeStatus,
    ListingSource,
    Disclosures,
    IntakeValidationResult,
    REQUIRED_INTAKE_FIELDS,
    REQUIRED_DISCLOSURE_FIELDS,
)
from core.intake.logbook import (
    PropertyLogbook,
    LogbookVersion,
    SubmittedBy,
    LogbookStatus,
)
from core.intake.validation import (
    validate_intake,
    validate_disclosures,
    create_intake,
)

__all__ = [
    # Schema
    "PropertyIntake",
    "DisclosureStatus",
    "IntakeStatus",
    "ListingSource",
    "Disclosures",
    "IntakeValidationResult",
    "REQUIRED_INTAKE_FIELDS",
    "REQUIRED_DISCLOSURE_FIELDS",
    # Logbook
    "PropertyLogbook",
    "LogbookVersion",
    "SubmittedBy",
    "LogbookStatus",
    # Validation
    "validate_intake",
    "validate_disclosures",
    "create_intake",
]
