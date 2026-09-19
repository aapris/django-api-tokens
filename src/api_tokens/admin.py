"""Admin: list and revoke tokens. Tokens are created with ``manage.py token_create``.

Creation is not offered here because the secret must be shown exactly once, and an admin
change form is a poor place for that.
"""

from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest

from api_tokens.models import ApiToken


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    """Read-only token listing with a revoke action."""

    list_display = ["name", "user", "display_id", "scope", "created_at", "expires_at", "last_used_at", "revoked_at"]
    list_filter = ["scope", ("revoked_at", admin.EmptyFieldListFilter)]
    search_fields = ["name", "key_id", "user__username"]
    readonly_fields = [f.name for f in ApiToken._meta.fields if f.name != "key_hash"]
    exclude = ["key_hash"]
    actions = ["revoke_tokens"]

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Disallow creating tokens from the admin.

        Args:
            request: Current request.

        Returns:
            Always False.
        """
        return False

    def has_change_permission(self, request: HttpRequest, obj: ApiToken | None = None) -> bool:
        """Make the change form read-only while keeping list actions available.

        Args:
            request: Current request.
            obj: Token being viewed, if any.

        Returns:
            False for a single object, the default permission for the changelist.
        """
        return obj is None and super().has_change_permission(request)

    @admin.action(description="Revoke selected tokens")
    def revoke_tokens(self, request: HttpRequest, queryset: QuerySet[ApiToken]) -> None:
        """Revoke every selected token.

        Args:
            request: Current request.
            queryset: Selected tokens.
        """
        count = 0
        for token in queryset.filter(revoked_at__isnull=True):
            token.revoke()
            count += 1
        self.message_user(request, f"Revoked {count} token(s).", messages.SUCCESS)
