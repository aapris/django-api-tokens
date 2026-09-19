"""Token generation, parsing and hashing.

A token looks like ``<prefix>_<key_id>_<secret>``:

- ``prefix``: project-specific, from settings (``mydata``);
- ``key_id``: 12 random base62 characters, stored in clear and used for lookup;
- ``secret``: 40 random base62 characters (~238 bits), never stored.

Only the SHA-256 of the whole token is stored. A slow password hash is unnecessary
because the input is uniformly random and far too long to brute-force.
"""

import hashlib
import hmac
import secrets
import string
from dataclasses import dataclass

ALPHABET = string.ascii_letters + string.digits
KEY_ID_LENGTH = 12
SECRET_LENGTH = 40


@dataclass(frozen=True)
class ParsedToken:
    """The parts of a token string.

    Attributes:
        prefix: Project prefix.
        key_id: Public lookup identifier.
        raw: The full token string as presented.
    """

    prefix: str
    key_id: str
    raw: str


def _random_string(length: int) -> str:
    """Return a cryptographically random base62 string.

    Args:
        length: Number of characters.

    Returns:
        The random string.
    """
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def generate_key_id() -> str:
    """Return a new random key identifier.

    Returns:
        A base62 string of ``KEY_ID_LENGTH`` characters.
    """
    return _random_string(KEY_ID_LENGTH)


def build_token(prefix: str, key_id: str) -> str:
    """Assemble a full token with a fresh secret.

    Args:
        prefix: Project prefix.
        key_id: Key identifier of the token row.

    Returns:
        The full token string. It is shown to the user once and never stored.
    """
    return f"{prefix}_{key_id}_{_random_string(SECRET_LENGTH)}"


def parse_token(raw: str) -> ParsedToken | None:
    """Split a token string into its parts.

    Args:
        raw: Token as presented by a client.

    Returns:
        The parsed token, or None if the string does not have the token shape.
    """
    parts = raw.rsplit("_", 2)
    if len(parts) != 3:  # prefix, key id, secret
        return None
    prefix, key_id, secret = parts
    if not prefix or len(key_id) != KEY_ID_LENGTH or len(secret) != SECRET_LENGTH:
        return None
    if not set(key_id + secret) <= set(ALPHABET):
        return None
    return ParsedToken(prefix=prefix, key_id=key_id, raw=raw)


def hash_token(raw: str) -> str:
    """Hash a full token for storage.

    Args:
        raw: The full token string.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(raw.encode()).hexdigest()


def token_matches(raw: str, stored_hash: str) -> bool:
    """Compare a presented token against a stored hash in constant time.

    Args:
        raw: The full token string.
        stored_hash: Hex digest from the database.

    Returns:
        True if the token hashes to ``stored_hash``.
    """
    return hmac.compare_digest(hash_token(raw), stored_hash)
