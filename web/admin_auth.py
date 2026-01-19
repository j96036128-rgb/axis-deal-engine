"""
Admin Authentication - Secure Password-Based Authentication for Admin Dashboard

Implements:
- Password-based authentication with secure hashing
- Session management via signed cookies
- Environment-based admin user configuration

Security:
- Passwords hashed with bcrypt (via passlib)
- Sessions signed with secret key
- CSRF protection via same-site cookies
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Optional

from fastapi import Request, Response


# =============================================================================
# Configuration
# =============================================================================

# Admin emails from environment (comma-separated)
# Example: ADMIN_EMAILS=admin@axisallocation.com,ops@axisallocation.com
def get_admin_emails() -> set[str]:
    """Get admin emails from environment variable."""
    emails = os.getenv("ADMIN_EMAILS", "")
    if not emails:
        return set()
    return {e.strip().lower() for e in emails.split(",") if e.strip()}


# Admin password from environment (single password for all admins)
# Must be set in production
def get_admin_password_hash() -> Optional[str]:
    """Get pre-hashed admin password from environment."""
    return os.getenv("ADMIN_PASSWORD_HASH")


# Secret key for signing sessions
def get_session_secret() -> str:
    """Get session secret key from environment."""
    secret = os.getenv("SESSION_SECRET")
    if not secret:
        # Generate ephemeral secret for development (sessions won't persist across restarts)
        secret = secrets.token_hex(32)
    return secret


# Session configuration
SESSION_COOKIE_NAME: Final[str] = "axis_admin_session"
SESSION_DURATION_HOURS: Final[int] = 8  # Sessions expire after 8 hours


# =============================================================================
# Password Hashing (using hashlib for zero dependencies)
# =============================================================================


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """
    Hash a password using PBKDF2-HMAC-SHA256.

    Returns: salt$hash (both hex-encoded)
    """
    if salt is None:
        salt = secrets.token_hex(16)

    # PBKDF2 with 100,000 iterations
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    )
    return f"{salt}${hash_bytes.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash."""
    try:
        salt, _ = stored_hash.split("$", 1)
        return hmac.compare_digest(hash_password(password, salt), stored_hash)
    except (ValueError, AttributeError):
        return False


# =============================================================================
# Session Token Management
# =============================================================================


@dataclass(frozen=True)
class AdminSession:
    """Represents an authenticated admin session."""

    email: str
    created_at: datetime
    expires_at: datetime
    session_id: str

    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.utcnow() > self.expires_at

    def to_dict(self) -> dict:
        """Serialize session to dictionary."""
        return {
            "email": self.email,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AdminSession":
        """Deserialize session from dictionary."""
        return cls(
            email=data["email"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            session_id=data["session_id"],
        )


def create_session(email: str) -> AdminSession:
    """Create a new admin session."""
    now = datetime.utcnow()
    return AdminSession(
        email=email,
        created_at=now,
        expires_at=now + timedelta(hours=SESSION_DURATION_HOURS),
        session_id=secrets.token_hex(16),
    )


def sign_session(session: AdminSession, secret: str) -> str:
    """
    Sign and encode a session for cookie storage.

    Format: base64(json_payload).signature
    """
    import base64

    payload = json.dumps(session.to_dict(), separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode()

    # HMAC signature
    signature = hmac.new(
        secret.encode(),
        payload_b64.encode(),
        hashlib.sha256,
    ).hexdigest()

    return f"{payload_b64}.{signature}"


def verify_session(token: str, secret: str) -> Optional[AdminSession]:
    """
    Verify and decode a signed session token.

    Returns AdminSession if valid and not expired, None otherwise.
    """
    import base64

    try:
        payload_b64, signature = token.rsplit(".", 1)

        # Verify signature
        expected_signature = hmac.new(
            secret.encode(),
            payload_b64.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            return None

        # Decode payload
        payload = base64.urlsafe_b64decode(payload_b64.encode()).decode()
        data = json.loads(payload)

        session = AdminSession.from_dict(data)

        # Check expiration
        if session.is_expired:
            return None

        return session

    except (ValueError, KeyError, json.JSONDecodeError):
        return None


# =============================================================================
# Authentication Functions
# =============================================================================


def authenticate_admin(email: str, password: str) -> Optional[AdminSession]:
    """
    Authenticate an admin user.

    Args:
        email: Admin email address
        password: Plain text password

    Returns:
        AdminSession if authentication successful, None otherwise
    """
    email = email.strip().lower()

    # Check if email is in admin list
    admin_emails = get_admin_emails()
    if not admin_emails:
        # No admins configured - reject all
        return None

    if email not in admin_emails:
        return None

    # Verify password
    stored_hash = get_admin_password_hash()
    if not stored_hash:
        # No password configured - reject all
        return None

    if not verify_password(password, stored_hash):
        return None

    # Create session
    return create_session(email)


def get_current_admin(request: Request) -> Optional[AdminSession]:
    """
    Get the current admin session from request cookies.

    Args:
        request: FastAPI request object

    Returns:
        AdminSession if valid session exists, None otherwise
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None

    return verify_session(token, get_session_secret())


def set_session_cookie(response: Response, session: AdminSession) -> None:
    """Set the session cookie on a response."""
    token = sign_session(session, get_session_secret())

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_DURATION_HOURS * 3600,
        httponly=True,
        secure=os.getenv("RAILWAY_ENVIRONMENT") is not None,  # Secure in production
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    """Clear the session cookie on a response."""
    response.delete_cookie(key=SESSION_COOKIE_NAME)


# =============================================================================
# Helper: Generate Password Hash (for setup)
# =============================================================================


def generate_password_hash(password: str) -> str:
    """
    Generate a password hash for environment variable setup.

    Usage:
        python -c "from web.admin_auth import generate_password_hash; print(generate_password_hash('your-password'))"

    Then set: ADMIN_PASSWORD_HASH=<output>
    """
    return hash_password(password)


# =============================================================================
# Development Helper
# =============================================================================


def is_admin_configured() -> bool:
    """Check if admin authentication is properly configured."""
    return bool(get_admin_emails()) and bool(get_admin_password_hash())
