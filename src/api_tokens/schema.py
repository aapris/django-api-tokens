"""drf-spectacular extension: document ApiTokenAuthentication as HTTP Bearer auth.

Imported from ``AppConfig.ready()`` only when drf-spectacular is installed; the package
does not depend on it.
"""

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema

from api_tokens.conf import get_settings


class ApiTokenScheme(OpenApiAuthenticationExtension):
    """OpenAPI security scheme for API tokens."""

    target_class = "api_tokens.authentication.ApiTokenAuthentication"
    name = "apiToken"

    def get_security_definition(self, auto_schema: AutoSchema) -> dict[str, Any]:
        """Describe the scheme.

        Args:
            auto_schema: The schema generator for the current view.

        Returns:
            An OpenAPI ``http`` bearer security scheme.
        """
        prefix = get_settings().prefix
        return {
            "type": "http",
            "scheme": "bearer",
            "description": f"API token `{prefix}_<key_id>_<secret>` from `manage.py token_create`.",
        }
