"""List API tokens without revealing secrets."""

from argparse import ArgumentParser
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from api_tokens.models import ApiToken

COLUMNS = ("ID", "USER", "NAME", "SCOPE", "CREATED", "EXPIRES", "LAST USED", "STATE")


def _fmt(value: Any) -> str:
    """Format an optional datetime for the table.

    Args:
        value: A datetime or None.

    Returns:
        ``YYYY-MM-DD HH:MM`` or ``-``.
    """
    return value.strftime("%Y-%m-%d %H:%M") if value else "-"


class Command(BaseCommand):
    """``manage.py token_list [--user alice] [--all]``."""

    help = "List API tokens (active only unless --all)."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Declare command-line options.

        Args:
            parser: The command's argument parser.
        """
        parser.add_argument("--user", help="Only this user's tokens.")
        parser.add_argument("--all", action="store_true", help="Include revoked and expired tokens.")

    def handle(self, *args: Any, **options: Any) -> None:
        """Print the token table.

        Args:
            *args: Unused positional arguments.
            **options: Parsed options.
        """
        tokens = ApiToken.objects.select_related("user")
        if not options["all"]:
            tokens = tokens.active()
        if options["user"]:
            tokens = tokens.filter(**{f"user__{get_user_model().USERNAME_FIELD}": options["user"]})
        rows = [COLUMNS] + [
            (
                t.display_id,
                t.user.get_username(),
                t.name,
                t.scope,
                _fmt(t.created_at),
                _fmt(t.expires_at),
                _fmt(t.last_used_at),
                "active" if t.is_active else ("revoked" if t.revoked_at else "expired"),
            )
            for t in tokens
        ]
        widths = [max(len(row[i]) for row in rows) for i in range(len(COLUMNS))]
        for row in rows:
            self.stdout.write("  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip())
