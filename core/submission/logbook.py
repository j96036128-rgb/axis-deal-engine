"""
Submission Logbook - Immutable Audit Trail for Property Submissions

Implements append-only versioning for property submissions with hash chain integrity.
New submissions create new versions - previous versions remain accessible.

Hash Chain Properties:
- Each version contains a SHA-256 hash of its content
- Each version references the hash of the previous version (forming a chain)
- Hash computation is deterministic (sorted keys, consistent serialization)
- Tampering with any version breaks the chain integrity
"""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from core.submission.schema import AgentSubmission, SubmissionStatus


# =============================================================================
# Hash Chain Utilities
# =============================================================================


def _serialize_for_hash(data: dict[str, Any]) -> str:
    """
    Serialize data deterministically for hash computation.

    Uses sorted keys and consistent formatting to ensure
    identical inputs always produce identical hashes.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def compute_version_hash(
    property_id: str,
    version_number: int,
    timestamp: datetime,
    action: str,
    action_by: str,
    action_note: Optional[str],
    submission_snapshot: dict[str, Any],
    status: str,
    previous_version_hash: Optional[str],
) -> str:
    """
    Compute SHA-256 hash for a submission version.

    The hash covers all version fields to ensure complete integrity.
    Including previous_version_hash creates the chain linkage.
    """
    hashable_content = {
        "property_id": property_id,
        "version_number": version_number,
        "timestamp": timestamp.isoformat(),
        "action": action,
        "action_by": action_by,
        "action_note": action_note,
        "submission_snapshot": submission_snapshot,
        "status": status,
        "previous_version_hash": previous_version_hash,
    }

    serialized = _serialize_for_hash(hashable_content)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def verify_hash_chain(versions: list["SubmissionVersion"]) -> dict[str, Any]:
    """
    Verify the integrity of a version hash chain.

    Returns:
        dict with:
            - valid: bool indicating if chain is intact
            - broken_at: version number where chain broke (if any)
            - error: description of the issue (if any)
    """
    if not versions:
        return {"valid": True, "broken_at": None, "error": None}

    # First version must have no previous hash
    if versions[0].previous_version_hash is not None:
        return {
            "valid": False,
            "broken_at": 1,
            "error": "First version has a previous_version_hash (should be None)",
        }

    for i, version in enumerate(versions):
        # Recompute hash
        expected_hash = compute_version_hash(
            property_id=version.property_id,
            version_number=version.version_number,
            timestamp=version.timestamp,
            action=version.action.value,
            action_by=version.action_by,
            action_note=version.action_note,
            submission_snapshot=version.submission_snapshot,
            status=version.status_at_version.value,
            previous_version_hash=version.previous_version_hash,
        )

        if version.version_hash != expected_hash:
            return {
                "valid": False,
                "broken_at": version.version_number,
                "error": f"Hash mismatch at version {version.version_number}",
            }

        # Verify chain linkage (version 2+ must reference previous hash)
        if i > 0:
            expected_previous = versions[i - 1].version_hash
            if version.previous_version_hash != expected_previous:
                return {
                    "valid": False,
                    "broken_at": version.version_number,
                    "error": f"Chain broken at version {version.version_number}: "
                             f"previous_version_hash does not match version {i} hash",
                }

    return {"valid": True, "broken_at": None, "error": None}


# =============================================================================
# Enums
# =============================================================================


class VersionAction(Enum):
    """Type of action that created this version."""

    INITIAL_SUBMISSION = "initial_submission"
    DOCUMENT_ADDED = "document_added"
    DOCUMENT_REPLACED = "document_replaced"
    FIELD_UPDATED = "field_updated"
    STATUS_CHANGED = "status_changed"
    AXIS_REVIEW = "axis_review"
    RESUBMISSION = "resubmission"


# =============================================================================
# Submission Version
# =============================================================================


@dataclass(frozen=True)
class SubmissionVersion:
    """
    Immutable snapshot of a submission at a point in time.

    Each version captures the complete state of the submission.
    Versions are immutable - once created, they cannot be modified.

    Hash Chain:
    - version_hash: SHA-256 hash of this version's content
    - previous_version_hash: Hash of the previous version (None for v1)
    - Together these form an append-only hash chain for integrity verification
    """

    # === IDENTITY ===
    version_id: str
    property_id: str
    version_number: int
    timestamp: datetime

    # === ACTION INFO ===
    action: VersionAction
    action_by: str  # Agent email or "axis_system"
    action_note: Optional[str]

    # === IMMUTABLE SNAPSHOT ===
    submission_snapshot: dict[str, Any]

    # === STATUS AT VERSION ===
    status_at_version: SubmissionStatus

    # === HASH CHAIN ===
    version_hash: str  # SHA-256 hash of this version
    previous_version_hash: Optional[str]  # Hash of previous version (None for v1)

    @classmethod
    def create(
        cls,
        property_id: str,
        version_number: int,
        action: VersionAction,
        action_by: str,
        submission_snapshot: dict[str, Any],
        action_note: Optional[str] = None,
        previous_version_hash: Optional[str] = None,
    ) -> "SubmissionVersion":
        """
        Create a new submission version with hash chain linkage.

        Args:
            property_id: Property ID
            version_number: Sequential version number (1-indexed)
            action: Type of action that created this version
            action_by: Who performed the action
            submission_snapshot: Complete copy of submission data
            action_note: Optional note explaining the action
            previous_version_hash: Hash of the previous version (None for v1)

        Returns:
            New immutable SubmissionVersion with computed hash
        """
        version_id = f"{property_id}-v{version_number}"

        # Extract status from snapshot
        status_str = submission_snapshot.get("status", "draft")
        status = SubmissionStatus(status_str)

        # Deep copy snapshot to ensure immutability
        snapshot_copy = copy.deepcopy(submission_snapshot)

        # Capture timestamp
        timestamp = datetime.utcnow()

        # Compute hash for this version
        version_hash = compute_version_hash(
            property_id=property_id,
            version_number=version_number,
            timestamp=timestamp,
            action=action.value,
            action_by=action_by,
            action_note=action_note,
            submission_snapshot=snapshot_copy,
            status=status.value,
            previous_version_hash=previous_version_hash,
        )

        return cls(
            version_id=version_id,
            property_id=property_id,
            version_number=version_number,
            timestamp=timestamp,
            action=action,
            action_by=action_by,
            action_note=action_note,
            submission_snapshot=snapshot_copy,
            status_at_version=status,
            version_hash=version_hash,
            previous_version_hash=previous_version_hash,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert version to dictionary for serialisation."""
        return {
            "version_id": self.version_id,
            "property_id": self.property_id,
            "version_number": self.version_number,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "action_by": self.action_by,
            "action_note": self.action_note,
            "submission_snapshot": self.submission_snapshot,
            "status_at_version": self.status_at_version.value,
            "version_hash": self.version_hash,
            "previous_version_hash": self.previous_version_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SubmissionVersion":
        """Create version from dictionary."""
        return cls(
            version_id=data["version_id"],
            property_id=data["property_id"],
            version_number=data["version_number"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            action=VersionAction(data["action"]),
            action_by=data["action_by"],
            action_note=data.get("action_note"),
            submission_snapshot=data["submission_snapshot"],
            status_at_version=SubmissionStatus(data["status_at_version"]),
            version_hash=data["version_hash"],
            previous_version_hash=data.get("previous_version_hash"),
        )

    def verify_hash(self) -> bool:
        """
        Verify this version's hash matches its content.

        Returns:
            True if hash is valid, False if tampered
        """
        expected_hash = compute_version_hash(
            property_id=self.property_id,
            version_number=self.version_number,
            timestamp=self.timestamp,
            action=self.action.value,
            action_by=self.action_by,
            action_note=self.action_note,
            submission_snapshot=self.submission_snapshot,
            status=self.status_at_version.value,
            previous_version_hash=self.previous_version_hash,
        )
        return self.version_hash == expected_hash


# =============================================================================
# Submission Logbook
# =============================================================================


@dataclass
class SubmissionLogbook:
    """
    Digital Property Logbook - Append-Only Audit Trail.

    Maintains complete history of all submission changes.
    All operations are append-only - no versions are ever deleted or modified.

    Rules:
    - Logbook entries are append-only
    - No silent edits
    - All changes create new versions
    - Previous versions remain accessible
    """

    # === IDENTITY ===
    property_id: str
    created_at: datetime

    # === CURRENT STATE ===
    current_status: SubmissionStatus

    # === VERSION HISTORY (append-only) ===
    _versions: list[SubmissionVersion] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        """Validate logbook state."""
        if not self.property_id:
            raise ValueError("property_id is required")

    @classmethod
    def create(
        cls,
        submission: AgentSubmission,
    ) -> "SubmissionLogbook":
        """
        Create a new submission logbook with initial version.

        Args:
            submission: Initial submission data

        Returns:
            New SubmissionLogbook with version 1
        """
        now = datetime.utcnow()

        # Update submission timestamp
        object.__setattr__(submission, "submitted_at", now)

        logbook = cls(
            property_id=submission.property_id,
            created_at=now,
            current_status=submission.status,
        )

        # Create initial version
        initial_version = SubmissionVersion.create(
            property_id=submission.property_id,
            version_number=1,
            action=VersionAction.INITIAL_SUBMISSION,
            action_by=submission.agent_email,
            submission_snapshot=submission.to_dict(),
        )
        logbook._versions.append(initial_version)

        return logbook

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def versions(self) -> tuple[SubmissionVersion, ...]:
        """Get all versions (read-only tuple)."""
        return tuple(self._versions)

    @property
    def version_count(self) -> int:
        """Get number of versions."""
        return len(self._versions)

    @property
    def current_version(self) -> Optional[SubmissionVersion]:
        """Get the most recent version."""
        if not self._versions:
            return None
        return self._versions[-1]

    @property
    def current_snapshot(self) -> Optional[dict[str, Any]]:
        """Get the current submission snapshot."""
        current = self.current_version
        if current:
            return copy.deepcopy(current.submission_snapshot)
        return None

    @property
    def current_submission(self) -> Optional[AgentSubmission]:
        """Get the current submission as an AgentSubmission object."""
        snapshot = self.current_snapshot
        if snapshot:
            return AgentSubmission.from_dict(snapshot)
        return None

    @property
    def current_hash(self) -> Optional[str]:
        """Get the hash of the current (latest) version."""
        current = self.current_version
        if current:
            return current.version_hash
        return None

    # =========================================================================
    # Version Management (Append-Only with Hash Chain)
    # =========================================================================

    def add_version(
        self,
        submission: AgentSubmission,
        action: VersionAction,
        action_by: str,
        action_note: Optional[str] = None,
    ) -> SubmissionVersion:
        """
        Add a new version to the logbook (append-only with hash chain).

        Args:
            submission: Updated submission data
            action: Type of action creating this version
            action_by: Who performed the action
            action_note: Optional note explaining the action

        Returns:
            The newly created version with hash chain linkage
        """
        next_version_number = len(self._versions) + 1

        # Get previous version hash for chain linkage
        previous_hash = self.current_hash

        new_version = SubmissionVersion.create(
            property_id=self.property_id,
            version_number=next_version_number,
            action=action,
            action_by=action_by,
            submission_snapshot=submission.to_dict(),
            action_note=action_note,
            previous_version_hash=previous_hash,
        )

        self._versions.append(new_version)
        self.current_status = submission.status

        return new_version

    def update_status(
        self,
        new_status: SubmissionStatus,
        action_by: str,
        action_note: Optional[str] = None,
    ) -> SubmissionVersion:
        """
        Update logbook status (creates new version).

        Args:
            new_status: New status
            action_by: Who made the status change
            action_note: Optional note explaining the change

        Returns:
            The newly created version
        """
        current = self.current_submission
        if not current:
            raise ValueError("Cannot update status of empty logbook")

        # Update status on submission
        object.__setattr__(current, "status", new_status)

        return self.add_version(
            submission=current,
            action=VersionAction.STATUS_CHANGED,
            action_by=action_by,
            action_note=action_note or f"Status changed to {new_status.value}",
        )

    # =========================================================================
    # Version Retrieval
    # =========================================================================

    def get_version(self, version_number: int) -> Optional[SubmissionVersion]:
        """
        Get a specific version by number.

        Args:
            version_number: Version number (1-indexed)

        Returns:
            SubmissionVersion if found, None otherwise
        """
        if version_number < 1 or version_number > len(self._versions):
            return None
        return self._versions[version_number - 1]

    def get_version_by_id(self, version_id: str) -> Optional[SubmissionVersion]:
        """Get a specific version by ID."""
        for version in self._versions:
            if version.version_id == version_id:
                return version
        return None

    def get_version_by_hash(self, version_hash: str) -> Optional[SubmissionVersion]:
        """Get a specific version by its hash."""
        for version in self._versions:
            if version.version_hash == version_hash:
                return version
        return None

    # =========================================================================
    # Hash Chain Verification
    # =========================================================================

    def verify_chain_integrity(self) -> dict[str, Any]:
        """
        Verify the integrity of the entire version hash chain.

        Returns:
            dict with:
                - valid: bool indicating if chain is intact
                - broken_at: version number where chain broke (if any)
                - error: description of the issue (if any)
                - version_count: number of versions checked
        """
        result = verify_hash_chain(list(self._versions))
        result["version_count"] = self.version_count
        return result

    def is_chain_valid(self) -> bool:
        """Quick check if hash chain is valid."""
        return self.verify_chain_integrity()["valid"]

    # =========================================================================
    # History & Export
    # =========================================================================

    def get_history(self) -> list[dict[str, Any]]:
        """
        Get complete version history for viewing.

        Returns list of version summaries ordered oldest to newest,
        including hash chain information.
        """
        history = []
        for version in self._versions:
            history.append({
                "version_id": version.version_id,
                "version_number": version.version_number,
                "timestamp": version.timestamp.isoformat(),
                "action": version.action.value,
                "action_by": version.action_by,
                "action_note": version.action_note,
                "status": version.status_at_version.value,
                "version_hash": version.version_hash,
                "previous_version_hash": version.previous_version_hash,
            })
        return history

    def get_completeness_check(self) -> dict[str, Any]:
        """
        Get completeness status for the current submission.

        Returns dict with status, missing items, and completeness flag.
        """
        current = self.current_submission
        if not current:
            return {
                "is_complete": False,
                "status": "no_submission",
                "missing_documents": [],
                "error": "No submission found",
            }

        return {
            "is_complete": current.is_complete,
            "status": current.status.value,
            "missing_documents": [dt.value for dt in current.missing_documents],
            "has_all_documents": current.has_all_required_documents,
            "document_count": len(current.documents),
            "required_document_count": len(current.required_document_types),
        }

    def export_for_deal_engine(
        self,
        verification_summary: Optional[dict[str, Any]] = None,
        require_verified: bool = True,
    ) -> dict[str, Any]:
        """
        Export logbook data for Deal Engine consumption (read-only).

        Returns complete submission data suitable for analysis,
        including hash chain integrity status.

        Args:
            verification_summary: Optional verification summary dict from PropertyVerificationSummary
            require_verified: If True, only include verified facts in the export

        Returns:
            Dict with submission data, integrity status, and verification info.
            If require_verified=True and integrity is broken, returns blocked=True.
        """
        current = self.current_snapshot
        chain_integrity = self.verify_chain_integrity()
        current_ver = self.current_version

        # Check if export should be blocked due to integrity failure
        blocked = False
        block_reason = None

        if not chain_integrity["valid"]:
            blocked = True
            block_reason = f"Hash chain integrity failure: {chain_integrity.get('error')}"

        # Build integrity section
        integrity = {
            "chain_valid": chain_integrity["valid"],
            "current_version_hash": current_ver.version_hash if current_ver else None,
            "verification_error": chain_integrity.get("error"),
        }

        # Build verification section
        verification = {
            "summary": verification_summary,
            "require_verified": require_verified,
        }

        if verification_summary:
            verification["verification_percentage"] = verification_summary.get("verification_percentage", 0)
            verification["has_disputes"] = verification_summary.get("has_disputes", False)
            verification["has_rejections"] = verification_summary.get("has_rejections", False)

            # Block if there are disputes or rejections
            if verification_summary.get("has_disputes"):
                blocked = True
                block_reason = block_reason or "Submission contains disputed facts"
            if verification_summary.get("has_rejections"):
                blocked = True
                block_reason = block_reason or "Submission contains rejected facts"

        return {
            "property_id": self.property_id,
            "created_at": self.created_at.isoformat(),
            "current_status": self.current_status.value,
            "version_count": self.version_count,
            "submission": current,
            "is_complete": current.get("is_complete", False) if current else False,
            "completeness": self.get_completeness_check(),
            "integrity": integrity,
            "verification": verification,
            # Deal Engine gating
            "blocked": blocked,
            "block_reason": block_reason,
            "ready_for_evaluation": not blocked and (current.get("is_complete", False) if current else False),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert logbook to dictionary for serialisation."""
        return {
            "property_id": self.property_id,
            "created_at": self.created_at.isoformat(),
            "current_status": self.current_status.value,
            "version_count": self.version_count,
            "versions": [v.to_dict() for v in self._versions],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SubmissionLogbook":
        """Create logbook from dictionary."""
        logbook = cls(
            property_id=data["property_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            current_status=SubmissionStatus(data["current_status"]),
        )

        # Restore versions
        for v_data in data.get("versions", []):
            version = SubmissionVersion.from_dict(v_data)
            logbook._versions.append(version)

        return logbook
