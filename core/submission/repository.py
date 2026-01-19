"""
Submission Repository - In-Memory Storage for Property Submissions

Provides storage and retrieval for submission logbooks.
This is an in-memory implementation for development.
Production should use a persistent database.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.submission.logbook import SubmissionLogbook, VersionAction
from core.submission.schema import AgentSubmission, SubmissionStatus


# =============================================================================
# Repository
# =============================================================================


class SubmissionRepository:
    """
    Repository for storing and retrieving submission logbooks.

    Provides CRUD operations and querying capabilities.
    Uses in-memory storage with optional file persistence.
    """

    def __init__(self, persist_path: Optional[str] = None):
        """
        Initialise repository.

        Args:
            persist_path: Optional path to persist data to JSON file
        """
        self._logbooks: dict[str, SubmissionLogbook] = {}
        self._persist_path = Path(persist_path) if persist_path else None

        # Load existing data if persist path exists
        if self._persist_path and self._persist_path.exists():
            self._load_from_file()

    def _save_to_file(self) -> None:
        """Persist data to file."""
        if not self._persist_path:
            return

        data = {
            "logbooks": {
                pid: lb.to_dict()
                for pid, lb in self._logbooks.items()
            },
            "saved_at": datetime.utcnow().isoformat(),
        }

        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._persist_path.write_text(json.dumps(data, indent=2))

    def _load_from_file(self) -> None:
        """Load data from file."""
        if not self._persist_path or not self._persist_path.exists():
            return

        try:
            data = json.loads(self._persist_path.read_text())
            for pid, lb_data in data.get("logbooks", {}).items():
                self._logbooks[pid] = SubmissionLogbook.from_dict(lb_data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Log error but don't fail - start fresh
            print(f"Warning: Could not load repository data: {e}")

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def create(self, submission: AgentSubmission) -> SubmissionLogbook:
        """
        Create a new submission logbook.

        Args:
            submission: Initial submission data

        Returns:
            New SubmissionLogbook

        Raises:
            ValueError: If property_id already exists
        """
        if submission.property_id in self._logbooks:
            raise ValueError(f"Property {submission.property_id} already exists")

        logbook = SubmissionLogbook.create(submission)
        self._logbooks[submission.property_id] = logbook

        self._save_to_file()
        return logbook

    def get(self, property_id: str) -> Optional[SubmissionLogbook]:
        """
        Get a submission logbook by property ID.

        Args:
            property_id: Property ID

        Returns:
            SubmissionLogbook if found, None otherwise
        """
        return self._logbooks.get(property_id)

    def update(
        self,
        property_id: str,
        submission: AgentSubmission,
        action: VersionAction,
        action_by: str,
        action_note: Optional[str] = None,
    ) -> Optional[SubmissionLogbook]:
        """
        Update a submission (creates new version).

        Args:
            property_id: Property ID
            submission: Updated submission data
            action: Type of action
            action_by: Who performed the action
            action_note: Optional note

        Returns:
            Updated SubmissionLogbook, or None if not found
        """
        logbook = self._logbooks.get(property_id)
        if not logbook:
            return None

        logbook.add_version(
            submission=submission,
            action=action,
            action_by=action_by,
            action_note=action_note,
        )

        self._save_to_file()
        return logbook

    def update_status(
        self,
        property_id: str,
        new_status: SubmissionStatus,
        action_by: str,
        action_note: Optional[str] = None,
    ) -> Optional[SubmissionLogbook]:
        """
        Update submission status.

        Args:
            property_id: Property ID
            new_status: New status
            action_by: Who performed the action
            action_note: Optional note

        Returns:
            Updated SubmissionLogbook, or None if not found
        """
        logbook = self._logbooks.get(property_id)
        if not logbook:
            return None

        logbook.update_status(
            new_status=new_status,
            action_by=action_by,
            action_note=action_note,
        )

        self._save_to_file()
        return logbook

    def delete(self, property_id: str) -> bool:
        """
        Delete a submission logbook.

        Note: In production, submissions should be archived, not deleted.

        Args:
            property_id: Property ID

        Returns:
            True if deleted, False if not found
        """
        if property_id in self._logbooks:
            del self._logbooks[property_id]
            self._save_to_file()
            return True
        return False

    # =========================================================================
    # Query Operations
    # =========================================================================

    def list_all(self) -> list[SubmissionLogbook]:
        """Get all submission logbooks."""
        return list(self._logbooks.values())

    def list_by_status(self, status: SubmissionStatus) -> list[SubmissionLogbook]:
        """Get submissions by status."""
        return [lb for lb in self._logbooks.values() if lb.current_status == status]

    def list_by_agent(self, agent_email: str) -> list[SubmissionLogbook]:
        """Get submissions by agent email."""
        result = []
        for logbook in self._logbooks.values():
            current = logbook.current_submission
            if current and current.agent_email == agent_email:
                result.append(logbook)
        return result

    def count(self) -> int:
        """Get total number of submissions."""
        return len(self._logbooks)

    def count_by_status(self) -> dict[str, int]:
        """Get count of submissions by status."""
        counts: dict[str, int] = {}
        for logbook in self._logbooks.values():
            status = logbook.current_status.value
            counts[status] = counts.get(status, 0) + 1
        return counts

    def get_summary(self) -> dict:
        """
        Get summary statistics for admin view.

        Returns dict with counts by status and recent submissions.
        """
        status_counts = self.count_by_status()

        # Get recent submissions (last 10)
        all_logbooks = sorted(
            self._logbooks.values(),
            key=lambda lb: lb.created_at,
            reverse=True,
        )
        recent = []
        for lb in all_logbooks[:10]:
            current = lb.current_submission
            if current:
                recent.append({
                    "property_id": lb.property_id,
                    "address": current.full_address,
                    "postcode": current.postcode,
                    "guide_price": current.guide_price,
                    "status": lb.current_status.value,
                    "created_at": lb.created_at.isoformat(),
                    "version_count": lb.version_count,
                    "is_complete": current.is_complete,
                })

        return {
            "total_submissions": self.count(),
            "status_counts": status_counts,
            "recent_submissions": recent,
        }

    def get_admin_list(self) -> list[dict]:
        """
        Get list of all submissions for admin view.

        Returns list of submission summaries with status and completeness.
        """
        result = []
        for logbook in sorted(
            self._logbooks.values(),
            key=lambda lb: lb.created_at,
            reverse=True,
        ):
            current = logbook.current_submission
            if current:
                completeness = logbook.get_completeness_check()
                completeness_score = current.get_completeness_score()
                result.append({
                    "property_id": logbook.property_id,
                    "address": current.full_address,
                    "postcode": current.postcode,
                    "property_type": current.property_type.value,
                    "tenure": current.tenure.value,
                    "guide_price": current.guide_price,
                    "floor_area_sqm": current.floor_area_sqm,
                    "sale_route": current.sale_route.value,
                    "agent_firm": current.agent_firm,
                    "agent_name": current.agent_name,
                    "agent_email": current.agent_email,
                    "status": logbook.current_status.value,
                    "created_at": logbook.created_at.isoformat(),
                    "version_count": logbook.version_count,
                    "is_complete": completeness.get("is_complete", False),
                    "missing_documents": completeness.get("missing_documents", []),
                    "document_count": completeness.get("document_count", 0),
                    # Completeness score for admin
                    "completeness_score": completeness_score.total_score,
                    "completeness_blocked": completeness_score.is_blocked,
                })
        return result


# =============================================================================
# Singleton Instance
# =============================================================================

_repository_instance: Optional[SubmissionRepository] = None


def get_submission_repository(persist_path: Optional[str] = None) -> SubmissionRepository:
    """
    Get the submission repository singleton.

    Args:
        persist_path: Optional path for persistence (only used on first call)

    Returns:
        SubmissionRepository instance
    """
    global _repository_instance
    if _repository_instance is None:
        _repository_instance = SubmissionRepository(
            persist_path or "data/submissions.json"
        )
    return _repository_instance
