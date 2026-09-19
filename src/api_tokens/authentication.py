"""DRF authentication class for API tokens."""

import logging

from django.contrib.auth.models import AbstractBaseUser
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.permissions import SAFE_METHODS
from rest_framework.request import Request

from api_tokens import crypto
from api_tokens.conf import get_settings
from api_tokens.models import ApiToken, TokenScope

logger = logging.getLogger(__name__)

INVALID_TOKEN = "Invalid or inactive token."


class ApiTokenAuthentication(BaseAuthentication):
    """Authenticate ``Authorization: Bearer <prefix>_<key_id>_<secret>`` headers.

    Scope is enforced here rather than in a permission class: views that set their own
    ``permission_classes`` replace the defaults, which would silently turn a read-only
    token into a read-write one. Authentication runs for every DRF view, so this cannot
    be bypassed.

    A Bearer token with a different prefix is ignored (returns None), so another Bearer
    scheme (e.g. JWT) can be listed after this class.
    """

    def authenticate(self, request: Request) -> tuple[AbstractBaseUser, ApiToken] | None:
        """Resolve the request's token to a user.

        Args:
            request: The DRF request.

        Returns:
            ``(user, token)`` on success, or None if the request carries no token of ours.

        Raises:
            AuthenticationFailed: If the token is ours but unknown, wrong, revoked or expired.
            PermissionDenied: If the token's scope does not allow the request method.
        """
        conf = get_settings()
        raw = self._raw_token(request, conf.keyword)
        if raw is None:
            return None
        parsed = crypto.parse_token(raw)
        if parsed is None or parsed.prefix != conf.prefix:
            return None
        token = self._verify(parsed)
        self._check_scope(token, request.method)
        token.touch()
        return token.user, token

    def authenticate_header(self, request: Request) -> str:
        """Value for ``WWW-Authenticate`` so unauthenticated requests get 401, not 403.

        Args:
            request: The DRF request.

        Returns:
            The challenge string.
        """
        return f'{get_settings().keyword} realm="api"'

    @staticmethod
    def _raw_token(request: Request, keyword: str) -> str | None:
        """Extract the token string from the Authorization header.

        Args:
            request: The DRF request.
            keyword: Expected auth scheme, compared case-insensitively.

        Returns:
            The credential part, or None if the header uses another scheme.

        Raises:
            AuthenticationFailed: If the scheme matches but the header is malformed.
        """
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != keyword.lower().encode():
            return None
        if len(parts) != 2:  # scheme + credential
            raise exceptions.AuthenticationFailed("Malformed Authorization header.")
        try:
            return parts[1].decode("ascii")
        except UnicodeDecodeError:
            raise exceptions.AuthenticationFailed("Malformed Authorization header.") from None

    @staticmethod
    def _verify(parsed: crypto.ParsedToken) -> ApiToken:
        """Look the token up and check its secret and state.

        Every failure gives the same message so a client cannot probe which key ids exist.

        Args:
            parsed: The parsed token.

        Returns:
            The matching active token with its user loaded.

        Raises:
            AuthenticationFailed: On any mismatch.
        """
        token = ApiToken.objects.select_related("user").filter(key_id=parsed.key_id).first()
        if token is None or not crypto.token_matches(parsed.raw, token.key_hash):
            logger.warning("API token rejected: unknown key or wrong secret (%s_%s)", parsed.prefix, parsed.key_id)
            raise exceptions.AuthenticationFailed(INVALID_TOKEN)
        if not token.is_active or not token.user.is_active:
            logger.warning("API token rejected: revoked, expired or inactive user (%s)", token.display_id)
            raise exceptions.AuthenticationFailed(INVALID_TOKEN)
        return token

    @staticmethod
    def _check_scope(token: ApiToken, method: str) -> None:
        """Refuse unsafe methods for read-only tokens.

        Args:
            token: The authenticated token.
            method: HTTP method of the request.

        Raises:
            PermissionDenied: If the scope does not allow ``method``.
        """
        if token.scope == TokenScope.WRITE or method in SAFE_METHODS:
            return
        raise exceptions.PermissionDenied(f"Token scope '{token.scope}' does not allow {method} requests.")
