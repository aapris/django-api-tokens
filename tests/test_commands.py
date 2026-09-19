"""Management commands and expiry parsing."""

from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.utils import timezone

from api_tokens import crypto
from api_tokens.durations import parse_expiry
from api_tokens.models import ApiToken, TokenScope

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def _run(*args: str) -> tuple[str, str]:
    """Run a management command and capture its output.

    Args:
        *args: Command name and arguments.

    Returns:
        ``(stdout, stderr)``.
    """
    out, err = StringIO(), StringIO()
    call_command(*args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


def test_create_prints_only_token_on_stdout(user: User) -> None:
    """stdout is the bare token, usable as ``TOKEN=$(…)``.

    Args:
        user: Token owner.
    """
    out, err = _run("token_create", "--user", "alice", "--name", "ha", "--scope", "write", "--expires", "30d")
    raw = out.strip()
    token = ApiToken.objects.get()
    assert crypto.token_matches(raw, token.key_hash)
    assert token.scope == TokenScope.WRITE
    assert token.expires_at is not None
    assert "cannot be shown again" in err


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--user", "nobody", "--name", "x"], "No user"),
        (["--user", "alice", "--name", "x", "--expires", "soon"], "Expected e.g."),
    ],
)
def test_create_errors(user: User, args: list[str], message: str) -> None:
    """Bad input becomes a CommandError, not a traceback.

    Args:
        user: Existing user.
        args: Command arguments.
        message: Expected error fragment.
    """
    with pytest.raises(CommandError, match=message):
        _run("token_create", *args)


def test_create_duplicate_name(user: User) -> None:
    """A second active token with the same name is refused.

    Args:
        user: Token owner.
    """
    ApiToken.issue(user, "ha")
    with pytest.raises(CommandError, match="already exists"):
        _run("token_create", "--user", "alice", "--name", "ha")


def test_list_hides_secrets_and_revoked(user: User) -> None:
    """The list shows IDs, never hashes; revoked tokens only with --all.

    Args:
        user: Token owner.
    """
    live, _ = ApiToken.issue(user, "live")
    gone, _ = ApiToken.issue(user, "gone")
    gone.revoke()
    out, _ = _run("token_list")
    assert live.display_id in out
    assert gone.display_id not in out
    assert live.key_hash not in out
    out_all, _ = _run("token_list", "--all", "--user", "alice")
    assert "revoked" in out_all


@pytest.mark.parametrize("form", ["display_id", "key_id", "raw"])
def test_revoke_accepts_id_or_full_token(user: User, form: str) -> None:
    """Revoke by the listed ID, the bare key id, or a pasted leaked token.

    Args:
        user: Token owner.
        form: Which identifier to pass.
    """
    token, raw = ApiToken.issue(user, "ha")
    value = {"display_id": token.display_id, "key_id": token.key_id, "raw": raw}[form]
    _run("token_revoke", value)
    token.refresh_from_db()
    assert token.revoked_at is not None


def test_revoke_unknown(db: None) -> None:
    """Unknown IDs are an error.

    Args:
        db: Database access.
    """
    with pytest.raises(CommandError, match="No token"):
        _run("token_revoke", "test_doesnotexist")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("12h", NOW + timedelta(hours=12)),
        ("90d", NOW + timedelta(days=90)),
        ("2w", NOW + timedelta(days=14)),
        ("1y", NOW + timedelta(days=365)),
        ("2026-09-20T08:00:00+00:00", datetime(2026, 9, 20, 8, 0, tzinfo=UTC)),
    ],
)
def test_parse_expiry(value: str, expected: datetime) -> None:
    """Relative and absolute expiry forms.

    Args:
        value: Input string.
        expected: Expected result.
    """
    assert parse_expiry(value, now=NOW) == expected


def test_parse_expiry_bare_date_is_end_of_local_day() -> None:
    """A bare date expires at the end of that day in the current time zone."""
    result = parse_expiry("2026-10-01", now=NOW)
    local = timezone.localtime(result)
    assert (local.date().isoformat(), local.hour, local.minute) == ("2026-10-01", 23, 59)


@pytest.mark.parametrize("value", ["0d", "2020-01-01", "tomorrow"])
def test_parse_expiry_rejects(value: str) -> None:
    """Past, zero and unparseable values fail.

    Args:
        value: Input string.
    """
    with pytest.raises(ValueError, match=r"not in the future|Expected e\.g\."):
        parse_expiry(value, now=NOW)
