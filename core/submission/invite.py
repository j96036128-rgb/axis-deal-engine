"""
Invite Token System for Private Submission Portal

This module provides cryptographic invite tokens for private, invite-only
access to the submission portal. No accounts. No passwords.

Principles:
1. Invite-only by design
2. Tokens are cryptographically secure
3. Tokens can be revoked or expire
4. No self-signup or public discovery
5. Agent metadata is bound to token, not editable by user
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Final, Optional, Union
from uuid import uuid4


# =============================================================================
# Constants
# =============================================================================

# Token length in bytes (32 bytes = 256 bits = 43 URL-safe base64 chars)
TOKEN_BYTES: Final[int] = 32

# Default token validity period (days)
DEFAULT_EXPIRY_DAYS: Final[int] = 90


# =============================================================================
# Enums
# =============================================================================


class InviteStatus(Enum):
    """Status of an invite token."""

    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


# =============================================================================
# Data Model
# =============================================================================


@dataclass
class InviteToken:
    """
    Cryptographic invite token for submission portal access.

    Immutable after creation except for status and uses_count.
    """

    token_id: str
    token_value: str  # URL-safe secure random string
    agent_firm: str
    agent_email: str
    status: InviteStatus
    created_at: datetime
    expires_at: Optional[datetime]
    max_uses: Optional[int]
    uses_count: int = 0
    notes: Optional[str] = None  # Internal only, never exposed

    def __post_init__(self):
        """Validate token data."""
        if not self.token_id:
            raise ValueError("token_id is required")
        if not self.token_value:
            raise ValueError("token_value is required")
        if not self.agent_firm:
            raise ValueError("agent_firm is required")
        if not self.agent_email:
            raise ValueError("agent_email is required")
        if self.max_uses is not None and self.max_uses < 1:
            raise ValueError("max_uses must be at least 1")

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_max_uses_reached(self) -> bool:
        """Check if token has reached maximum uses."""
        if self.max_uses is None:
            return False
        return self.uses_count >= self.max_uses

    @property
    def is_valid(self) -> bool:
        """
        Check if token is currently valid for use.

        A token is valid if:
        - Status is ACTIVE
        - Not expired
        - Max uses not exceeded
        """
        return (
            self.status == InviteStatus.ACTIVE
            and not self.is_expired
            and not self.is_max_uses_reached
        )

    @property
    def remaining_uses(self) -> Optional[int]:
        """Get remaining uses, or None if unlimited."""
        if self.max_uses is None:
            return None
        return max(0, self.max_uses - self.uses_count)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "token_id": self.token_id,
            "token_value": self.token_value,
            "agent_firm": self.agent_firm,
            "agent_email": self.agent_email,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "max_uses": self.max_uses,
            "uses_count": self.uses_count,
            "notes": self.notes,
        }

    def to_public_dict(self) -> dict:
        """
        Convert to dictionary for external use.

        Excludes internal notes and token_value (security).
        """
        return {
            "token_id": self.token_id,
            "agent_firm": self.agent_firm,
            "agent_email": self.agent_email,
            "status": self.status.value,
            "is_valid": self.is_valid,
            "remaining_uses": self.remaining_uses,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InviteToken":
        """Create from dictionary."""
        return cls(
            token_id=data["token_id"],
            token_value=data["token_value"],
            agent_firm=data["agent_firm"],
            agent_email=data["agent_email"],
            status=InviteStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
            max_uses=data.get("max_uses"),
            uses_count=data.get("uses_count", 0),
            notes=data.get("notes"),
        )


# =============================================================================
# Token Generation
# =============================================================================


def generate_token_value() -> str:
    """
    Generate a cryptographically secure, URL-safe token value.

    Uses secrets module for cryptographic randomness.
    Returns a URL-safe base64 encoded string.
    """
    return secrets.token_urlsafe(TOKEN_BYTES)


def create_invite_token(
    agent_firm: str,
    agent_email: str,
    expires_at: Optional[datetime] = None,
    max_uses: Optional[int] = None,
    notes: Optional[str] = None,
) -> InviteToken:
    """
    Create a new invite token.

    Args:
        agent_firm: Agent's firm name (locked, cannot be changed by user)
        agent_email: Agent's email (locked, cannot be changed by user)
        expires_at: Optional expiration datetime
        max_uses: Optional maximum number of submissions
        notes: Optional internal notes

    Returns:
        New InviteToken instance
    """
    return InviteToken(
        token_id=f"INV-{uuid4().hex[:12].upper()}",
        token_value=generate_token_value(),
        agent_firm=agent_firm,
        agent_email=agent_email,
        status=InviteStatus.ACTIVE,
        created_at=datetime.utcnow(),
        expires_at=expires_at,
        max_uses=max_uses,
        uses_count=0,
        notes=notes,
    )


# =============================================================================
# Repository
# =============================================================================


class InviteTokenRepository:
    """
    Repository for storing and managing invite tokens.

    Uses JSON file persistence, swappable for database later.
    """

    def __init__(self, persist_path: Optional[str] = None):
        """
        Initialize repository.

        Args:
            persist_path: Path to JSON file for persistence
        """
        self._tokens: dict[str, InviteToken] = {}  # token_id -> InviteToken
        self._value_index: dict[str, str] = {}  # token_value -> token_id
        self._persist_path = Path(persist_path) if persist_path else None

        if self._persist_path and self._persist_path.exists():
            self._load_from_file()

    def _save_to_file(self) -> None:
        """Persist data to file."""
        if not self._persist_path:
            return

        data = {
            "tokens": {tid: t.to_dict() for tid, t in self._tokens.items()},
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
            for tid, token_data in data.get("tokens", {}).items():
                token = InviteToken.from_dict(token_data)
                self._tokens[tid] = token
                self._value_index[token.token_value] = tid
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Warning: Could not load invite token data: {e}")

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def create_token(
        self,
        agent_firm: str,
        agent_email: str,
        expires_at: Optional[datetime] = None,
        max_uses: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> InviteToken:
        """
        Create and store a new invite token.

        Args:
            agent_firm: Agent's firm name
            agent_email: Agent's email
            expires_at: Optional expiration datetime
            max_uses: Optional maximum uses
            notes: Optional internal notes

        Returns:
            New InviteToken
        """
        token = create_invite_token(
            agent_firm=agent_firm,
            agent_email=agent_email,
            expires_at=expires_at,
            max_uses=max_uses,
            notes=notes,
        )

        # Ensure token_value is unique (extremely unlikely collision)
        while token.token_value in self._value_index:
            token = InviteToken(
                token_id=token.token_id,
                token_value=generate_token_value(),
                agent_firm=token.agent_firm,
                agent_email=token.agent_email,
                status=token.status,
                created_at=token.created_at,
                expires_at=token.expires_at,
                max_uses=token.max_uses,
                uses_count=token.uses_count,
                notes=token.notes,
            )

        self._tokens[token.token_id] = token
        self._value_index[token.token_value] = token.token_id
        self._save_to_file()

        return token

    def get_by_id(self, token_id: str) -> Optional[InviteToken]:
        """Get token by ID."""
        return self._tokens.get(token_id)

    def get_by_value(self, token_value: str) -> Optional[InviteToken]:
        """Get token by value (for validation)."""
        token_id = self._value_index.get(token_value)
        if token_id:
            return self._tokens.get(token_id)
        return None

    def increment_use(self, token_id: str) -> bool:
        """
        Increment uses_count for a token.

        Args:
            token_id: Token ID

        Returns:
            True if incremented, False if token not found
        """
        token = self._tokens.get(token_id)
        if not token:
            return False

        # Create new token with incremented count (dataclass is not frozen)
        token.uses_count += 1
        self._save_to_file()
        return True

    def revoke(self, token_id: str, note: Optional[str] = None) -> bool:
        """
        Revoke a token.

        Args:
            token_id: Token ID
            note: Optional note explaining revocation

        Returns:
            True if revoked, False if token not found
        """
        token = self._tokens.get(token_id)
        if not token:
            return False

        token.status = InviteStatus.REVOKED
        if note:
            existing_notes = token.notes or ""
            token.notes = f"{existing_notes}\n[REVOKED] {note}".strip()

        self._save_to_file()
        return True

    def is_valid(self, token_value: str) -> bool:
        """
        Check if a token value is valid.

        Args:
            token_value: The token value to check

        Returns:
            True if token exists and is valid
        """
        token = self.get_by_value(token_value)
        return token is not None and token.is_valid

    # =========================================================================
    # Query Operations
    # =========================================================================

    def list_all(self) -> list[InviteToken]:
        """Get all tokens."""
        return list(self._tokens.values())

    def list_active(self) -> list[InviteToken]:
        """Get all active (valid) tokens."""
        return [t for t in self._tokens.values() if t.is_valid]

    def list_by_agent(self, agent_email: str) -> list[InviteToken]:
        """Get all tokens for an agent."""
        return [t for t in self._tokens.values() if t.agent_email == agent_email]

    def list_by_firm(self, agent_firm: str) -> list[InviteToken]:
        """Get all tokens for a firm."""
        return [t for t in self._tokens.values() if t.agent_firm == agent_firm]

    def count(self) -> int:
        """Get total number of tokens."""
        return len(self._tokens)

    def get_admin_list(self) -> list[dict]:
        """
        Get list of all tokens for admin view.

        Returns list with usage statistics.
        """
        result = []
        for token in sorted(
            self._tokens.values(),
            key=lambda t: t.created_at,
            reverse=True,
        ):
            result.append({
                "token_id": token.token_id,
                "agent_firm": token.agent_firm,
                "agent_email": token.agent_email,
                "status": token.status.value,
                "is_valid": token.is_valid,
                "created_at": token.created_at.isoformat(),
                "expires_at": token.expires_at.isoformat() if token.expires_at else None,
                "max_uses": token.max_uses,
                "uses_count": token.uses_count,
                "remaining_uses": token.remaining_uses,
            })
        return result


# =============================================================================
# Validation Results
# =============================================================================


@dataclass(frozen=True)
class InviteValidationSuccess:
    """Returned when invite token is valid."""

    token: InviteToken
    agent_firm: str
    agent_email: str


@dataclass(frozen=True)
class InviteValidationFailure:
    """Returned when invite token is invalid."""

    reason: str
    error_code: str  # MISSING, NOT_FOUND, REVOKED, EXPIRED, MAX_USES


InviteValidationResult = Union[InviteValidationSuccess, InviteValidationFailure]


def validate_invite_token(
    token_value: Optional[str],
    repository: InviteTokenRepository,
) -> InviteValidationResult:
    """
    Validate an invite token.

    Args:
        token_value: The token value from query params
        repository: Token repository

    Returns:
        InviteValidationSuccess if valid, InviteValidationFailure otherwise
    """
    if not token_value:
        return InviteValidationFailure(
            reason="Invite token is required",
            error_code="MISSING",
        )

    token = repository.get_by_value(token_value)

    if not token:
        return InviteValidationFailure(
            reason="Invalid invite token",
            error_code="NOT_FOUND",
        )

    if token.status == InviteStatus.REVOKED:
        return InviteValidationFailure(
            reason="This invite has been revoked",
            error_code="REVOKED",
        )

    if token.is_expired:
        return InviteValidationFailure(
            reason="This invite has expired",
            error_code="EXPIRED",
        )

    if token.is_max_uses_reached:
        return InviteValidationFailure(
            reason="This invite has reached its maximum uses",
            error_code="MAX_USES",
        )

    return InviteValidationSuccess(
        token=token,
        agent_firm=token.agent_firm,
        agent_email=token.agent_email,
    )


# =============================================================================
# Singleton Instance
# =============================================================================

_repository_instance: Optional[InviteTokenRepository] = None


def get_invite_repository(persist_path: Optional[str] = None) -> InviteTokenRepository:
    """
    Get the invite token repository singleton.

    Args:
        persist_path: Optional path for persistence (only used on first call)

    Returns:
        InviteTokenRepository instance
    """
    global _repository_instance
    if _repository_instance is None:
        _repository_instance = InviteTokenRepository(
            persist_path or "data/invite_tokens.json"
        )
    return _repository_instance


def reset_invite_repository() -> None:
    """Reset the singleton instance (for testing)."""
    global _repository_instance
    _repository_instance = None
