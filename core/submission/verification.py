"""
Fact Verification Model - Trust Status Tracking for Submission Facts

Implements verification status tracking for individual facts within submissions.
Each verifiable fact has its own verification state, creating a granular trust model.

Verification States:
- UNVERIFIED: Agent-claimed, no supporting evidence
- SUBMITTED: Document provided as evidence (awaiting verification)
- VERIFIED: Axis has confirmed accuracy against source documents
- DISPUTED: Conflict identified between claimed and verified values
- REJECTED: Verification failed, fact is unreliable

Principles:
- Facts are verified independently
- Verification status is immutable (new verification creates new record)
- Deal Engine only consumes VERIFIED facts for calculations
- All verification actions are audited
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Final, Optional


# =============================================================================
# Enums
# =============================================================================


class VerificationStatus(Enum):
    """Verification state for a fact or document."""

    UNVERIFIED = "unverified"  # Agent-claimed, no evidence
    SUBMITTED = "submitted"  # Evidence provided, awaiting verification
    VERIFIED = "verified"  # Confirmed by Axis
    DISPUTED = "disputed"  # Conflict identified
    REJECTED = "rejected"  # Verification failed


class VerificationSource(Enum):
    """Source of verification."""

    AGENT_CLAIM = "agent_claim"  # Agent's own assertion
    DOCUMENT = "document"  # Verified against uploaded document
    LAND_REGISTRY = "land_registry"  # Verified against Land Registry
    EPC_REGISTER = "epc_register"  # Verified against EPC register
    COUNCIL_RECORDS = "council_records"  # Verified against council
    AXIS_INSPECTION = "axis_inspection"  # Verified by Axis site visit
    THIRD_PARTY = "third_party"  # Verified by third party


class FactCategory(Enum):
    """Category of verifiable fact."""

    # Property identity
    ADDRESS = "address"
    POSTCODE = "postcode"

    # Structural facts
    PROPERTY_TYPE = "property_type"
    FLOOR_AREA = "floor_area"
    BEDROOMS = "bedrooms"
    BATHROOMS = "bathrooms"
    YEAR_BUILT = "year_built"

    # Legal facts
    TENURE = "tenure"
    LEASE_YEARS = "lease_years"
    GROUND_RENT = "ground_rent"
    SERVICE_CHARGE = "service_charge"

    # Valuation facts
    GUIDE_PRICE = "guide_price"
    COUNCIL_TAX_BAND = "council_tax_band"
    EPC_RATING = "epc_rating"


# =============================================================================
# Constants
# =============================================================================


# Facts that can be verified against Land Registry
LAND_REGISTRY_VERIFIABLE: Final[tuple[FactCategory, ...]] = (
    FactCategory.ADDRESS,
    FactCategory.POSTCODE,
    FactCategory.TENURE,
    FactCategory.PROPERTY_TYPE,  # Partial - via property description
)

# Facts that can be verified against EPC register
EPC_VERIFIABLE: Final[tuple[FactCategory, ...]] = (
    FactCategory.FLOOR_AREA,
    FactCategory.EPC_RATING,
    FactCategory.PROPERTY_TYPE,
)

# Facts that require document evidence
DOCUMENT_VERIFIABLE: Final[tuple[FactCategory, ...]] = (
    FactCategory.LEASE_YEARS,
    FactCategory.GROUND_RENT,
    FactCategory.SERVICE_CHARGE,
)

# Facts that are agent claims only (no external verification possible)
CLAIM_ONLY: Final[tuple[FactCategory, ...]] = (
    FactCategory.GUIDE_PRICE,  # Agent's valuation opinion
)


# =============================================================================
# Verification Record
# =============================================================================


@dataclass(frozen=True)
class VerificationRecord:
    """
    Immutable record of a fact verification action.

    Each verification attempt creates a new record.
    Records form an audit trail for the verification process.
    """

    # === IDENTITY ===
    verification_id: str
    property_id: str
    fact_category: FactCategory
    timestamp: datetime

    # === VERIFICATION STATE ===
    status: VerificationStatus
    previous_status: Optional[VerificationStatus]

    # === VALUES ===
    claimed_value: Any  # Value claimed by agent
    verified_value: Optional[Any]  # Value from verification source (if different)

    # === SOURCE ===
    source: VerificationSource
    source_document_id: Optional[str]  # Reference to supporting document
    source_reference: Optional[str]  # External reference (e.g., Land Registry title number)

    # === VERIFICATION ACTOR ===
    verified_by: str  # Who performed verification
    verification_note: Optional[str]

    # === INTEGRITY ===
    record_hash: str  # SHA-256 hash of this record

    @classmethod
    def create(
        cls,
        property_id: str,
        fact_category: FactCategory,
        status: VerificationStatus,
        claimed_value: Any,
        source: VerificationSource,
        verified_by: str,
        previous_status: Optional[VerificationStatus] = None,
        verified_value: Optional[Any] = None,
        source_document_id: Optional[str] = None,
        source_reference: Optional[str] = None,
        verification_note: Optional[str] = None,
    ) -> "VerificationRecord":
        """Create a new verification record with computed hash."""
        verification_id = f"VER-{uuid.uuid4().hex[:12].upper()}"
        timestamp = datetime.utcnow()

        # Compute hash
        hash_content = {
            "verification_id": verification_id,
            "property_id": property_id,
            "fact_category": fact_category.value,
            "timestamp": timestamp.isoformat(),
            "status": status.value,
            "previous_status": previous_status.value if previous_status else None,
            "claimed_value": claimed_value,
            "verified_value": verified_value,
            "source": source.value,
            "source_document_id": source_document_id,
            "source_reference": source_reference,
            "verified_by": verified_by,
            "verification_note": verification_note,
        }
        serialized = json.dumps(hash_content, sort_keys=True, separators=(",", ":"), default=str)
        record_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        return cls(
            verification_id=verification_id,
            property_id=property_id,
            fact_category=fact_category,
            timestamp=timestamp,
            status=status,
            previous_status=previous_status,
            claimed_value=claimed_value,
            verified_value=verified_value,
            source=source,
            source_document_id=source_document_id,
            source_reference=source_reference,
            verified_by=verified_by,
            verification_note=verification_note,
            record_hash=record_hash,
        )

    @property
    def is_verified(self) -> bool:
        """Check if this fact is verified."""
        return self.status == VerificationStatus.VERIFIED

    @property
    def is_disputed(self) -> bool:
        """Check if this fact is disputed."""
        return self.status == VerificationStatus.DISPUTED

    @property
    def is_usable(self) -> bool:
        """Check if this fact can be used by Deal Engine."""
        return self.status == VerificationStatus.VERIFIED

    @property
    def value_mismatch(self) -> bool:
        """Check if claimed and verified values differ."""
        if self.verified_value is None:
            return False
        return self.claimed_value != self.verified_value

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialisation."""
        return {
            "verification_id": self.verification_id,
            "property_id": self.property_id,
            "fact_category": self.fact_category.value,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "previous_status": self.previous_status.value if self.previous_status else None,
            "claimed_value": self.claimed_value,
            "verified_value": self.verified_value,
            "source": self.source.value,
            "source_document_id": self.source_document_id,
            "source_reference": self.source_reference,
            "verified_by": self.verified_by,
            "verification_note": self.verification_note,
            "record_hash": self.record_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VerificationRecord":
        """Create from dictionary."""
        return cls(
            verification_id=data["verification_id"],
            property_id=data["property_id"],
            fact_category=FactCategory(data["fact_category"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            status=VerificationStatus(data["status"]),
            previous_status=VerificationStatus(data["previous_status"]) if data.get("previous_status") else None,
            claimed_value=data["claimed_value"],
            verified_value=data.get("verified_value"),
            source=VerificationSource(data["source"]),
            source_document_id=data.get("source_document_id"),
            source_reference=data.get("source_reference"),
            verified_by=data["verified_by"],
            verification_note=data.get("verification_note"),
            record_hash=data["record_hash"],
        )


# =============================================================================
# Fact Verification State
# =============================================================================


@dataclass
class FactVerificationState:
    """
    Current verification state for a single fact.

    Tracks the latest verification status and complete history.
    """

    property_id: str
    fact_category: FactCategory
    current_status: VerificationStatus
    current_value: Any  # The value to use (verified_value if available, else claimed)
    claimed_value: Any
    verified_value: Optional[Any]

    # Verification history (append-only)
    _history: list[VerificationRecord] = field(default_factory=list, repr=False)

    @classmethod
    def create_unverified(
        cls,
        property_id: str,
        fact_category: FactCategory,
        claimed_value: Any,
        agent_email: str,
    ) -> "FactVerificationState":
        """Create initial unverified fact state."""
        state = cls(
            property_id=property_id,
            fact_category=fact_category,
            current_status=VerificationStatus.UNVERIFIED,
            current_value=claimed_value,
            claimed_value=claimed_value,
            verified_value=None,
        )

        # Create initial verification record
        initial_record = VerificationRecord.create(
            property_id=property_id,
            fact_category=fact_category,
            status=VerificationStatus.UNVERIFIED,
            claimed_value=claimed_value,
            source=VerificationSource.AGENT_CLAIM,
            verified_by=agent_email,
            verification_note="Initial submission - agent claim",
        )
        state._history.append(initial_record)

        return state

    @property
    def history(self) -> tuple[VerificationRecord, ...]:
        """Get verification history (read-only)."""
        return tuple(self._history)

    @property
    def latest_record(self) -> Optional[VerificationRecord]:
        """Get the most recent verification record."""
        if not self._history:
            return None
        return self._history[-1]

    @property
    def is_verified(self) -> bool:
        """Check if fact is verified."""
        return self.current_status == VerificationStatus.VERIFIED

    @property
    def is_disputed(self) -> bool:
        """Check if fact is disputed."""
        return self.current_status == VerificationStatus.DISPUTED

    @property
    def is_rejected(self) -> bool:
        """Check if fact is rejected."""
        return self.current_status == VerificationStatus.REJECTED

    @property
    def value_mismatch(self) -> bool:
        """Check if claimed and verified values differ."""
        if self.verified_value is None:
            return False
        return self.claimed_value != self.verified_value

    @property
    def is_usable_by_deal_engine(self) -> bool:
        """Check if this fact can be used for Deal Engine calculations."""
        return self.current_status == VerificationStatus.VERIFIED

    def verify(
        self,
        verified_value: Any,
        source: VerificationSource,
        verified_by: str,
        source_document_id: Optional[str] = None,
        source_reference: Optional[str] = None,
        verification_note: Optional[str] = None,
    ) -> VerificationRecord:
        """
        Mark fact as verified.

        Args:
            verified_value: Value confirmed by verification source
            source: Source of verification
            verified_by: Who performed verification
            source_document_id: Reference to supporting document
            source_reference: External reference
            verification_note: Optional note

        Returns:
            New VerificationRecord
        """
        record = VerificationRecord.create(
            property_id=self.property_id,
            fact_category=self.fact_category,
            status=VerificationStatus.VERIFIED,
            claimed_value=self.claimed_value,
            source=source,
            verified_by=verified_by,
            previous_status=self.current_status,
            verified_value=verified_value,
            source_document_id=source_document_id,
            source_reference=source_reference,
            verification_note=verification_note,
        )

        self._history.append(record)
        self.current_status = VerificationStatus.VERIFIED
        self.verified_value = verified_value
        self.current_value = verified_value  # Use verified value

        return record

    def dispute(
        self,
        disputed_value: Any,
        source: VerificationSource,
        verified_by: str,
        source_document_id: Optional[str] = None,
        source_reference: Optional[str] = None,
        verification_note: Optional[str] = None,
    ) -> VerificationRecord:
        """
        Mark fact as disputed (conflict between claimed and source value).

        Args:
            disputed_value: Value from verification source that conflicts
            source: Source of verification
            verified_by: Who identified the dispute
            source_document_id: Reference to supporting document
            source_reference: External reference
            verification_note: Note explaining the dispute

        Returns:
            New VerificationRecord
        """
        record = VerificationRecord.create(
            property_id=self.property_id,
            fact_category=self.fact_category,
            status=VerificationStatus.DISPUTED,
            claimed_value=self.claimed_value,
            source=source,
            verified_by=verified_by,
            previous_status=self.current_status,
            verified_value=disputed_value,
            source_document_id=source_document_id,
            source_reference=source_reference,
            verification_note=verification_note or "Value conflict identified",
        )

        self._history.append(record)
        self.current_status = VerificationStatus.DISPUTED
        self.verified_value = disputed_value
        # Keep current_value as claimed until resolved

        return record

    def reject(
        self,
        verified_by: str,
        verification_note: str,
        source: VerificationSource = VerificationSource.AXIS_INSPECTION,
    ) -> VerificationRecord:
        """
        Reject fact verification.

        Args:
            verified_by: Who rejected the fact
            verification_note: Reason for rejection
            source: Source of rejection decision

        Returns:
            New VerificationRecord
        """
        record = VerificationRecord.create(
            property_id=self.property_id,
            fact_category=self.fact_category,
            status=VerificationStatus.REJECTED,
            claimed_value=self.claimed_value,
            source=source,
            verified_by=verified_by,
            previous_status=self.current_status,
            verification_note=verification_note,
        )

        self._history.append(record)
        self.current_status = VerificationStatus.REJECTED

        return record

    def mark_document_submitted(
        self,
        document_id: str,
        verified_by: str,
        verification_note: Optional[str] = None,
    ) -> VerificationRecord:
        """
        Mark fact as having document evidence submitted.

        Args:
            document_id: ID of the supporting document
            verified_by: Who uploaded the document
            verification_note: Optional note

        Returns:
            New VerificationRecord
        """
        record = VerificationRecord.create(
            property_id=self.property_id,
            fact_category=self.fact_category,
            status=VerificationStatus.SUBMITTED,
            claimed_value=self.claimed_value,
            source=VerificationSource.DOCUMENT,
            verified_by=verified_by,
            previous_status=self.current_status,
            source_document_id=document_id,
            verification_note=verification_note or "Document evidence submitted",
        )

        self._history.append(record)
        self.current_status = VerificationStatus.SUBMITTED

        return record

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialisation."""
        return {
            "property_id": self.property_id,
            "fact_category": self.fact_category.value,
            "current_status": self.current_status.value,
            "current_value": self.current_value,
            "claimed_value": self.claimed_value,
            "verified_value": self.verified_value,
            "history": [r.to_dict() for r in self._history],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FactVerificationState":
        """Create from dictionary."""
        state = cls(
            property_id=data["property_id"],
            fact_category=FactCategory(data["fact_category"]),
            current_status=VerificationStatus(data["current_status"]),
            current_value=data["current_value"],
            claimed_value=data["claimed_value"],
            verified_value=data.get("verified_value"),
        )

        for record_data in data.get("history", []):
            record = VerificationRecord.from_dict(record_data)
            state._history.append(record)

        return state


# =============================================================================
# Property Verification Summary
# =============================================================================


@dataclass
class PropertyVerificationSummary:
    """
    Aggregated verification status for a property.

    Provides summary statistics and fact-level verification states.
    """

    property_id: str
    facts: dict[FactCategory, FactVerificationState] = field(default_factory=dict)

    @property
    def total_facts(self) -> int:
        """Total number of tracked facts."""
        return len(self.facts)

    @property
    def verified_count(self) -> int:
        """Number of verified facts."""
        return sum(1 for f in self.facts.values() if f.is_verified)

    @property
    def unverified_count(self) -> int:
        """Number of unverified facts."""
        return sum(1 for f in self.facts.values() if f.current_status == VerificationStatus.UNVERIFIED)

    @property
    def disputed_count(self) -> int:
        """Number of disputed facts."""
        return sum(1 for f in self.facts.values() if f.current_status == VerificationStatus.DISPUTED)

    @property
    def submitted_count(self) -> int:
        """Number of facts with documents submitted (awaiting verification)."""
        return sum(1 for f in self.facts.values() if f.current_status == VerificationStatus.SUBMITTED)

    @property
    def rejected_count(self) -> int:
        """Number of rejected facts."""
        return sum(1 for f in self.facts.values() if f.current_status == VerificationStatus.REJECTED)

    @property
    def verification_percentage(self) -> float:
        """Percentage of facts that are verified."""
        if self.total_facts == 0:
            return 0.0
        return (self.verified_count / self.total_facts) * 100

    @property
    def is_fully_verified(self) -> bool:
        """Check if all facts are verified."""
        return self.verified_count == self.total_facts and self.total_facts > 0

    @property
    def has_disputes(self) -> bool:
        """Check if any facts are disputed."""
        return self.disputed_count > 0

    @property
    def has_rejections(self) -> bool:
        """Check if any facts are rejected."""
        return self.rejected_count > 0

    def get_verified_facts(self) -> dict[FactCategory, Any]:
        """
        Get only verified facts (for Deal Engine consumption).

        Returns dict of fact category to verified value.
        Only includes facts with VERIFIED status.
        """
        return {
            cat: state.current_value
            for cat, state in self.facts.items()
            if state.is_verified
        }

    def get_unverified_facts(self) -> list[FactCategory]:
        """Get list of unverified fact categories."""
        return [
            cat for cat, state in self.facts.items()
            if state.current_status == VerificationStatus.UNVERIFIED
        ]

    def get_disputed_facts(self) -> list[tuple[FactCategory, Any, Any]]:
        """
        Get list of disputed facts with claimed and verified values.

        Returns list of (category, claimed_value, verified_value) tuples.
        """
        return [
            (cat, state.claimed_value, state.verified_value)
            for cat, state in self.facts.items()
            if state.current_status == VerificationStatus.DISPUTED
        ]

    def add_fact(
        self,
        fact_category: FactCategory,
        claimed_value: Any,
        agent_email: str,
    ) -> FactVerificationState:
        """
        Add a new fact to track (starts as UNVERIFIED).

        Args:
            fact_category: Category of the fact
            claimed_value: Value claimed by agent
            agent_email: Agent's email

        Returns:
            New FactVerificationState
        """
        state = FactVerificationState.create_unverified(
            property_id=self.property_id,
            fact_category=fact_category,
            claimed_value=claimed_value,
            agent_email=agent_email,
        )
        self.facts[fact_category] = state
        return state

    def get_fact(self, fact_category: FactCategory) -> Optional[FactVerificationState]:
        """Get verification state for a specific fact."""
        return self.facts.get(fact_category)

    def to_summary_dict(self) -> dict[str, Any]:
        """Get summary statistics as dict."""
        return {
            "property_id": self.property_id,
            "total_facts": self.total_facts,
            "verified_count": self.verified_count,
            "unverified_count": self.unverified_count,
            "submitted_count": self.submitted_count,
            "disputed_count": self.disputed_count,
            "rejected_count": self.rejected_count,
            "verification_percentage": round(self.verification_percentage, 1),
            "is_fully_verified": self.is_fully_verified,
            "has_disputes": self.has_disputes,
            "has_rejections": self.has_rejections,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialisation."""
        return {
            "property_id": self.property_id,
            "facts": {cat.value: state.to_dict() for cat, state in self.facts.items()},
            "summary": self.to_summary_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PropertyVerificationSummary":
        """Create from dictionary."""
        summary = cls(property_id=data["property_id"])

        for cat_str, state_data in data.get("facts", {}).items():
            state = FactVerificationState.from_dict(state_data)
            summary.facts[FactCategory(cat_str)] = state

        return summary


# =============================================================================
# Factory Functions
# =============================================================================


def create_verification_summary_from_submission(
    property_id: str,
    submission_data: dict[str, Any],
    agent_email: str,
) -> PropertyVerificationSummary:
    """
    Create a PropertyVerificationSummary from submission data.

    Extracts all verifiable facts from the submission and creates
    initial UNVERIFIED states for each.

    Args:
        property_id: Property ID
        submission_data: Submission data dict
        agent_email: Agent's email

    Returns:
        PropertyVerificationSummary with all facts in UNVERIFIED state
    """
    summary = PropertyVerificationSummary(property_id=property_id)

    # Map submission fields to fact categories
    field_mapping = {
        "full_address": FactCategory.ADDRESS,
        "postcode": FactCategory.POSTCODE,
        "property_type": FactCategory.PROPERTY_TYPE,
        "tenure": FactCategory.TENURE,
        "floor_area_sqm": FactCategory.FLOOR_AREA,
        "guide_price": FactCategory.GUIDE_PRICE,
        "bedrooms": FactCategory.BEDROOMS,
        "bathrooms": FactCategory.BATHROOMS,
        "year_built": FactCategory.YEAR_BUILT,
        "council_tax_band": FactCategory.COUNCIL_TAX_BAND,
        "epc_rating": FactCategory.EPC_RATING,
        "lease_years_remaining": FactCategory.LEASE_YEARS,
        "ground_rent_annual": FactCategory.GROUND_RENT,
        "service_charge_annual": FactCategory.SERVICE_CHARGE,
    }

    for field_name, fact_category in field_mapping.items():
        value = submission_data.get(field_name)
        if value is not None:
            summary.add_fact(
                fact_category=fact_category,
                claimed_value=value,
                agent_email=agent_email,
            )

    return summary


# =============================================================================
# Deal Engine Gating Functions
# =============================================================================


@dataclass
class DealEngineGatingResult:
    """
    Result of checking if a submission is ready for Deal Engine evaluation.

    The Deal Engine should ONLY evaluate submissions that pass these gates:
    1. Hash chain integrity is valid (no tampering)
    2. No disputed or rejected facts
    3. Submission is complete (all required documents)
    """

    can_evaluate: bool
    reasons: list[str]
    verified_facts: dict[str, Any]  # Only facts with VERIFIED status
    unverified_facts: list[str]  # Fact categories that are not verified
    integrity_valid: bool
    has_disputes: bool
    has_rejections: bool

    @classmethod
    def blocked(cls, reason: str) -> "DealEngineGatingResult":
        """Create a blocked result with a single reason."""
        return cls(
            can_evaluate=False,
            reasons=[reason],
            verified_facts={},
            unverified_facts=[],
            integrity_valid=False,
            has_disputes=False,
            has_rejections=False,
        )


def check_deal_engine_readiness(
    chain_integrity: dict[str, Any],
    verification_summary: PropertyVerificationSummary,
    submission_complete: bool,
    require_full_verification: bool = False,
) -> DealEngineGatingResult:
    """
    Check if a submission is ready for Deal Engine evaluation.

    This function implements the verification gating logic that ensures
    the Deal Engine only processes trusted, verifiable data.

    Args:
        chain_integrity: Result from logbook.verify_chain_integrity()
        verification_summary: PropertyVerificationSummary for the submission
        submission_complete: Whether all required documents are uploaded
        require_full_verification: If True, require 100% verification

    Returns:
        DealEngineGatingResult with evaluation readiness and verified facts
    """
    reasons = []
    can_evaluate = True

    # Gate 1: Hash chain integrity
    integrity_valid = chain_integrity.get("valid", False)
    if not integrity_valid:
        can_evaluate = False
        reasons.append(f"Hash chain integrity failure: {chain_integrity.get('error', 'Unknown')}")

    # Gate 2: No disputes
    has_disputes = verification_summary.has_disputes
    if has_disputes:
        can_evaluate = False
        disputed = verification_summary.get_disputed_facts()
        reasons.append(f"Disputed facts: {[d[0].value for d in disputed]}")

    # Gate 3: No rejections
    has_rejections = verification_summary.has_rejections
    if has_rejections:
        can_evaluate = False
        reasons.append("Contains rejected facts that cannot be trusted")

    # Gate 4: Submission completeness
    if not submission_complete:
        can_evaluate = False
        reasons.append("Submission incomplete - missing required documents")

    # Gate 5: Full verification (if required)
    if require_full_verification and not verification_summary.is_fully_verified:
        can_evaluate = False
        unverified = verification_summary.get_unverified_facts()
        reasons.append(f"Not fully verified: {[u.value for u in unverified]}")

    # Extract verified facts (only facts with VERIFIED status)
    verified_facts = {}
    unverified_facts = []

    for category, state in verification_summary.facts.items():
        if state.is_verified:
            verified_facts[category.value] = state.current_value
        else:
            unverified_facts.append(category.value)

    return DealEngineGatingResult(
        can_evaluate=can_evaluate,
        reasons=reasons,
        verified_facts=verified_facts,
        unverified_facts=unverified_facts,
        integrity_valid=integrity_valid,
        has_disputes=has_disputes,
        has_rejections=has_rejections,
    )


def extract_verified_submission_data(
    submission_data: dict[str, Any],
    verification_summary: PropertyVerificationSummary,
) -> dict[str, Any]:
    """
    Extract only verified facts from submission data.

    This creates a "sanitized" version of the submission that only includes
    facts that have been verified. Unverified facts are set to None.

    Args:
        submission_data: Full submission data dict
        verification_summary: PropertyVerificationSummary with verification states

    Returns:
        Submission data dict with unverified facts set to None
    """
    # Map fact categories back to submission field names
    category_to_field = {
        FactCategory.ADDRESS: "full_address",
        FactCategory.POSTCODE: "postcode",
        FactCategory.PROPERTY_TYPE: "property_type",
        FactCategory.TENURE: "tenure",
        FactCategory.FLOOR_AREA: "floor_area_sqm",
        FactCategory.GUIDE_PRICE: "guide_price",
        FactCategory.BEDROOMS: "bedrooms",
        FactCategory.BATHROOMS: "bathrooms",
        FactCategory.YEAR_BUILT: "year_built",
        FactCategory.COUNCIL_TAX_BAND: "council_tax_band",
        FactCategory.EPC_RATING: "epc_rating",
        FactCategory.LEASE_YEARS: "lease_years_remaining",
        FactCategory.GROUND_RENT: "ground_rent_annual",
        FactCategory.SERVICE_CHARGE: "service_charge_annual",
    }

    # Create a copy of the submission data
    verified_data = submission_data.copy()

    # For each verifiable field, check if it's verified
    for category, field_name in category_to_field.items():
        fact_state = verification_summary.get_fact(category)

        if fact_state is None or not fact_state.is_verified:
            # Set unverified facts to None (Deal Engine should not use them)
            verified_data[field_name] = None
        else:
            # Use the verified value (may differ from claimed)
            verified_data[field_name] = fact_state.current_value

    # Add verification metadata
    verified_data["_verification"] = {
        "verified_fact_count": verification_summary.verified_count,
        "total_fact_count": verification_summary.total_facts,
        "verification_percentage": verification_summary.verification_percentage,
        "is_fully_verified": verification_summary.is_fully_verified,
    }

    return verified_data
