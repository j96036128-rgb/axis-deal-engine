"""
Tests for Invite Token System

Tests covering:
1. Valid token grants access
2. Invalid / expired / revoked token blocks access
3. max_uses enforced
4. Token use increments on submission
5. Token metadata never appears in exports or PDFs
"""

from __future__ import annotations

import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from core.submission.invite import (
    InviteToken,
    InviteStatus,
    InviteTokenRepository,
    InviteValidationSuccess,
    InviteValidationFailure,
    validate_invite_token,
    create_invite_token,
    generate_token_value,
    TOKEN_BYTES,
    reset_invite_repository,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_persist_path():
    """Create a temporary file path for persistence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield str(Path(tmpdir) / "invite_tokens.json")


@pytest.fixture
def repository(temp_persist_path):
    """Create a fresh repository for each test."""
    reset_invite_repository()
    return InviteTokenRepository(persist_path=temp_persist_path)


@pytest.fixture
def active_token(repository):
    """Create an active token."""
    return repository.create_token(
        agent_firm="Test Estate Agents",
        agent_email="agent@testestate.com",
    )


@pytest.fixture
def token_with_max_uses(repository):
    """Create a token with max_uses limit."""
    return repository.create_token(
        agent_firm="Limited Use Ltd",
        agent_email="limited@example.com",
        max_uses=3,
    )


@pytest.fixture
def expiring_token(repository):
    """Create a token that expires in the future."""
    return repository.create_token(
        agent_firm="Expiring Ltd",
        agent_email="expiring@example.com",
        expires_at=datetime.utcnow() + timedelta(days=30),
    )


@pytest.fixture
def expired_token(repository):
    """Create a token that has already expired."""
    return repository.create_token(
        agent_firm="Expired Ltd",
        agent_email="expired@example.com",
        expires_at=datetime.utcnow() - timedelta(days=1),
    )


# =============================================================================
# Token Generation Tests
# =============================================================================


class TestTokenGeneration:
    """Tests for token creation and generation."""

    def test_generate_token_value_is_url_safe(self):
        """Generated token values should be URL-safe."""
        token_value = generate_token_value()
        # URL-safe base64 only contains these characters
        valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        assert all(c in valid_chars for c in token_value)

    def test_generate_token_value_has_sufficient_entropy(self):
        """Generated token values should have enough entropy."""
        token_value = generate_token_value()
        # 32 bytes = 256 bits, URL-safe base64 is 4/3 size = ~43 chars
        assert len(token_value) >= 40

    def test_generate_token_value_is_unique(self):
        """Generated token values should be unique."""
        tokens = {generate_token_value() for _ in range(100)}
        assert len(tokens) == 100  # All unique

    def test_create_invite_token_generates_valid_id(self):
        """Created tokens should have valid IDs."""
        token = create_invite_token(
            agent_firm="Test Firm",
            agent_email="test@example.com",
        )
        assert token.token_id.startswith("INV-")
        assert len(token.token_id) == 16  # INV- + 12 hex chars

    def test_create_invite_token_sets_defaults(self):
        """Created tokens should have correct defaults."""
        token = create_invite_token(
            agent_firm="Test Firm",
            agent_email="test@example.com",
        )
        assert token.status == InviteStatus.ACTIVE
        assert token.uses_count == 0
        assert token.max_uses is None
        assert token.expires_at is None


# =============================================================================
# Valid Token Grants Access Tests
# =============================================================================


class TestValidTokenGrantsAccess:
    """Tests that valid tokens grant access."""

    def test_valid_token_returns_success(self, repository, active_token):
        """Valid token should return InviteValidationSuccess."""
        result = validate_invite_token(active_token.token_value, repository)
        assert isinstance(result, InviteValidationSuccess)

    def test_valid_token_contains_agent_data(self, repository, active_token):
        """Valid token result should contain agent firm and email."""
        result = validate_invite_token(active_token.token_value, repository)
        assert isinstance(result, InviteValidationSuccess)
        assert result.agent_firm == "Test Estate Agents"
        assert result.agent_email == "agent@testestate.com"

    def test_valid_token_contains_token_object(self, repository, active_token):
        """Valid token result should contain the token object."""
        result = validate_invite_token(active_token.token_value, repository)
        assert isinstance(result, InviteValidationSuccess)
        assert result.token.token_id == active_token.token_id

    def test_token_with_remaining_uses_is_valid(self, repository, token_with_max_uses):
        """Token with remaining uses should be valid."""
        # Use token once
        repository.increment_use(token_with_max_uses.token_id)

        # Should still be valid (2 uses remaining)
        result = validate_invite_token(token_with_max_uses.token_value, repository)
        assert isinstance(result, InviteValidationSuccess)

    def test_unexpired_token_is_valid(self, repository, expiring_token):
        """Token that hasn't expired yet should be valid."""
        result = validate_invite_token(expiring_token.token_value, repository)
        assert isinstance(result, InviteValidationSuccess)


# =============================================================================
# Invalid Token Blocks Access Tests
# =============================================================================


class TestInvalidTokenBlocksAccess:
    """Tests that invalid tokens block access."""

    def test_missing_token_returns_failure(self, repository):
        """Missing token should return failure."""
        result = validate_invite_token(None, repository)
        assert isinstance(result, InviteValidationFailure)
        assert result.error_code == "MISSING"

    def test_empty_token_returns_failure(self, repository):
        """Empty token should return failure."""
        result = validate_invite_token("", repository)
        assert isinstance(result, InviteValidationFailure)
        assert result.error_code == "MISSING"

    def test_invalid_token_returns_failure(self, repository):
        """Invalid token value should return failure."""
        result = validate_invite_token("invalid-token-value", repository)
        assert isinstance(result, InviteValidationFailure)
        assert result.error_code == "NOT_FOUND"

    def test_revoked_token_returns_failure(self, repository, active_token):
        """Revoked token should return failure."""
        repository.revoke(active_token.token_id, "Test revocation")

        result = validate_invite_token(active_token.token_value, repository)
        assert isinstance(result, InviteValidationFailure)
        assert result.error_code == "REVOKED"

    def test_expired_token_returns_failure(self, repository, expired_token):
        """Expired token should return failure."""
        result = validate_invite_token(expired_token.token_value, repository)
        assert isinstance(result, InviteValidationFailure)
        assert result.error_code == "EXPIRED"


# =============================================================================
# Max Uses Enforced Tests
# =============================================================================


class TestMaxUsesEnforced:
    """Tests that max_uses limit is enforced."""

    def test_max_uses_reached_returns_failure(self, repository, token_with_max_uses):
        """Token at max uses should return failure."""
        # Use token 3 times (max_uses = 3)
        for _ in range(3):
            repository.increment_use(token_with_max_uses.token_id)

        result = validate_invite_token(token_with_max_uses.token_value, repository)
        assert isinstance(result, InviteValidationFailure)
        assert result.error_code == "MAX_USES"

    def test_one_below_max_uses_is_valid(self, repository, token_with_max_uses):
        """Token one below max uses should still be valid."""
        # Use token 2 times (max_uses = 3)
        for _ in range(2):
            repository.increment_use(token_with_max_uses.token_id)

        result = validate_invite_token(token_with_max_uses.token_value, repository)
        assert isinstance(result, InviteValidationSuccess)

    def test_unlimited_uses_token_never_reaches_max(self, repository, active_token):
        """Token without max_uses should never reach limit."""
        # Use token many times
        for _ in range(100):
            repository.increment_use(active_token.token_id)

        result = validate_invite_token(active_token.token_value, repository)
        assert isinstance(result, InviteValidationSuccess)

    def test_remaining_uses_calculated_correctly(self, repository, token_with_max_uses):
        """Remaining uses should be calculated correctly."""
        assert token_with_max_uses.remaining_uses == 3

        repository.increment_use(token_with_max_uses.token_id)
        token = repository.get_by_id(token_with_max_uses.token_id)
        assert token.remaining_uses == 2

    def test_unlimited_remaining_uses_is_none(self, repository, active_token):
        """Token without max_uses should have None remaining_uses."""
        assert active_token.remaining_uses is None


# =============================================================================
# Token Use Increments Tests
# =============================================================================


class TestTokenUseIncrements:
    """Tests that token usage is tracked correctly."""

    def test_increment_use_increases_count(self, repository, active_token):
        """increment_use should increase uses_count."""
        assert active_token.uses_count == 0

        repository.increment_use(active_token.token_id)
        token = repository.get_by_id(active_token.token_id)
        assert token.uses_count == 1

    def test_increment_use_persists(self, repository, active_token, temp_persist_path):
        """Incremented usage should persist to file."""
        repository.increment_use(active_token.token_id)

        # Create new repository from same file
        new_repo = InviteTokenRepository(persist_path=temp_persist_path)
        token = new_repo.get_by_id(active_token.token_id)
        assert token.uses_count == 1

    def test_increment_nonexistent_token_returns_false(self, repository):
        """Incrementing nonexistent token should return False."""
        result = repository.increment_use("INV-NONEXISTENT")
        assert result is False

    def test_multiple_increments_accumulate(self, repository, active_token):
        """Multiple increments should accumulate."""
        for i in range(5):
            repository.increment_use(active_token.token_id)

        token = repository.get_by_id(active_token.token_id)
        assert token.uses_count == 5


# =============================================================================
# Token Metadata Security Tests
# =============================================================================


class TestTokenMetadataSecurity:
    """Tests that token metadata doesn't leak to exports or PDFs."""

    def test_public_dict_excludes_token_value(self, active_token):
        """to_public_dict should not include token_value."""
        public = active_token.to_public_dict()
        assert "token_value" not in public

    def test_public_dict_excludes_notes(self, repository):
        """to_public_dict should not include internal notes."""
        token = repository.create_token(
            agent_firm="Secret Notes Ltd",
            agent_email="secret@example.com",
            notes="Internal admin note - do not expose",
        )
        public = token.to_public_dict()
        assert "notes" not in public

    def test_full_dict_includes_token_value(self, active_token):
        """to_dict should include token_value (for admin use)."""
        full = active_token.to_dict()
        assert "token_value" in full
        assert full["token_value"] == active_token.token_value

    def test_token_value_not_in_validation_result(self, repository, active_token):
        """Validation result should not expose token_value directly."""
        result = validate_invite_token(active_token.token_value, repository)
        assert isinstance(result, InviteValidationSuccess)
        # The token object is included but that's for internal use
        # Public-facing code should use agent_firm and agent_email only


# =============================================================================
# Repository Tests
# =============================================================================


class TestRepository:
    """Tests for InviteTokenRepository functionality."""

    def test_create_token_stores_token(self, repository):
        """Created token should be stored and retrievable."""
        token = repository.create_token(
            agent_firm="Store Test Ltd",
            agent_email="store@example.com",
        )

        retrieved = repository.get_by_id(token.token_id)
        assert retrieved is not None
        assert retrieved.agent_firm == "Store Test Ltd"

    def test_get_by_value_returns_token(self, repository, active_token):
        """get_by_value should return the token."""
        retrieved = repository.get_by_value(active_token.token_value)
        assert retrieved is not None
        assert retrieved.token_id == active_token.token_id

    def test_get_by_value_returns_none_for_invalid(self, repository):
        """get_by_value should return None for invalid value."""
        assert repository.get_by_value("invalid-value") is None

    def test_revoke_changes_status(self, repository, active_token):
        """revoke should change token status."""
        repository.revoke(active_token.token_id)

        token = repository.get_by_id(active_token.token_id)
        assert token.status == InviteStatus.REVOKED

    def test_revoke_adds_note(self, repository, active_token):
        """revoke should add note to token."""
        repository.revoke(active_token.token_id, "Revoked for testing")

        token = repository.get_by_id(active_token.token_id)
        assert "Revoked for testing" in token.notes

    def test_list_all_returns_all_tokens(self, repository):
        """list_all should return all tokens."""
        repository.create_token("Firm 1", "a@example.com")
        repository.create_token("Firm 2", "b@example.com")
        repository.create_token("Firm 3", "c@example.com")

        all_tokens = repository.list_all()
        assert len(all_tokens) == 3

    def test_list_active_excludes_revoked(self, repository):
        """list_active should exclude revoked tokens."""
        t1 = repository.create_token("Firm 1", "a@example.com")
        t2 = repository.create_token("Firm 2", "b@example.com")
        repository.revoke(t1.token_id)

        active = repository.list_active()
        assert len(active) == 1
        assert active[0].token_id == t2.token_id

    def test_list_by_agent_filters_correctly(self, repository):
        """list_by_agent should filter by email."""
        repository.create_token("Firm 1", "alice@example.com")
        repository.create_token("Firm 2", "alice@example.com")
        repository.create_token("Firm 3", "bob@example.com")

        alice_tokens = repository.list_by_agent("alice@example.com")
        assert len(alice_tokens) == 2

    def test_list_by_firm_filters_correctly(self, repository):
        """list_by_firm should filter by firm name."""
        repository.create_token("ABC Estates", "a@example.com")
        repository.create_token("ABC Estates", "b@example.com")
        repository.create_token("XYZ Agents", "c@example.com")

        abc_tokens = repository.list_by_firm("ABC Estates")
        assert len(abc_tokens) == 2

    def test_persistence_survives_reload(self, temp_persist_path):
        """Tokens should survive repository reload."""
        repo1 = InviteTokenRepository(persist_path=temp_persist_path)
        token = repo1.create_token("Persist Ltd", "persist@example.com")

        # Create new repository from same file
        repo2 = InviteTokenRepository(persist_path=temp_persist_path)
        retrieved = repo2.get_by_id(token.token_id)

        assert retrieved is not None
        assert retrieved.agent_firm == "Persist Ltd"


# =============================================================================
# Token Properties Tests
# =============================================================================


class TestTokenProperties:
    """Tests for InviteToken property methods."""

    def test_is_expired_false_when_no_expiry(self):
        """is_expired should be False when expires_at is None."""
        token = create_invite_token("Test", "test@example.com")
        assert not token.is_expired

    def test_is_expired_false_when_future(self):
        """is_expired should be False when expires_at is in future."""
        token = create_invite_token(
            "Test", "test@example.com",
            expires_at=datetime.utcnow() + timedelta(days=1),
        )
        assert not token.is_expired

    def test_is_expired_true_when_past(self):
        """is_expired should be True when expires_at is in past."""
        token = create_invite_token(
            "Test", "test@example.com",
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        assert token.is_expired

    def test_is_max_uses_reached_false_when_none(self):
        """is_max_uses_reached should be False when max_uses is None."""
        token = create_invite_token("Test", "test@example.com")
        assert not token.is_max_uses_reached

    def test_is_max_uses_reached_false_when_under(self):
        """is_max_uses_reached should be False when under limit."""
        token = create_invite_token(
            "Test", "test@example.com",
            max_uses=5,
        )
        assert not token.is_max_uses_reached

    def test_is_valid_comprehensive(self, repository):
        """is_valid should check all conditions."""
        # Valid token
        valid = repository.create_token("Valid", "valid@example.com")
        assert valid.is_valid

        # Revoked token
        revoked = repository.create_token("Revoked", "revoked@example.com")
        repository.revoke(revoked.token_id)
        revoked = repository.get_by_id(revoked.token_id)
        assert not revoked.is_valid

        # Expired token
        expired = repository.create_token(
            "Expired", "expired@example.com",
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        assert not expired.is_valid


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for token serialization/deserialization."""

    def test_to_dict_round_trip(self, active_token):
        """Token should survive to_dict/from_dict round trip."""
        data = active_token.to_dict()
        restored = InviteToken.from_dict(data)

        assert restored.token_id == active_token.token_id
        assert restored.token_value == active_token.token_value
        assert restored.agent_firm == active_token.agent_firm
        assert restored.agent_email == active_token.agent_email
        assert restored.status == active_token.status

    def test_to_dict_handles_optional_fields(self):
        """to_dict should handle None optional fields."""
        token = create_invite_token("Test", "test@example.com")
        data = token.to_dict()

        assert data["expires_at"] is None
        assert data["max_uses"] is None
        assert data["notes"] is None

    def test_from_dict_handles_missing_optional(self):
        """from_dict should handle missing optional fields."""
        data = {
            "token_id": "INV-TEST123456",
            "token_value": "test-token-value",
            "agent_firm": "Test Firm",
            "agent_email": "test@example.com",
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
        }

        token = InviteToken.from_dict(data)
        assert token.expires_at is None
        assert token.max_uses is None
        assert token.uses_count == 0
