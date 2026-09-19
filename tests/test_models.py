"""ApiToken issuing, state and usage tracking."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from api_tokens import crypto
from api_tokens.models import ApiToken, DuplicateTokenNameError, TokenScope


def test_issue_stores_only_hash(user: User) -> None:
    """The raw token is returned but never persisted.

    Args:
        user: Token owner.
    """
    token, raw = ApiToken.issue(user, "ha")
    assert raw.startswith(f"test_{token.key_id}_")
    assert raw not in {token.key_hash, token.key_id}
    assert crypto.token_matches(raw, ApiToken.objects.get(pk=token.pk).key_hash)
    assert token.scope == TokenScope.READ
    assert str(token) == f"ha (test_{token.key_id}…)"


def test_duplicate_active_name_rejected_until_revoked(user: User) -> None:
    """Names are unique among active tokens only, so rotation is revoke + issue.

    Args:
        user: Token owner.
    """
    token, _ = ApiToken.issue(user, "ha")
    with pytest.raises(DuplicateTokenNameError):
        ApiToken.issue(user, "ha")
    token.revoke()
    ApiToken.issue(user, "ha")
    assert ApiToken.objects.filter(name="ha").count() == 2


def test_active_queryset_and_is_active(user: User) -> None:
    """Revoked and expired tokens are excluded consistently.

    Args:
        user: Token owner.
    """
    live, _ = ApiToken.issue(user, "live")
    expired, _ = ApiToken.issue(user, "expired", expires_at=timezone.now() - timedelta(seconds=1))
    revoked, _ = ApiToken.issue(user, "revoked")
    revoked.revoke()
    assert list(ApiToken.objects.active()) == [live]
    assert (live.is_active, expired.is_active, revoked.is_active) == (True, False, False)


def test_revoke_is_idempotent(user: User) -> None:
    """A second revoke keeps the original timestamp.

    Args:
        user: Token owner.
    """
    token, _ = ApiToken.issue(user, "ha")
    token.revoke()
    first = token.revoked_at
    token.revoke()
    assert token.revoked_at == first


def test_touch_is_throttled(user: User) -> None:
    """last_used_at is written at most once per interval.

    Args:
        user: Token owner.
    """
    token, _ = ApiToken.issue(user, "ha")
    t0 = timezone.now()
    token.touch(t0)
    token.touch(t0 + timedelta(seconds=30))
    assert ApiToken.objects.get(pk=token.pk).last_used_at == t0
    token.touch(t0 + timedelta(seconds=61))
    assert ApiToken.objects.get(pk=token.pk).last_used_at == t0 + timedelta(seconds=61)
