"""Package settings, read from ``settings.API_TOKENS`` with defaults."""

import re
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

# The prefix ends up in the token itself, so keep it to characters that survive
# shells, URLs and headers unquoted. Underscores are allowed: parsing splits from the right.
PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


@dataclass(frozen=True)
class ApiTokenSettings:
    """Resolved package settings.

    Attributes:
        prefix: Project-specific token prefix, e.g. ``mydata``. Makes leaked tokens
            recognisable to secret scanners and to humans.
        keyword: Authorization header scheme, ``Bearer`` by default.
        last_used_interval: Minimum seconds between two ``last_used_at`` writes of one token.
    """

    prefix: str = "tok"
    keyword: str = "Bearer"
    last_used_interval: int = 60


def get_settings() -> ApiTokenSettings:
    """Build the settings object from ``settings.API_TOKENS``.

    Read on every call (it is a dict lookup) so ``override_settings`` works in tests.

    Returns:
        The resolved settings.

    Raises:
        ImproperlyConfigured: If a key is unknown or the prefix is malformed.
    """
    raw = {key.lower(): value for key, value in getattr(settings, "API_TOKENS", {}).items()}
    unknown = set(raw) - set(ApiTokenSettings.__dataclass_fields__)
    if unknown:
        raise ImproperlyConfigured(f"Unknown API_TOKENS setting(s): {', '.join(sorted(unknown))}")
    resolved = ApiTokenSettings(**raw)
    if not PREFIX_PATTERN.match(resolved.prefix):
        raise ImproperlyConfigured(
            f"API_TOKENS['PREFIX'] must match {PREFIX_PATTERN.pattern}, got {resolved.prefix!r}"
        )
    return resolved
