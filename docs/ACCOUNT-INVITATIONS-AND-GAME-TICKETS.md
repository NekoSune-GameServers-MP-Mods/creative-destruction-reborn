# Account service — invitations and one-use game tickets

This is the dedicated `account` branch. Its GitHub Actions workflow publishes ONLY:

`ghcr.io/nekosune-gameservers-mp-mods/creative-destruction-reborn/account-api:branch-account`

The service provides `POST /v1/login`, `POST /v1/game-ticket`, `POST /v1/register`, `POST /v1/admin/invitations`, `POST /v1/logout` and `GET /v1/me`. It listens internally on 8090, ordinarily bound to the container network and published to **127.0.0.1 only** on the VPS host (often host port 8091).

**Never expose the raw account API directly to the internet over HTTP.** Put it behind a trusted HTTPS reverse proxy with a verified certificate. For example, with Caddy after creating DNS `auth.example.com` pointing at the VPS, a Caddyfile can contain:

```caddy
auth.example.com {
  reverse_proxy 127.0.0.1:8091
}
```

Adjust host port to your actual `compose.yaml`. TLS certificates are automatically managed by Caddy when correctly configured; this is **separate** from the certificate required for the game server's custom TLS TCP ports.

## Invitations without sharing your admin key

Only the operator with `CDR_REGISTRATION_KEY` creates invites. HTTP request:
- `POST https://auth.example.com/v1/admin/invitations`
- Header `X-Registration-Key`: your existing private 32+ character registration secret
- JSON body `{"lifetime_seconds":86400}` (60 seconds to 7 days)
- Response `{"invite_code":"...", "expires_at":...}`

A player can then call `POST /v1/register` with `{"username":"ExamplePlayer","password":"strong unique password","invite_code":"..."}`. The code can only be used once; failed duplicate-name registration rolls its use back. Username must be 3–24 supported characters; password 12–128 characters. Rate limits apply.

**Do not distribute the admin registration key to players.** Create one invitation per player; give it to them privately. A Windows helper under the `server` branch, `reborn/tools/steam_register.py`, prompts for the invite and password over HTTPS.

## Game tickets

`POST /v1/game-ticket` requires an existing valid Reborn `Authorization: Bearer ...` account session (from `/v1/login`). It issues a **single-use 45-second ticket**, deleting older pending codes for that account. Only its SHA-256 digest is stored in SQLite. The server's `game_identity.py` atomically redeems the ticket at `C_LOGIN_AUTH`.

The bearer token stays on the HTTPS Windows bridge; account passwords and long-lived bearer tokens are **never sent over the game's NeoX protocol**. The game TCP ports must be protected by TLS before opening to remote users.

**Database sharing:** account-api and game-server MUST mount the same `/app/reborn/server/save/accounts.sqlite3` and SQLite WAL sidecar storage under the same persistent volume. This design is suitable for the *same VPS*, not a shared SQLite file mounted by independent remote nodes. True multi-VPS hosting needs a central authenticated account/identity service and a multi-node ticket-validation API.

Other security work still needed: account recovery, moderation/bans, rate-limit storage shared across replicated API instances, and load testing.
