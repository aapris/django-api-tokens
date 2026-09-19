"""Admin: read-only listing and the revoke action."""

from django.contrib.auth.models import User
from django.test import Client

from api_tokens.models import ApiToken


def test_admin_lists_and_revokes(user: User) -> None:
    """Superusers see tokens without hashes and can revoke them in bulk.

    Args:
        user: Token owner.
    """
    token, _ = ApiToken.issue(user, "ha")
    User.objects.create_superuser("root", password="pw")
    client = Client()
    client.login(username="root", password="pw")

    changelist = client.get("/admin/api_tokens/apitoken/")
    assert changelist.status_code == 200
    assert token.key_hash not in changelist.content.decode()
    assert client.get("/admin/api_tokens/apitoken/add/").status_code == 403

    detail = client.get(f"/admin/api_tokens/apitoken/{token.pk}/change/")
    assert detail.status_code == 200
    assert token.key_hash not in detail.content.decode()

    client.post(
        "/admin/api_tokens/apitoken/",
        {"action": "revoke_tokens", "_selected_action": [token.pk]},
    )
    token.refresh_from_db()
    assert token.revoked_at is not None
