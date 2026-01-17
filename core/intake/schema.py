"""
Property Intake Schema - Mandatory Upfront Information Gate

Defines the canonical intake schema enforced at submission time.
All required fields must be provided - no inference or fallback.

This is Step 1 of the Axis property intake process.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Final, Optional

from core.comp_engine.models import PropertyType, Tenure


# =============================================================================
# Enums
# =============================================================================


class ListingSource(Enum):
    """Source of the property listing submission."""

    AGENT = "agent"
    SELLER = "seller"
    AXIS_INVITE = "axis_invite"


class IntakeStatus(Enum):
    """
    Status of the property intake submission.

    INFORMATION_COMPLETE: All required fields and disclosures provided
    INFORMATION_PARTIAL: Required fields complete, some disclosures missing
    INFORMATION_MISSING: Required fields missing - hard stop
    """

    INFORMATION_COMPLETE = "information_complete"
    INFORMATION_PARTIAL = "information_partial"
    INFORMATION_MISSING = "information_missing"


class DisclosureStatus(Enum):
    """Status of individual disclosure field."""

    PROVIDED = "provided"
    NOT_PROVIDED = "not_provided"
    NOT_APPLICABLE = "not_applicable"


# =============================================================================
# Constants
# =============================================================================

# UK postcode validation regex
UK_POSTCODE_REGEX: Final = re.compile(
    r"^([A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2})$", re.IGNORECASE
)

# Required intake fields - submission rejected if any missing
REQUIRED_INTAKE_FIELDS: Final[tuple[str, ...]] = (
    "full_address",
    "postcode",
    "property_type",
    "tenure",
    "asking_price",
    "listing_source",
)

# Required disclosure fields - must be explicitly answered
REQUIRED_DISCLOSURE_FIELDS: Final[tuple[str, ...]] = (
    "epc_available",
    "title_number_available",
    "planning_constraints_known",
    "known_issues_disclosed",
)

# Leasehold-specific required disclosures
LEASEHOLD_REQUIRED_DISCLOSURES: Final[tuple[str, ...]] = ("lease_length_known",)


# =============================================================================
# Validation Helpers
# =============================================================================


def validate_uk_postcode(postcode: str) -> bool:
    """Validate UK postcode format."""
    if not postcode:
        return False
    normalised = " ".join(postcode.upper().split())
    return bool(UK_POSTCODE_REGEX.match(normalised))


def normalise_uk_postcode(postcode: str) -> str:
    """Normalise UK postcode to standard format."""
    if not postcode:
        return ""
    clean = postcode.upper().replace(" ", "")
    if len(clean) >= 4:
        return f"{clean[:-3]} {clean[-3:]}"
    return clean


# =============================================================================
# Disclosures
# =============================================================================


@dataclass
class Disclosures:
    """
    Mandatory disclosure fields for property intake.

    All fields must be explicitly answered - no inference or default values.
    The disclosure tracks both the answer (bool) and optional supporting text.
    """

    # Core disclosures (always required)
    epc_available: Optional[bool] = None
    epc_rating: Optional[str] = None  # If available: A-G

    title_number_available: Optional[bool] = None
    title_number: Optional[str] = None  # If available

    planning_constraints_known: Optional[bool] = None
    planning_constraints_detail: Optional[str] = None  # If known

    known_issues_disclosed: Optional[bool] = None
    known_issues_detail: Optional[str] = None  # If yes

    # Leasehold-specific (required only if tenure is leasehold)
    lease_length_known: Optional[bool] = None
    lease_years_remaining: Optional[int] = None  # If known
    ground_rent: Optional[int] = None  # Annual ground rent if known
    service_charge: Optional[int] = None  # Annual service charge if known

    def get_missing_disclosures(self, is_leasehold: bool = False) -> list[str]:
        """
        Get list of missing required disclosure fields.

        Args:
            is_leasehold: Whether property is leasehold (adds lease requirements)

        Returns:
            List of field names that are None (not answered)
        """
        missing = []

        # Check core required disclosures
        if self.epc_available is None:
            missing.append("epc_available")
        if self.title_number_available is None:
            missing.append("title_number_available")
        if self.planning_constraints_known is None:
            missing.append("planning_constraints_known")
        if self.known_issues_disclosed is None:
            missing.append("known_issues_disclosed")

        # Check leasehold-specific disclosures
        if is_leasehold and self.lease_length_known is None:
            missing.append("lease_length_known")

        return missing

    def get_disclosure_status(self, is_leasehold: bool = False) -> DisclosureStatus:
        """
        Determine overall disclosure status.

        Returns:
            PROVIDED if all required disclosures answered
            NOT_PROVIDED if any required disclosure missing
        """
        missing = self.get_missing_disclosures(is_leasehold)
        if missing:
            return DisclosureStatus.NOT_PROVIDED
        return DisclosureStatus.PROVIDED

    def to_dict(self) -> dict:
        """Convert disclosures to dictionary for serialisation."""
        return {
            "epc_available": self.epc_available,
            "epc_rating": self.epc_rating,
            "title_number_available": self.title_number_available,
            "title_number": self.title_number,
            "planning_constraints_known": self.planning_constraints_known,
            "planning_constraints_detail": self.planning_constraints_detail,
            "known_issues_disclosed": self.known_issues_disclosed,
            "known_issues_detail": self.known_issues_detail,
            "lease_length_known": self.lease_length_known,
            "lease_years_remaining": self.lease_years_remaining,
            "ground_rent": self.ground_rent,
            "service_charge": self.service_charge,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Disclosures":
        """Create Disclosures from dictionary."""
        return cls(
            epc_available=data.get("epc_available"),
            epc_rating=data.get("epc_rating"),
            title_number_available=data.get("title_number_available"),
            title_number=data.get("title_number"),
            planning_constraints_known=data.get("planning_constraints_known"),
            planning_constraints_detail=data.get("planning_constraints_detail"),
            known_issues_disclosed=data.get("known_issues_disclosed"),
            known_issues_detail=data.get("known_issues_detail"),
            lease_length_known=data.get("lease_length_known"),
            lease_years_remaining=data.get("lease_years_remaining"),
            ground_rent=data.get("ground_rent"),
            service_charge=data.get("service_charge"),
        )


# =============================================================================
# Property Intake
# =============================================================================


@dataclass
class PropertyIntake:
    """
    Mandatory property intake schema enforced at submission time.

    All REQUIRED fields must be provided - no inference, fallback, or mock data.
    Partial disclosures are allowed but tracked.

    This is the entry point for all properties into the Axis system.
    """

    # === REQUIRED FIELDS (submission rejected if missing) ===
    full_address: str
    postcode: str
    property_type: PropertyType
    tenure: Tenure
    asking_price: int
    listing_source: ListingSource

    # === REQUIRED DISCLOSURES ===
    disclosures: Disclosures

    # === OPTIONAL FIELDS (may be None) ===
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    square_feet: Optional[int] = None
    description: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

    # === METADATA (set by system) ===
    intake_id: Optional[str] = None
    submitted_at: Optional[datetime] = None
    status: IntakeStatus = field(default=IntakeStatus.INFORMATION_MISSING)

    def __post_init__(self) -> None:
        """Validate required fields at construction."""
        # Validate required string fields
        if not self.full_address or not self.full_address.strip():
            raise ValueError("full_address is required and cannot be empty")

        if not self.postcode or not self.postcode.strip():
            raise ValueError("postcode is required and cannot be empty")

        if not validate_uk_postcode(self.postcode):
            raise ValueError(f"Invalid UK postcode format: {self.postcode}")

        # Normalise postcode
        object.__setattr__(self, "postcode", normalise_uk_postcode(self.postcode))

        # Validate asking price
        if self.asking_price is None:
            raise ValueError("asking_price is required")
        if self.asking_price <= 0:
            raise ValueError("asking_price must be positive")

        # Validate optional numeric fields if provided
        if self.bedrooms is not None and self.bedrooms < 0:
            raise ValueError("bedrooms cannot be negative")
        if self.bathrooms is not None and self.bathrooms < 0:
            raise ValueError("bathrooms cannot be negative")
        if self.square_feet is not None and self.square_feet <= 0:
            raise ValueError("square_feet must be positive if provided")

        # Determine status based on disclosures
        self._update_status()

    def _update_status(self) -> None:
        """Update intake status based on disclosure completeness."""
        is_leasehold = self.tenure == Tenure.LEASEHOLD
        missing = self.disclosures.get_missing_disclosures(is_leasehold)

        if not missing:
            object.__setattr__(self, "status", IntakeStatus.INFORMATION_COMPLETE)
        else:
            object.__setattr__(self, "status", IntakeStatus.INFORMATION_PARTIAL)

    @property
    def is_complete(self) -> bool:
        """Check if intake has all required information."""
        return self.status == IntakeStatus.INFORMATION_COMPLETE

    @property
    def is_leasehold(self) -> bool:
        """Check if property is leasehold."""
        return self.tenure == Tenure.LEASEHOLD

    @property
    def missing_disclosures(self) -> list[str]:
        """Get list of missing disclosure fields."""
        return self.disclosures.get_missing_disclosures(self.is_leasehold)

    def to_dict(self) -> dict:
        """Convert intake to dictionary for serialisation."""
        return {
            "intake_id": self.intake_id,
            "full_address": self.full_address,
            "postcode": self.postcode,
            "property_type": self.property_type.value,
            "tenure": self.tenure.value,
            "asking_price": self.asking_price,
            "listing_source": self.listing_source.value,
            "disclosures": self.disclosures.to_dict(),
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
            "square_feet": self.square_feet,
            "description": self.description,
            "contact_name": self.contact_name,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "status": self.status.value,
        }


# =============================================================================
# Validation Result
# =============================================================================


@dataclass(frozen=True)
class IntakeValidationResult:
    """
    Result of intake validation.

    Contains validation outcome, status, and any error messages.
    """

    valid: bool
    status: IntakeStatus
    missing_required_fields: tuple[str, ...]
    missing_disclosures: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def can_proceed(self) -> bool:
        """
        Check if intake can proceed to next stage.

        INFORMATION_COMPLETE and INFORMATION_PARTIAL can proceed.
        INFORMATION_MISSING is a hard stop.
        """
        return self.status != IntakeStatus.INFORMATION_MISSING

    @property
    def is_blocked(self) -> bool:
        """Check if intake is blocked due to missing required fields."""
        return self.status == IntakeStatus.INFORMATION_MISSING

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "valid": self.valid,
            "status": self.status.value,
            "can_proceed": self.can_proceed,
            "is_blocked": self.is_blocked,
            "missing_required_fields": list(self.missing_required_fields),
            "missing_disclosures": list(self.missing_disclosures),
            "errors": list(self.errors),
        }
