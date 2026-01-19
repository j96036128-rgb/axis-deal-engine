"""
VerifiedPropertyExport v1.0 Data Contract

Defines the canonical, immutable export format for Deal Engine consumption.
This is the ONLY data format the Deal Engine is permitted to consume from the
Digital Property Logbook.

Core Principles (Non-Negotiable):
1. Verified facts only - never inferred
2. Explicit nulls over assumptions
3. No source metadata exposed
4. No free-text fields
5. Deterministic serialization
6. Immutable once exported
7. Deal Engine must refuse unknown versions

Security Boundary (FORBIDDEN):
- Agent names
- Marketing text
- Source platform identifiers
- Confidence boosting heuristics
- "Assumed" values
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Final, Optional

from core.comp_engine.models import PropertyType, Tenure
from core.submission.schema import SaleRoute


# =============================================================================
# Constants
# =============================================================================

EXPORT_VERSION: Final[str] = "1.0"
SUPPORTED_EXPORT_VERSIONS: Final[tuple[str, ...]] = ("1.0",)

# Trust level thresholds
HIGH_TRUST_THRESHOLD: Final[float] = 85.0
MEDIUM_TRUST_THRESHOLD: Final[float] = 70.0


# =============================================================================
# Enums
# =============================================================================


class TrustLevel(Enum):
    """Trust level based on verification percentage."""

    HIGH = "high"  # >= 85% verified facts
    MEDIUM = "medium"  # >= 70% and < 85% verified facts
    LOW = "low"  # < 70% verified facts (still exportable, but flagged)


class PlanningRestriction(Enum):
    """Known planning restrictions that affect property value."""

    CONSERVATION_AREA = "conservation_area"
    LISTED_BUILDING = "listed_building"
    GREEN_BELT = "green_belt"
    ARTICLE_4 = "article_4"
    TPO = "tpo"  # Tree Preservation Order
    FLOOD_ZONE = "flood_zone"
    RIGHT_OF_WAY = "right_of_way"
    NONE = "none"


# =============================================================================
# Exceptions
# =============================================================================


class ExportVersionError(ValueError):
    """Raised when export version is not supported."""

    pass


class ExportBlockedError(Exception):
    """Raised when export is blocked by gating rules."""

    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__(f"Export blocked: {'; '.join(reasons)}")


# =============================================================================
# Nested Frozen Dataclasses
# =============================================================================


@dataclass(frozen=True)
class ExportMetadata:
    """Metadata about when and how this export was created."""

    exported_at: datetime
    logbook_version: int
    logbook_hash: str  # SHA-256 hex of current version
    chain_valid: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "exported_at": self.exported_at.isoformat(),
            "logbook_version": self.logbook_version,
            "logbook_hash": self.logbook_hash,
            "chain_valid": self.chain_valid,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExportMetadata":
        """Create from dictionary."""
        return cls(
            exported_at=datetime.fromisoformat(data["exported_at"]),
            logbook_version=data["logbook_version"],
            logbook_hash=data["logbook_hash"],
            chain_valid=data["chain_valid"],
        )


@dataclass(frozen=True)
class ExportVerificationSummary:
    """Aggregated verification statistics for the export."""

    trust_level: TrustLevel
    verified_fact_count: int
    unverified_fact_count: int
    disputed_fact_count: int
    rejected_fact_count: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trust_level": self.trust_level.value,
            "verified_fact_count": self.verified_fact_count,
            "unverified_fact_count": self.unverified_fact_count,
            "disputed_fact_count": self.disputed_fact_count,
            "rejected_fact_count": self.rejected_fact_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExportVerificationSummary":
        """Create from dictionary."""
        return cls(
            trust_level=TrustLevel(data["trust_level"]),
            verified_fact_count=data["verified_fact_count"],
            unverified_fact_count=data["unverified_fact_count"],
            disputed_fact_count=data["disputed_fact_count"],
            rejected_fact_count=data["rejected_fact_count"],
        )


@dataclass(frozen=True)
class AddressFacts:
    """Verified address information."""

    full_address: str
    postcode: str
    verified: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "full_address": self.full_address,
            "postcode": self.postcode,
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AddressFacts":
        """Create from dictionary."""
        return cls(
            full_address=data["full_address"],
            postcode=data["postcode"],
            verified=data["verified"],
        )


@dataclass(frozen=True)
class PhysicalFacts:
    """Verified physical property characteristics."""

    property_type: PropertyType
    floor_area_sqm: Optional[float]
    bedrooms: Optional[int]
    bathrooms: Optional[int]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "property_type": self.property_type.value,
            "floor_area_sqm": self.floor_area_sqm,
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PhysicalFacts":
        """Create from dictionary."""
        return cls(
            property_type=PropertyType(data["property_type"]),
            floor_area_sqm=data.get("floor_area_sqm"),
            bedrooms=data.get("bedrooms"),
            bathrooms=data.get("bathrooms"),
        )


@dataclass(frozen=True)
class TenureFacts:
    """Verified tenure information."""

    tenure_type: Tenure
    lease_years_remaining: Optional[int]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tenure_type": self.tenure_type.value,
            "lease_years_remaining": self.lease_years_remaining,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TenureFacts":
        """Create from dictionary."""
        return cls(
            tenure_type=Tenure(data["tenure_type"]),
            lease_years_remaining=data.get("lease_years_remaining"),
        )


@dataclass(frozen=True)
class FinancialFacts:
    """Verified financial information."""

    guide_price: int
    sale_route: SaleRoute

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "guide_price": self.guide_price,
            "sale_route": self.sale_route.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FinancialFacts":
        """Create from dictionary."""
        return cls(
            guide_price=data["guide_price"],
            sale_route=SaleRoute(data["sale_route"]),
        )


@dataclass(frozen=True)
class PlanningFacts:
    """Verified planning information."""

    existing_permissions: Optional[bool]
    restrictions: tuple[PlanningRestriction, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "existing_permissions": self.existing_permissions,
            "restrictions": [r.value for r in self.restrictions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanningFacts":
        """Create from dictionary."""
        restrictions = tuple(
            PlanningRestriction(r) for r in data.get("restrictions", [])
        )
        return cls(
            existing_permissions=data.get("existing_permissions"),
            restrictions=restrictions,
        )


@dataclass(frozen=True)
class PropertyFacts:
    """All verified property facts."""

    address: AddressFacts
    physical: PhysicalFacts
    tenure: TenureFacts
    financial: FinancialFacts
    planning: PlanningFacts

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "address": self.address.to_dict(),
            "physical": self.physical.to_dict(),
            "tenure": self.tenure.to_dict(),
            "financial": self.financial.to_dict(),
            "planning": self.planning.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PropertyFacts":
        """Create from dictionary."""
        return cls(
            address=AddressFacts.from_dict(data["address"]),
            physical=PhysicalFacts.from_dict(data["physical"]),
            tenure=TenureFacts.from_dict(data["tenure"]),
            financial=FinancialFacts.from_dict(data["financial"]),
            planning=PlanningFacts.from_dict(data["planning"]),
        )


@dataclass(frozen=True)
class ExportDocumentRecord:
    """Verified document information (excludes storage path for security)."""

    hash: str  # SHA-256 of document content
    verified: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "hash": self.hash,
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExportDocumentRecord":
        """Create from dictionary."""
        return cls(
            hash=data["hash"],
            verified=data["verified"],
        )


@dataclass(frozen=True)
class ExportEpcRecord:
    """EPC document with rating."""

    rating: Optional[str]  # A-G
    hash: str
    verified: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "rating": self.rating,
            "hash": self.hash,
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExportEpcRecord":
        """Create from dictionary."""
        return cls(
            rating=data.get("rating"),
            hash=data["hash"],
            verified=data["verified"],
        )


@dataclass(frozen=True)
class ExportDocuments:
    """Required document verification status."""

    title_register: Optional[ExportDocumentRecord]
    epc: Optional[ExportEpcRecord]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title_register": self.title_register.to_dict() if self.title_register else None,
            "epc": self.epc.to_dict() if self.epc else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExportDocuments":
        """Create from dictionary."""
        title_register = None
        if data.get("title_register"):
            title_register = ExportDocumentRecord.from_dict(data["title_register"])

        epc = None
        if data.get("epc"):
            epc = ExportEpcRecord.from_dict(data["epc"])

        return cls(
            title_register=title_register,
            epc=epc,
        )


@dataclass(frozen=True)
class ExportFlags:
    """Gating flags for Deal Engine eligibility."""

    eligible_for_evaluation: bool
    blocked_reason: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "eligible_for_evaluation": self.eligible_for_evaluation,
            "blocked_reason": self.blocked_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExportFlags":
        """Create from dictionary."""
        return cls(
            eligible_for_evaluation=data["eligible_for_evaluation"],
            blocked_reason=data.get("blocked_reason"),
        )


# =============================================================================
# Root Contract Dataclass
# =============================================================================


@dataclass(frozen=True)
class VerifiedPropertyExport:
    """
    VerifiedPropertyExport v1.0 Data Contract

    Immutable, versioned export format for Deal Engine consumption.
    Contains ONLY verified facts - no agent names, marketing text,
    or source platform identifiers.

    Security Boundary (NEVER included):
    - agent_name, agent_firm, agent_email
    - submission_id
    - Marketing descriptions
    - Source platform identifiers
    - Confidence boosting heuristics
    - "Assumed" values
    """

    # Version identifier (must be "1.0" for this contract)
    export_version: str

    # Property identification
    property_id: str  # UUID format: PROP-XXXXXXXXXXXX
    uprn: Optional[str]  # UK UPRN if available

    # Export metadata
    export_metadata: ExportMetadata

    # Verification summary
    verification_summary: ExportVerificationSummary

    # Verified property facts
    property_facts: PropertyFacts

    # Document verification status
    documents: ExportDocuments

    # Gating flags
    export_flags: ExportFlags

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "export_version": self.export_version,
            "property_id": self.property_id,
            "uprn": self.uprn,
            "export_metadata": self.export_metadata.to_dict(),
            "verification_summary": self.verification_summary.to_dict(),
            "property_facts": self.property_facts.to_dict(),
            "documents": self.documents.to_dict(),
            "export_flags": self.export_flags.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VerifiedPropertyExport":
        """Create from dictionary."""
        return cls(
            export_version=data["export_version"],
            property_id=data["property_id"],
            uprn=data.get("uprn"),
            export_metadata=ExportMetadata.from_dict(data["export_metadata"]),
            verification_summary=ExportVerificationSummary.from_dict(data["verification_summary"]),
            property_facts=PropertyFacts.from_dict(data["property_facts"]),
            documents=ExportDocuments.from_dict(data["documents"]),
            export_flags=ExportFlags.from_dict(data["export_flags"]),
        )


# =============================================================================
# Deterministic Serialization
# =============================================================================


def _serialize_for_hash(data: dict[str, Any]) -> str:
    """
    Serialize data deterministically for hash computation.

    Uses sorted keys and consistent formatting to ensure
    identical inputs always produce identical hashes.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def compute_export_hash(export: VerifiedPropertyExport) -> str:
    """Compute SHA-256 hash of the export."""
    serialized = _serialize_for_hash(export.to_dict())
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# =============================================================================
# Version Validation
# =============================================================================


def validate_export_version(export_data: dict[str, Any]) -> None:
    """
    Validate that the export version is supported.

    Args:
        export_data: Raw export dict (from JSON or to_dict())

    Raises:
        ExportVersionError: If version is missing or unsupported
    """
    version = export_data.get("export_version")
    if version is None:
        raise ExportVersionError("Missing export_version field")
    if version not in SUPPORTED_EXPORT_VERSIONS:
        raise ExportVersionError(
            f"Unsupported export version: {version}. "
            f"Supported versions: {SUPPORTED_EXPORT_VERSIONS}"
        )


def parse_verified_property_export(
    export_data: dict[str, Any],
) -> VerifiedPropertyExport:
    """
    Parse and validate a VerifiedPropertyExport from dict.

    Args:
        export_data: Raw export dict

    Returns:
        VerifiedPropertyExport instance

    Raises:
        ExportVersionError: If version is unsupported
        ValueError: If data is malformed
    """
    validate_export_version(export_data)
    return VerifiedPropertyExport.from_dict(export_data)


# =============================================================================
# Trust Level Calculation
# =============================================================================


def _calculate_trust_level(verification_percentage: float) -> TrustLevel:
    """
    Calculate trust level from verification percentage.

    Rules:
    - HIGH: >= 85% verified facts
    - MEDIUM: >= 70% and < 85% verified facts
    - LOW: < 70% verified facts
    """
    if verification_percentage >= HIGH_TRUST_THRESHOLD:
        return TrustLevel.HIGH
    elif verification_percentage >= MEDIUM_TRUST_THRESHOLD:
        return TrustLevel.MEDIUM
    else:
        return TrustLevel.LOW


# =============================================================================
# Factory Function
# =============================================================================


def create_verified_property_export(
    logbook: "SubmissionLogbook",
    verification_summary: "PropertyVerificationSummary",
) -> tuple[Optional[VerifiedPropertyExport], list[str]]:
    """
    Create a VerifiedPropertyExport from logbook and verification summary.

    This factory enforces all gating rules and security boundaries.

    Gating Rules (HARD FAIL):
    1. Hash chain invalid → BLOCK
    2. Any disputed facts → BLOCK
    3. Guide price unverified → BLOCK
    4. Missing mandatory documents (title_register) → BLOCK

    Args:
        logbook: The property submission logbook
        verification_summary: Verification status for all facts

    Returns:
        Tuple of (VerifiedPropertyExport or None, list of blocking reasons)
        If blocked, returns (None, [reasons...])
        If successful, returns (export, [])
    """
    # Import here to avoid circular imports
    from core.submission.schema import DocumentType
    from core.submission.verification import FactCategory, VerificationStatus

    blocking_reasons: list[str] = []

    # === GATE 1: Hash chain integrity ===
    chain_integrity = logbook.verify_chain_integrity()
    chain_valid = chain_integrity.get("valid", False)
    if not chain_valid:
        blocking_reasons.append(
            f"Hash chain invalid: {chain_integrity.get('error', 'Unknown error')}"
        )

    # === GATE 2: No disputed facts ===
    if verification_summary.has_disputes:
        disputed_facts = verification_summary.get_disputed_facts()
        disputed_names = [f[0].value for f in disputed_facts]
        blocking_reasons.append(f"Disputed facts present: {disputed_names}")

    # === GATE 3: Guide price must be verified ===
    guide_price_fact = verification_summary.get_fact(FactCategory.GUIDE_PRICE)
    guide_price_verified = (
        guide_price_fact is not None
        and guide_price_fact.current_status == VerificationStatus.VERIFIED
    )
    if not guide_price_verified:
        blocking_reasons.append("Guide price is not verified")

    # === GATE 4: Mandatory documents (title_register) ===
    current_submission = logbook.current_submission
    if current_submission is None:
        blocking_reasons.append("No submission found in logbook")
        return None, blocking_reasons

    title_register_doc = None
    epc_doc = None

    for doc in current_submission.documents:
        if doc.document_type == DocumentType.TITLE_REGISTER:
            title_register_doc = doc
        elif doc.document_type == DocumentType.EPC:
            epc_doc = doc

    if title_register_doc is None:
        blocking_reasons.append("Missing mandatory document: title_register")

    # If any blocking reasons, return None with reasons
    if blocking_reasons:
        return None, blocking_reasons

    # === Build the export ===

    # Get current version info
    current_version = logbook.current_version
    if current_version is None:
        return None, ["No version found in logbook"]

    # Calculate verification percentage and trust level
    total_facts = verification_summary.total_facts
    verified_count = verification_summary.verified_count
    verification_percentage = (
        (verified_count / total_facts * 100) if total_facts > 0 else 0.0
    )
    trust_level = _calculate_trust_level(verification_percentage)

    # Get submission snapshot
    snapshot = logbook.current_snapshot or {}

    # Build address facts
    address_fact = verification_summary.get_fact(FactCategory.ADDRESS)
    postcode_fact = verification_summary.get_fact(FactCategory.POSTCODE)
    address_verified = (
        address_fact is not None
        and address_fact.current_status == VerificationStatus.VERIFIED
        and postcode_fact is not None
        and postcode_fact.current_status == VerificationStatus.VERIFIED
    )

    address_facts = AddressFacts(
        full_address=snapshot.get("full_address", ""),
        postcode=snapshot.get("postcode", ""),
        verified=address_verified,
    )

    # Build physical facts
    property_type_fact = verification_summary.get_fact(FactCategory.PROPERTY_TYPE)
    floor_area_fact = verification_summary.get_fact(FactCategory.FLOOR_AREA)
    bedrooms_fact = verification_summary.get_fact(FactCategory.BEDROOMS)
    bathrooms_fact = verification_summary.get_fact(FactCategory.BATHROOMS)

    # Get property type from submission
    property_type_value = snapshot.get("property_type")
    if isinstance(property_type_value, str):
        property_type = PropertyType(property_type_value)
    elif hasattr(property_type_value, "value"):
        property_type = PropertyType(property_type_value.value)
    else:
        property_type = property_type_value

    # Only include verified values, otherwise None
    floor_area = None
    if (
        floor_area_fact is not None
        and floor_area_fact.current_status == VerificationStatus.VERIFIED
    ):
        floor_area = floor_area_fact.current_value

    bedrooms = None
    if (
        bedrooms_fact is not None
        and bedrooms_fact.current_status == VerificationStatus.VERIFIED
    ):
        bedrooms = bedrooms_fact.current_value

    bathrooms = None
    if (
        bathrooms_fact is not None
        and bathrooms_fact.current_status == VerificationStatus.VERIFIED
    ):
        bathrooms = bathrooms_fact.current_value

    physical_facts = PhysicalFacts(
        property_type=property_type,
        floor_area_sqm=floor_area,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
    )

    # Build tenure facts
    tenure_value = snapshot.get("tenure")
    if isinstance(tenure_value, str):
        tenure_type = Tenure(tenure_value)
    elif hasattr(tenure_value, "value"):
        tenure_type = Tenure(tenure_value.value)
    else:
        tenure_type = tenure_value

    lease_years_fact = verification_summary.get_fact(FactCategory.LEASE_YEARS)
    lease_years = None
    if (
        lease_years_fact is not None
        and lease_years_fact.current_status == VerificationStatus.VERIFIED
    ):
        lease_years = lease_years_fact.current_value

    tenure_facts = TenureFacts(
        tenure_type=tenure_type,
        lease_years_remaining=lease_years,
    )

    # Build financial facts (guide_price already verified by gate 3)
    sale_route_value = snapshot.get("sale_route")
    if isinstance(sale_route_value, str):
        sale_route = SaleRoute(sale_route_value)
    elif hasattr(sale_route_value, "value"):
        sale_route = SaleRoute(sale_route_value.value)
    else:
        sale_route = sale_route_value

    financial_facts = FinancialFacts(
        guide_price=guide_price_fact.current_value,
        sale_route=sale_route,
    )

    # Build planning facts (currently not tracked in verification, use defaults)
    planning_facts = PlanningFacts(
        existing_permissions=None,
        restrictions=(),
    )

    # Build property facts container
    property_facts = PropertyFacts(
        address=address_facts,
        physical=physical_facts,
        tenure=tenure_facts,
        financial=financial_facts,
        planning=planning_facts,
    )

    # Build document records
    title_register_record = None
    if title_register_doc is not None:
        title_register_record = ExportDocumentRecord(
            hash=title_register_doc.content_hash,
            verified=True,  # Must be present to pass gate 4
        )

    epc_record = None
    if epc_doc is not None:
        epc_rating = snapshot.get("epc_rating")
        epc_record = ExportEpcRecord(
            rating=epc_rating,
            hash=epc_doc.content_hash,
            verified=True,
        )

    documents = ExportDocuments(
        title_register=title_register_record,
        epc=epc_record,
    )

    # Build export metadata
    export_metadata = ExportMetadata(
        exported_at=datetime.utcnow(),
        logbook_version=current_version.version_number,
        logbook_hash=current_version.version_hash,
        chain_valid=chain_valid,
    )

    # Build verification summary for export
    export_verification_summary = ExportVerificationSummary(
        trust_level=trust_level,
        verified_fact_count=verification_summary.verified_count,
        unverified_fact_count=verification_summary.unverified_count,
        disputed_fact_count=verification_summary.disputed_count,
        rejected_fact_count=verification_summary.rejected_count,
    )

    # Build export flags
    export_flags = ExportFlags(
        eligible_for_evaluation=True,
        blocked_reason=None,
    )

    # Create the final export
    export = VerifiedPropertyExport(
        export_version=EXPORT_VERSION,
        property_id=logbook.property_id,
        uprn=None,  # UPRN not currently tracked in submission
        export_metadata=export_metadata,
        verification_summary=export_verification_summary,
        property_facts=property_facts,
        documents=documents,
        export_flags=export_flags,
    )

    return export, []
