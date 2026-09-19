"""Create an API token and print it once."""

from argparse import ArgumentParser
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from api_tokens.durations import parse_expiry
from api_tokens.models import ApiToken, DuplicateTokenNameError, TokenScope


class Command(BaseCommand):
    """``manage.py token_create --user alice --name home-assistant [--scope write] [--expires 90d]``.

    The token goes to stdout alone, everything else to stderr, so
    ``TOKEN=$(manage.py token_create …)`` captures exactly the token.
    """

    help = "Create an API token. The token is shown once and cannot be recovered later."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Declare command-line options.

        Args:
            parser: The command's argument parser.
        """
        parser.add_argument("--user", required=True, help="Username of the token owner.")
        parser.add_argument("--name", required=True, help="What will use the token, e.g. home-assistant.")
        parser.add_argument("--scope", choices=TokenScope.values, default=TokenScope.READ, help="Default: read.")
        parser.add_argument("--expires", help="Relative (90d, 12h, 2w, 1y) or ISO date. Default: never.")

    def handle(self, *args: Any, **options: Any) -> None:
        """Create the token and print it.

        Args:
            *args: Unused positional arguments.
            **options: Parsed options.

        Raises:
            CommandError: On unknown user, bad expiry or duplicate name.
        """
        user_model = get_user_model()
        try:
            user = user_model._default_manager.get_by_natural_key(options["user"])
        except user_model.DoesNotExist:
            raise CommandError(f"No user {options['user']!r}.") from None
        try:
            expires_at = parse_expiry(options["expires"]) if options["expires"] else None
            token, raw = ApiToken.issue(user, options["name"], scope=options["scope"], expires_at=expires_at)
        except (ValueError, DuplicateTokenNameError) as exc:
            raise CommandError(str(exc)) from None
        expiry = token.expires_at.isoformat(timespec="minutes") if token.expires_at else "never"
        self.stderr.write(
            f"Created token {token.name!r} for {options['user']} (scope {token.scope}, expires {expiry})."
        )
        self.stderr.write("Store it now; it cannot be shown again:")
        self.stdout.write(raw)
