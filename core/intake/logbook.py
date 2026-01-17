"""
Digital Property Logbook - Append-Only Audit Trail

Implements the Digital Property Logbook system owned by Axis.
All entries are append-only with no silent edits.

This is Step 2 of the Axis property intake process.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# =============================================================================
# Enums
# =============================================================================


class SubmittedBy(Enum):
    """Who submitted the logbook version."""

    SELLER = "seller"
    AGENT = "agent"
    AXIS = "axis"


class LogbookStatus(Enum):
    """Current status of the property in the logbook."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    ANALYSIS_COMPLETE = "analysis_complete"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


# =============================================================================
# Logbook Version
# =============================================================================


@dataclass(frozen=True)
class LogbookVersion:
    """
    Immutable snapshot of property data at a point in time.

    Each version captures the complete state of the property intake
    data and any Axis analysis. Versions are immutable - once created,
    they cannot be modified.

    Axis analysis must reference a specific version to ensure traceability.
    """

    # === IDENTITY ===
    version_id: str
    property_id: str
    version_number: int
    timestamp: datetime

    # === SUBMISSION INFO ===
    submitted_by: SubmittedBy

    # === IMMUTABLE SNAPSHOT ===
    # Complete copy of intake data at time of version creation
    intake_snapshot: dict[str, Any]

    # === AXIS ANALYSIS (optional - filled later) ===
    axis_analysis: Optional[dict[str, Any]] = None
    analysis_timestamp: Optional[datetime] = None
    analysed_by: Optional[str] = None

    # === NOTES ===
    notes: Optional[str] = None
    internal_notes: Optional[str] = None  # Axis internal only

    # === STATUS AT TIME OF VERSION ===
    status_at_version: LogbookStatus = LogbookStatus.DRAFT

    @classmethod
    def create(
        cls,
        property_id: str,
        version_number: int,
        submitted_by: SubmittedBy,
        intake_snapshot: dict[str, Any],
        notes: Optional[str] = None,
        status: LogbookStatus = LogbookStatus.DRAFT,
    ) -> "LogbookVersion":
        """
        Create a new logbook version.

        Args:
            property_id: UUID of the property
            version_number: Sequential version number (1-indexed)
            submitted_by: Who submitted this version
            intake_snapshot: Complete copy of intake data
            notes: Optional notes for this version
            status: Status at time of version creation

        Returns:
            New immutable LogbookVersion
        """
        version_id = f"{property_id}-v{version_number}"

        # Deep copy snapshot to ensure immutability
        snapshot_copy = copy.deepcopy(intake_snapshot)

        return cls(
            version_id=version_id,
            property_id=property_id,
            version_number=version_number,
            timestamp=datetime.utcnow(),
            submitted_by=submitted_by,
            intake_snapshot=snapshot_copy,
            notes=notes,
            status_at_version=status,
        )

    def with_analysis(
        self,
        analysis: dict[str, Any],
        analysed_by: str,
        internal_notes: Optional[str] = None,
    ) -> "LogbookVersion":
        """
        Create a new version with Axis analysis added.

        Note: This creates a NEW version, not modifying the existing one.
        The original version remains unchanged.

        Args:
            analysis: Axis analysis data
            analysed_by: Identifier of analyst
            internal_notes: Axis internal notes

        Returns:
            New LogbookVersion with analysis (new version_id)
        """
        # Analysis creates a new version, preserving the original
        new_version_number = self.version_number + 1
        new_version_id = f"{self.property_id}-v{new_version_number}"

        return LogbookVersion(
            version_id=new_version_id,
            property_id=self.property_id,
            version_number=new_version_number,
            timestamp=datetime.utcnow(),
            submitted_by=SubmittedBy.AXIS,
            intake_snapshot=copy.deepcopy(self.intake_snapshot),
            axis_analysis=copy.deepcopy(analysis),
            analysis_timestamp=datetime.utcnow(),
            analysed_by=analysed_by,
            notes=self.notes,
            internal_notes=internal_notes,
            status_at_version=LogbookStatus.ANALYSIS_COMPLETE,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert version to dictionary for serialisation."""
        return {
            "version_id": self.version_id,
            "property_id": self.property_id,
            "version_number": self.version_number,
            "timestamp": self.timestamp.isoformat(),
            "submitted_by": self.submitted_by.value,
            "intake_snapshot": self.intake_snapshot,
            "axis_analysis": self.axis_analysis,
            "analysis_timestamp": (
                self.analysis_timestamp.isoformat() if self.analysis_timestamp else None
            ),
            "analysed_by": self.analysed_by,
            "notes": self.notes,
            "internal_notes": self.internal_notes,
            "status_at_version": self.status_at_version.value,
        }


# =============================================================================
# Property Logbook
# =============================================================================


@dataclass
class PropertyLogbook:
    """
    Digital Property Logbook - Append-Only Audit Trail.

    The logbook maintains a complete history of all property data changes.
    All operations are append-only - no versions are ever deleted or modified.

    Rules:
    - Logbook entries are append-only
    - No silent edits
    - Axis analysis must reference a specific version
    - All changes create new versions

    Supports:
    - Viewing history
    - Viewing current state
    - Export for PDF generation
    """

    # === IDENTITY ===
    property_id: str
    created_at: datetime

    # === STATE ===
    current_status: LogbookStatus

    # === VERSION HISTORY (append-only) ===
    _versions: list[LogbookVersion] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        """Validate logbook state."""
        if not self.property_id:
            raise ValueError("property_id is required")

    @classmethod
    def create(cls, intake_snapshot: dict[str, Any], submitted_by: SubmittedBy) -> "PropertyLogbook":
        """
        Create a new property logbook with initial version.

        Args:
            intake_snapshot: Initial intake data
            submitted_by: Who submitted the initial data

        Returns:
            New PropertyLogbook with version 1
        """
        property_id = str(uuid.uuid4())
        now = datetime.utcnow()

        logbook = cls(
            property_id=property_id,
            created_at=now,
            current_status=LogbookStatus.SUBMITTED,
        )

        # Create initial version
        initial_version = LogbookVersion.create(
            property_id=property_id,
            version_number=1,
            submitted_by=submitted_by,
            intake_snapshot=intake_snapshot,
            status=LogbookStatus.SUBMITTED,
        )
        logbook._versions.append(initial_version)

        return logbook

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def versions(self) -> tuple[LogbookVersion, ...]:
        """
        Get all versions (read-only).

        Returns tuple to prevent external modification.
        """
        return tuple(self._versions)

    @property
    def version_count(self) -> int:
        """Get number of versions."""
        return len(self._versions)

    @property
    def current_version(self) -> Optional[LogbookVersion]:
        """Get the most recent version."""
        if not self._versions:
            return None
        return self._versions[-1]

    @property
    def current_snapshot(self) -> Optional[dict[str, Any]]:
        """Get the current intake snapshot."""
        current = self.current_version
        if current:
            return copy.deepcopy(current.intake_snapshot)
        return None

    @property
    def has_analysis(self) -> bool:
        """Check if any version has Axis analysis."""
        return any(v.axis_analysis is not None for v in self._versions)

    @property
    def latest_analysis(self) -> Optional[dict[str, Any]]:
        """Get the most recent Axis analysis."""
        for version in reversed(self._versions):
            if version.axis_analysis is not None:
                return copy.deepcopy(version.axis_analysis)
        return None

    # =========================================================================
    # Version Management (Append-Only)
    # =========================================================================

    def add_version(
        self,
        intake_snapshot: dict[str, Any],
        submitted_by: SubmittedBy,
        notes: Optional[str] = None,
        new_status: Optional[LogbookStatus] = None,
    ) -> LogbookVersion:
        """
        Add a new version to the logbook (append-only).

        Args:
            intake_snapshot: Updated intake data
            submitted_by: Who submitted this update
            notes: Optional notes for this version
            new_status: Optional status update

        Returns:
            The newly created version
        """
        next_version_number = len(self._versions) + 1
        status = new_status if new_status else self.current_status

        new_version = LogbookVersion.create(
            property_id=self.property_id,
            version_number=next_version_number,
            submitted_by=submitted_by,
            intake_snapshot=intake_snapshot,
            notes=notes,
            status=status,
        )

        self._versions.append(new_version)

        if new_status:
            self.current_status = new_status

        return new_version

    def add_analysis(
        self,
        analysis: dict[str, Any],
        analysed_by: str,
        internal_notes: Optional[str] = None,
    ) -> LogbookVersion:
        """
        Add Axis analysis as a new version.

        Analysis is always added as a new version, not modifying existing.
        This maintains the append-only audit trail.

        Args:
            analysis: Axis analysis data
            analysed_by: Identifier of analyst
            internal_notes: Axis internal notes

        Returns:
            The newly created version with analysis
        """
        if not self._versions:
            raise ValueError("Cannot add analysis to empty logbook")

        current = self.current_version
        assert current is not None  # Checked above

        # Create new version with analysis
        analysis_version = current.with_analysis(
            analysis=analysis,
            analysed_by=analysed_by,
            internal_notes=internal_notes,
        )

        self._versions.append(analysis_version)
        self.current_status = LogbookStatus.ANALYSIS_COMPLETE

        return analysis_version

    def update_status(
        self,
        new_status: LogbookStatus,
        notes: Optional[str] = None,
        updated_by: SubmittedBy = SubmittedBy.AXIS,
    ) -> LogbookVersion:
        """
        Update logbook status (creates new version).

        Status changes are recorded as new versions to maintain audit trail.

        Args:
            new_status: New status
            notes: Optional notes explaining status change
            updated_by: Who made the status change

        Returns:
            The newly created version
        """
        current = self.current_version
        if not current:
            raise ValueError("Cannot update status of empty logbook")

        # Create new version with same snapshot but new status
        return self.add_version(
            intake_snapshot=current.intake_snapshot,
            submitted_by=updated_by,
            notes=notes,
            new_status=new_status,
        )

    # =========================================================================
    # Version Retrieval
    # =========================================================================

    def get_version(self, version_number: int) -> Optional[LogbookVersion]:
        """
        Get a specific version by number.

        Args:
            version_number: Version number (1-indexed)

        Returns:
            LogbookVersion if found, None otherwise
        """
        if version_number < 1 or version_number > len(self._versions):
            return None
        return self._versions[version_number - 1]

    def get_version_by_id(self, version_id: str) -> Optional[LogbookVersion]:
        """
        Get a specific version by ID.

        Args:
            version_id: Version ID string

        Returns:
            LogbookVersion if found, None otherwise
        """
        for version in self._versions:
            if version.version_id == version_id:
                return version
        return None

    # =========================================================================
    # History & Export
    # =========================================================================

    def get_history(self) -> list[dict[str, Any]]:
        """
        Get complete version history for viewing.

        Returns list of version summaries ordered oldest to newest.
        """
        history = []
        for version in self._versions:
            history.append(
                {
                    "version_id": version.version_id,
                    "version_number": version.version_number,
                    "timestamp": version.timestamp.isoformat(),
                    "submitted_by": version.submitted_by.value,
                    "status": version.status_at_version.value,
                    "has_analysis": version.axis_analysis is not None,
                    "notes": version.notes,
                }
            )
        return history

    def export_for_pdf(self) -> dict[str, Any]:
        """
        Export logbook data for PDF generation.

        Returns complete logbook state suitable for report generation.
        """
        return {
            "property_id": self.property_id,
            "created_at": self.created_at.isoformat(),
            "current_status": self.current_status.value,
            "version_count": self.version_count,
            "current_snapshot": self.current_snapshot,
            "latest_analysis": self.latest_analysis,
            "history": self.get_history(),
            "all_versions": [v.to_dict() for v in self._versions],
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
