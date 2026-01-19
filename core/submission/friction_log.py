"""
Friction Log - Internal Feedback Capture for Admin

Captures structured data about where agents struggle during submission.
Used to guide copy improvements and training without changing requirements.

This is internal only - not visible to agents.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Final, Optional


# =============================================================================
# Constants
# =============================================================================

FRICTION_LOG_DIR: Final = Path("data/friction_logs")
FRICTION_CATEGORIES: Final[tuple[str, ...]] = (
    "document_upload",      # Agent struggled with document upload
    "field_confusion",      # Agent confused about a field
    "validation_error",     # Agent hit repeated validation errors
    "flow_navigation",      # Agent couldn't find next step
    "format_mismatch",      # Agent submitted wrong format
    "leasehold_fields",     # Specific to leasehold requirements
    "timing_delay",         # Step took too long
    "abandonment",          # Agent abandoned mid-flow
    "other",                # General friction
)


# =============================================================================
# Friction Entry
# =============================================================================


@dataclass
class FrictionEntry:
    """
    Single friction observation recorded by admin.

    Captures what happened, where, and potential cause.
    """

    entry_id: str
    property_id: Optional[str]  # May be null if friction happened before submission
    category: str
    description: str  # What happened
    step_location: str  # Where in the flow
    potential_cause: str  # Admin's assessment
    recorded_by: str  # Admin email
    recorded_at: datetime
    agent_email: Optional[str] = None  # Agent who experienced friction
    severity: str = "medium"  # low, medium, high

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialisation."""
        return {
            "entry_id": self.entry_id,
            "property_id": self.property_id,
            "category": self.category,
            "description": self.description,
            "step_location": self.step_location,
            "potential_cause": self.potential_cause,
            "recorded_by": self.recorded_by,
            "recorded_at": self.recorded_at.isoformat(),
            "agent_email": self.agent_email,
            "severity": self.severity,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FrictionEntry":
        """Create from dictionary."""
        return cls(
            entry_id=data["entry_id"],
            property_id=data.get("property_id"),
            category=data["category"],
            description=data["description"],
            step_location=data["step_location"],
            potential_cause=data["potential_cause"],
            recorded_by=data["recorded_by"],
            recorded_at=datetime.fromisoformat(data["recorded_at"]),
            agent_email=data.get("agent_email"),
            severity=data.get("severity", "medium"),
        )


# =============================================================================
# Friction Log Repository
# =============================================================================


class FrictionLogRepository:
    """
    Simple JSON-based friction log storage.

    Stores friction entries in a daily log file for easy review.
    """

    def __init__(self, base_dir: Path = FRICTION_LOG_DIR):
        self._base_dir = base_dir
        self._ensure_dir()
        self._entry_counter = 0

    def _ensure_dir(self) -> None:
        """Create log directory if needed."""
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _get_today_file(self) -> Path:
        """Get path to today's log file."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return self._base_dir / f"friction_{today}.json"

    def _load_today_entries(self) -> list[dict]:
        """Load entries from today's log file."""
        log_file = self._get_today_file()
        if log_file.exists():
            with open(log_file, "r") as f:
                return json.load(f)
        return []

    def _save_today_entries(self, entries: list[dict]) -> None:
        """Save entries to today's log file."""
        log_file = self._get_today_file()
        with open(log_file, "w") as f:
            json.dump(entries, f, indent=2)

    def add_entry(
        self,
        category: str,
        description: str,
        step_location: str,
        potential_cause: str,
        recorded_by: str,
        property_id: Optional[str] = None,
        agent_email: Optional[str] = None,
        severity: str = "medium",
    ) -> FrictionEntry:
        """
        Add a new friction entry.

        Args:
            category: Category from FRICTION_CATEGORIES
            description: What happened
            step_location: Where in the flow
            potential_cause: Admin's assessment of why
            recorded_by: Admin email
            property_id: Optional property ID if known
            agent_email: Optional agent email if known
            severity: low, medium, or high

        Returns:
            Created FrictionEntry
        """
        if category not in FRICTION_CATEGORIES:
            raise ValueError(f"Invalid category: {category}. Must be one of {FRICTION_CATEGORIES}")

        if severity not in ("low", "medium", "high"):
            raise ValueError(f"Invalid severity: {severity}. Must be low, medium, or high")

        # Generate entry ID
        self._entry_counter += 1
        now = datetime.utcnow()
        entry_id = f"FRIC-{now.strftime('%Y%m%d')}-{self._entry_counter:04d}"

        entry = FrictionEntry(
            entry_id=entry_id,
            property_id=property_id,
            category=category,
            description=description,
            step_location=step_location,
            potential_cause=potential_cause,
            recorded_by=recorded_by,
            recorded_at=now,
            agent_email=agent_email,
            severity=severity,
        )

        # Append to today's log
        entries = self._load_today_entries()
        entries.append(entry.to_dict())
        self._save_today_entries(entries)

        return entry

    def get_today_entries(self) -> list[FrictionEntry]:
        """Get all entries from today."""
        entries = self._load_today_entries()
        return [FrictionEntry.from_dict(e) for e in entries]

    def get_entries_by_date(self, date_str: str) -> list[FrictionEntry]:
        """Get entries for a specific date (YYYY-MM-DD)."""
        log_file = self._base_dir / f"friction_{date_str}.json"
        if not log_file.exists():
            return []

        with open(log_file, "r") as f:
            entries = json.load(f)

        return [FrictionEntry.from_dict(e) for e in entries]

    def get_recent_entries(self, days: int = 7) -> list[FrictionEntry]:
        """Get entries from the last N days."""
        from datetime import timedelta

        all_entries = []
        for i in range(days):
            date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            all_entries.extend(self.get_entries_by_date(date))

        # Sort by recorded_at descending
        all_entries.sort(key=lambda e: e.recorded_at, reverse=True)
        return all_entries

    def get_summary(self, days: int = 7) -> dict:
        """Get summary statistics for friction entries."""
        entries = self.get_recent_entries(days)

        # Count by category
        category_counts = {}
        for cat in FRICTION_CATEGORIES:
            category_counts[cat] = sum(1 for e in entries if e.category == cat)

        # Count by severity
        severity_counts = {"low": 0, "medium": 0, "high": 0}
        for e in entries:
            severity_counts[e.severity] = severity_counts.get(e.severity, 0) + 1

        return {
            "total_entries": len(entries),
            "days_covered": days,
            "by_category": category_counts,
            "by_severity": severity_counts,
            "top_categories": sorted(
                category_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:3],
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_friction_log_repo: Optional[FrictionLogRepository] = None


def get_friction_log_repository() -> FrictionLogRepository:
    """Get the friction log repository singleton."""
    global _friction_log_repo
    if _friction_log_repo is None:
        _friction_log_repo = FrictionLogRepository()
    return _friction_log_repo


def reset_friction_log_repository() -> None:
    """Reset the singleton (for testing)."""
    global _friction_log_repo
    _friction_log_repo = None
