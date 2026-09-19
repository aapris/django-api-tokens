"""Revoke an API token."""

from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from api_tokens.conf import get_settings
from api_tokens.models import ApiToken


class Command(BaseCommand):
    """``manage.py token_revoke mydata_Ab12Cd34Ef56`` (the ID column of ``token_list``).

    The full token works too, so a leaked token can be revoked by pasting it.
    """

    help = "Revoke an API token by its ID (prefix_keyid) or the full token."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Declare command-line arguments.

        Args:
            parser: The command's argument parser.
        """
        parser.add_argument("token_id", help="Token ID as shown by token_list, or the full token.")

    def handle(self, *args: Any, **options: Any) -> None:
        """Revoke the token.

        Args:
            *args: Unused positional arguments.
            **options: Parsed options.

        Raises:
            CommandError: If no token matches.
        """
        prefix = get_settings().prefix
        value: str = options["token_id"].removeprefix(f"{prefix}_")
        key_id = value.split("_", 1)[0]
        token = ApiToken.objects.filter(key_id=key_id).first()
        if token is None:
            raise CommandError(f"No token with ID {options['token_id']!r}.")
        if token.revoked_at is not None:
            self.stderr.write(
                f"Token {token} was already revoked at {token.revoked_at.isoformat(timespec='minutes')}."
            )
            return
        token.revoke()
        self.stderr.write(f"Revoked token {token}.")
