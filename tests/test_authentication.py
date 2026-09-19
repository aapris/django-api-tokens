"""End-to-end authentication through DRF views."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from api_tokens import crypto
from api_tokens.models import ApiToken


def _auth(client: APIClient, raw: str, keyword: str = "Bearer") -> APIClient:
    """Attach a token header to the client.

    Args:
        client: Test client.
        raw: Token string.
        keyword: Auth scheme.

    Returns:
        The same client.
    """
    client.credentials(HTTP_AUTHORIZATION=f"{keyword} {raw}")
    return client


def test_valid_token_authenticates(api_client: APIClient, read_token: tuple[ApiToken, str]) -> None:
    """A valid token acts as its user and records usage.

    Args:
        api_client: Test client.
        read_token: Token under test.
    """
    token, raw = read_token
    response = _auth(api_client, raw).get("/echo/")
    assert response.status_code == 200
    assert response.json() == {"user": "alice"}
    token.refresh_from_db()
    assert token.last_used_at is not None


def test_keyword_is_case_insensitive(api_client: APIClient, read_token: tuple[ApiToken, str]) -> None:
    """``bearer`` works like ``Bearer``.

    Args:
        api_client: Test client.
        read_token: Token under test.
    """
    assert _auth(api_client, read_token[1], "bearer").get("/echo/").status_code == 200


def test_no_header_gets_401_with_challenge(api_client: APIClient, db: None) -> None:
    """Anonymous requests get 401 and a Bearer challenge (not 403).

    Args:
        api_client: Test client.
        db: Database access.
    """
    response = api_client.get("/echo/")
    assert response.status_code == 401
    assert response["WWW-Authenticate"] == 'Bearer realm="api"'


@pytest.mark.parametrize("mutation", ["wrong_secret", "unknown_key_id", "revoked", "expired", "inactive_user"])
def test_rejected_tokens(api_client: APIClient, user: User, mutation: str) -> None:
    """Every kind of bad token gets the same 401 message.

    Args:
        api_client: Test client.
        user: Token owner.
        mutation: What is wrong with the token.
    """
    token, raw = ApiToken.issue(user, "ha")
    if mutation == "wrong_secret":
        raw = crypto.build_token("test", token.key_id)
    elif mutation == "unknown_key_id":
        raw = crypto.build_token("test", crypto.generate_key_id())
    elif mutation == "revoked":
        token.revoke()
    elif mutation == "expired":
        ApiToken.objects.filter(pk=token.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
    elif mutation == "inactive_user":
        User.objects.filter(pk=user.pk).update(is_active=False)
    response = _auth(api_client, raw).get("/echo/")
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or inactive token."}


def test_malformed_header_rejected(api_client: APIClient, db: None) -> None:
    """``Bearer`` with extra parts is an error, not an anonymous request.

    Args:
        api_client: Test client.
        db: Database access.
    """
    assert _auth(api_client, "a b").get("/echo/").status_code == 401


@pytest.mark.parametrize("raw", ["other_" + "a" * 12 + "_" + "b" * 40, "eyJhbGciOiJIUzI1NiJ9.e30.sig"])
def test_foreign_bearer_tokens_are_ignored(api_client: APIClient, db: None, raw: str) -> None:
    """Other prefixes and non-token Bearer values fall through to other authenticators.

    Args:
        api_client: Test client.
        db: Database access.
        raw: A Bearer credential that is not ours.
    """
    response = _auth(api_client, raw).get("/echo/")
    assert response.status_code == 401
    assert response.json()["detail"] != "Invalid or inactive token."


@pytest.mark.parametrize("path", ["/echo/", "/open-echo/"])
def test_read_scope_blocks_unsafe_methods(api_client: APIClient, read_token: tuple[ApiToken, str], path: str) -> None:
    """Read tokens can GET but not POST/DELETE, even on views with their own permission_classes.

    Args:
        api_client: Test client.
        read_token: Read-only token.
        path: Endpoint under test.
    """
    client = _auth(api_client, read_token[1])
    assert client.get(path).status_code == 200
    assert client.post(path).status_code == 403
    assert client.delete(path).status_code == 403


def test_write_scope_allows_unsafe_methods(api_client: APIClient, write_token: tuple[ApiToken, str]) -> None:
    """Write tokens can POST without a CSRF token.

    Args:
        api_client: Test client.
        write_token: Read-write token.
    """
    client = APIClient(enforce_csrf_checks=True)
    assert _auth(client, write_token[1]).post("/echo/").status_code == 200
