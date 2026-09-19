# django-api-tokens

Hashed, named, scoped and revocable API tokens for Django REST Framework — one token
system shared by all my Django projects, so scripts and home automation talk to every
project the same way.

- **One token per client**, named (`home-assistant`, `backup-script`), revocable on its own.
- **Only a SHA-256 hash is stored.** The token is shown once, at creation.
- **Scopes:** `read` (GET/HEAD/OPTIONS) or `write` (everything). Enforced in the
  authentication class, so a view's own `permission_classes` cannot bypass it.
- **Optional expiry** and `last_used_at` tracking (throttled to one write per minute).
- **Recognisable format** `<prefix>_<key_id>_<secret>` with a per-project prefix, so a
  leaked token is obvious in logs and to secret scanners.
- Management commands to create, list and revoke; read-only admin with a revoke action;
  drf-spectacular schema extension when drf-spectacular is installed.

Requires Python ≥ 3.12, Django ≥ 5.2, DRF ≥ 3.15. No other dependencies.

## Token format

```
mydata_Ab12Cd34Ef56_x9Kq…(40 chars)
└─┬──┘ └────┬─────┘ └──┬──┘
prefix   key_id      secret
```

- `prefix`: `API_TOKENS["PREFIX"]`, by convention the project's name.
- `key_id`: 12 random base62 characters, stored in clear for lookup. With the prefix it
  forms the token's **ID** (`mydata_Ab12Cd34Ef56`), which is safe to log and show.
- `secret`: 40 random base62 characters (~238 bits), never stored.

Only `sha256(full token)` is stored. A slow password hash is unnecessary because the
input is random and far too long to brute-force.

## Installation

```bash
uv add "django-api-tokens @ git+ssh://git@github.com/<owner>/django-api-tokens.git@v0.1.0"
```

```python
# settings.py
INSTALLED_APPS = [
    ...,
    "rest_framework",
    "api_tokens",
]

API_TOKENS = {
    "PREFIX": "mydata",          # the project name; [a-z][a-z0-9_]{1,31}; default "tok"
    # "KEYWORD": "Bearer",       # Authorization scheme
    # "LAST_USED_INTERVAL": 60,  # seconds between last_used_at writes
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api_tokens.authentication.ApiTokenAuthentication",   # FIRST, see below
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}
```

```bash
python manage.py migrate api_tokens
```

**Put `ApiTokenAuthentication` first.** DRF builds the `WWW-Authenticate` header from the
first authentication class. `SessionAuthentication` has none, so with it first an
unauthenticated API call gets `403` instead of `401`, and HTTP clients that retry with
credentials on 401 misbehave.

**Drop `BasicAuthentication`.** It sends the account password with every request and
gives every script full account rights, which is exactly what tokens replace.

## Managing tokens

```bash
# Create. The token alone goes to stdout, details to stderr:
python manage.py token_create --user alice --name home-assistant                  # read-only, no expiry
python manage.py token_create --user alice --name backup --scope write --expires 90d
TOKEN=$(python manage.py token_create --user alice --name ci --expires 2027-01-31)

# List. Never shows secrets or hashes:
python manage.py token_list                 # active tokens
python manage.py token_list --all --user alice

# Revoke by ID, bare key id, or a pasted leaked token:
python manage.py token_revoke mydata_Ab12Cd34Ef56
```

`--expires` takes `12h`, `90d`, `2w`, `1y`, an ISO datetime, or an ISO date (the end of
that day in the project time zone).

**Rotation:** names are unique among a user's *active* tokens, so rotate with
`token_revoke` followed by `token_create` with the same name.

The admin lists tokens read-only and has a *Revoke selected tokens* action. Creating
tokens there is disabled on purpose: the secret must be shown exactly once.

Programmatic use:

```python
from api_tokens.models import ApiToken, TokenScope

token, raw = ApiToken.issue(user, "home-assistant", scope=TokenScope.READ)
token.revoke()
```

## Using a token

```bash
curl -H "Authorization: Bearer $TOKEN" https://mydata.example.ts.net/api/logbook/records/
```

Home Assistant (`configuration.yaml`, with `mydata_auth: "Bearer mydata_…"` in
`secrets.yaml`):

```yaml
rest:
  - resource: https://mydata.example.ts.net/api/logbook/records/
    headers:
      Authorization: !secret mydata_auth
    sensor:
      - name: Latest logbook entry
        value_template: "{{ value_json.results[0].description }}"
```

Python:

```python
import httpx

client = httpx.Client(base_url="https://mydata.example.ts.net", headers={"Authorization": f"Bearer {token}"})
client.get("/api/logbook/records/").raise_for_status()
```

Token requests carry no cookies and are therefore exempt from CSRF, so `write` tokens
can POST directly.

## Behaviour reference

| Request | Result |
|---|---|
| No `Authorization` header | Next authenticator; with `IsAuthenticated`: `401` + `WWW-Authenticate: Bearer realm="api"` |
| `Bearer` + another prefix, or not token-shaped (e.g. a JWT) | Ignored, next authenticator runs |
| `Bearer` + our prefix, but unknown ID / wrong secret / revoked / expired / inactive user | `401 {"detail": "Invalid or inactive token."}`: one message for all, logged as a warning with the token ID |
| `Bearer a b` (malformed) | `401` |
| `read` token with POST/PUT/PATCH/DELETE | `403` |
| Valid token | `request.user` is the owner, `request.auth` the `ApiToken` row |

Tokens authenticate **DRF views only**. Plain Django views (`@login_required` pages)
keep using the session.

## Conventions across projects

1. `PREFIX` is the project name (`mydata`; `mydata_dev` for a dev instance if it helps
   to tell them apart).
2. One token per client and machine; the name says which (`ha-livingroom`, `laptop-scripts`).
3. Prefer `read`; use `write` only for clients that create or change data.
4. Unattended automation may use tokens without expiry; ad-hoc use gets `--expires`.
5. Keep tokens in the client's secret store (HA `secrets.yaml`, a password manager, a
   gitignored `.env`), never in a repository.

## Development

```bash
just setup                        # uv sync + git hooks
just ci                           # lint + tests
just cov                          # tests with coverage
just makemigrations -n <name>     # after a model change
```

Tests run against SQLite with the minimal settings in `tests/settings.py`.
