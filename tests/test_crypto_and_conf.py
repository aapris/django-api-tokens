"""Token format, hashing and settings validation."""

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from api_tokens import crypto
from api_tokens.conf import get_settings


def test_build_and_parse_roundtrip() -> None:
    """A built token parses back into its prefix and key id."""
    key_id = crypto.generate_key_id()
    raw = crypto.build_token("my_project", key_id)
    parsed = crypto.parse_token(raw)
    assert parsed is not None
    assert (parsed.prefix, parsed.key_id, parsed.raw) == ("my_project", key_id, raw)


@pytest.mark.parametrize(
    "raw",
    ["", "nounderscores", "test_short_secret", f"test_{'a' * 12}_{'b' * 39}", f"test_{'a' * 12}_{'-' * 40}"],
)
def test_parse_rejects_malformed(raw: str) -> None:
    """Strings without the exact token shape are not tokens.

    Args:
        raw: Candidate string.
    """
    assert crypto.parse_token(raw) is None


def test_hash_matches_only_same_token() -> None:
    """The stored hash verifies the original token and nothing else."""
    raw = crypto.build_token("test", crypto.generate_key_id())
    stored = crypto.hash_token(raw)
    assert crypto.token_matches(raw, stored)
    assert not crypto.token_matches(raw + "x", stored)


def test_default_settings() -> None:
    """Without API_TOKENS the defaults apply."""
    with override_settings(API_TOKENS={}):
        conf = get_settings()
    assert (conf.prefix, conf.keyword, conf.last_used_interval) == ("tok", "Bearer", 60)


@pytest.mark.parametrize("api_tokens", [{"PREFIX": "Bad-Prefix"}, {"PREFIX": "x"}, {"UNKNOWN": 1}])
def test_invalid_settings_raise(api_tokens: dict[str, object]) -> None:
    """Malformed prefixes and unknown keys fail loudly.

    Args:
        api_tokens: The setting value under test.
    """
    with override_settings(API_TOKENS=api_tokens), pytest.raises(ImproperlyConfigured):
        get_settings()
