"""Django app configuration."""

import contextlib

from django.apps import AppConfig


class ApiTokensConfig(AppConfig):
    """App config for api_tokens."""

    name = "api_tokens"
    verbose_name = "API tokens"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """Register the OpenAPI extension if drf-spectacular is installed."""
        with contextlib.suppress(ImportError):
            import api_tokens.schema  # noqa: F401 - registers itself on import
