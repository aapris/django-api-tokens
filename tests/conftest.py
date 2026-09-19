"""Shared fixtures."""

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from api_tokens.models import ApiToken, TokenScope


@pytest.fixture
def user(db: None) -> User:
    """A regular active user.

    Args:
        db: pytest-django database access.

    Returns:
        The user.
    """
    return User.objects.create_user("alice", password="pw")


@pytest.fixture
def api_client() -> APIClient:
    """An unauthenticated DRF test client.

    Returns:
        The client.
    """
    return APIClient()


@pytest.fixture
def read_token(user: User) -> tuple[ApiToken, str]:
    """A read-only token for ``user``.

    Args:
        user: Token owner.

    Returns:
        The token row and the raw token string.
    """
    return ApiToken.issue(user, "reader", scope=TokenScope.READ)


@pytest.fixture
def write_token(user: User) -> tuple[ApiToken, str]:
    """A read-write token for ``user``.

    Args:
        user: Token owner.

    Returns:
        The token row and the raw token string.
    """
    return ApiToken.issue(user, "writer", scope=TokenScope.WRITE)
