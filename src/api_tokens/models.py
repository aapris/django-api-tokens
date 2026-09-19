"""The ApiToken model."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from api_tokens import crypto
from api_tokens.conf import get_settings

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

# Collisions in 62**12 are practically impossible; the retry only guards the unique constraint.
KEY_ID_ATTEMPTS = 5


class DuplicateTokenNameError(ValueError):
    """Raised when a user already has an active token with the requested name."""


class TokenScope(models.TextChoices):
    """What a token may do. Enforced by the authentication class."""

    READ = "read", "Read only (GET, HEAD, OPTIONS)"
    WRITE = "write", "Read and write"


class ApiTokenQuerySet(models.QuerySet["ApiToken"]):
    """Query helpers for tokens."""

    def active(self) -> ApiTokenQuerySet:
        """Filter to tokens that are neither revoked nor expired.

        Returns:
            The filtered queryset.
        """
        now = timezone.now()
        return self.filter(revoked_at__isnull=True).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
        )


class ApiToken(models.Model):
    """A named, scoped, revocable API credential belonging to one user.

    Only the SHA-256 of the full token is stored; the token itself is returned once by
    ``issue()`` and cannot be recovered afterwards.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_tokens")
    name = models.CharField(max_length=100, help_text="What uses this token, e.g. 'home-assistant'.")
    key_id = models.CharField(max_length=crypto.KEY_ID_LENGTH, unique=True, editable=False)
    key_hash = models.CharField(max_length=64, editable=False)
    scope = models.CharField(max_length=10, choices=TokenScope.choices, default=TokenScope.READ)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True, editable=False)
    revoked_at = models.DateTimeField(null=True, blank=True, editable=False)

    objects = ApiTokenQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                condition=models.Q(revoked_at__isnull=True),
                name="api_tokens_unique_active_name_per_user",
            )
        ]

    def __str__(self) -> str:
        """Return a label that never contains the secret.

        Returns:
            ``<name> (<prefix>_<key_id>…)``.
        """
        return f"{self.name} ({self.display_id}…)"

    @property
    def display_id(self) -> str:
        """The non-secret beginning of the token, safe to log and show.

        Returns:
            ``<prefix>_<key_id>``.
        """
        return f"{get_settings().prefix}_{self.key_id}"

    @property
    def is_active(self) -> bool:
        """Whether the token can currently authenticate.

        Returns:
            True if not revoked and not expired.
        """
        if self.revoked_at is not None:
            return False
        return self.expires_at is None or self.expires_at > timezone.now()

    @classmethod
    def issue(
        cls,
        user: AbstractBaseUser,
        name: str,
        scope: str = TokenScope.READ,
        expires_at: datetime | None = None,
    ) -> tuple[ApiToken, str]:
        """Create a token for ``user``.

        Args:
            user: Owner of the token; requests made with it act as this user.
            name: Human-readable purpose, unique among the user's active tokens.
            scope: A ``TokenScope`` value.
            expires_at: Optional expiry; None means the token lives until revoked.

        Returns:
            The saved token row and the full token string. The string is not stored anywhere
            and must be handed to the user now.

        Raises:
            DuplicateTokenNameError: If the user already has an active token with this name.
        """
        if cls.objects.filter(user=user, name=name, revoked_at__isnull=True).exists():
            raise DuplicateTokenNameError(f"An active token named {name!r} already exists; revoke it first.")
        prefix = get_settings().prefix
        for attempt in range(KEY_ID_ATTEMPTS):
            key_id = crypto.generate_key_id()
            raw = crypto.build_token(prefix, key_id)
            token = cls(
                user=user,
                name=name,
                scope=scope,
                expires_at=expires_at,
                key_id=key_id,
                key_hash=crypto.hash_token(raw),
            )
            token.full_clean(exclude=["user", "key_id", "key_hash"], validate_constraints=False)
            try:
                with transaction.atomic():
                    token.save()
            except IntegrityError:
                if attempt == KEY_ID_ATTEMPTS - 1 or not cls.objects.filter(key_id=key_id).exists():
                    raise
                continue
            return token, raw
        raise AssertionError("unreachable")  # pragma: no cover

    def revoke(self) -> None:
        """Revoke the token permanently. Revoking twice keeps the first timestamp."""
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])

    def touch(self, now: datetime | None = None) -> None:
        """Record usage, writing at most once per ``last_used_interval`` seconds.

        Args:
            now: Current time; defaults to ``timezone.now()``.
        """
        now = now or timezone.now()
        interval = timedelta(seconds=get_settings().last_used_interval)
        if self.last_used_at is not None and now - self.last_used_at < interval:
            return
        self.last_used_at = now
        # Queryset update: no signals, no race with a concurrent revoke() on other fields.
        type(self).objects.filter(pk=self.pk).update(last_used_at=now)
