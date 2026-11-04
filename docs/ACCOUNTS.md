# Secure account service (foundation)

This PR adds **independent persisted account management**, but the original game login is **not wired to the account store**. This is deliberately fail-closed for remote game connections. Do not advertise this as functioning multiplayer authentication.

## Private REST API (SSH tunnel only)
Run `docker compose -f compose.vps.yaml up --build -d`. The account service listens on **127.0.0.1:8090 on the VPS** and is reachable using `ssh -L 8090:127.0.0.1:8090 user@vps`.

Use a new `CDR_REGISTRATION_KEY` (separate from `CDR_STAFF_TOKEN`) and **never publish it**. Never use the original NetEase login or password.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | /v1/register | Add invited player with JSON username/password plus X-Registration-Key; disabled if registration secret is missing |
| POST | /v1/login | Check password and issue random 12-hour session token |
| GET | /v1/me | Validate Authorization: Bearer token |
| POST | /v1/logout | Revoke Bearer token; expects JSON body `{}` |

Example local SSH-tunneled invitation (replace placeholder values and do not put secrets in Git):
```sh
curl -s -X POST http://127.0.0.1:8090/v1/register \
  -H 'Content-Type: application/json' \
  -H 'X-Registration-Key: YOUR_PRIVATE_REGISTRATION_KEY' \
  -d '{"username":"NewPlayer","password":"long-random-player-password"}'
```
Then login:
```sh
curl -s -X POST http://127.0.0.1:8090/v1/login -H 'Content-Type: application/json' \
  -d '{"username":"NewPlayer","password":"long-random-player-password"}'
```

## Properties
- Standard-library SQLite database `save/accounts.sqlite3` with separate accounts and sessions tables and stable user IDs.
- Passwords stored as scrypt hashes (random 16-byte salt; parameters N=16384,r=8,p=1). Never store or log plaintext passwords.
- Session bearer tokens use 48 random bytes (URL-safe), 12-hour expiry, SHA-256 digest only in database.
- Unique case-insensitive usernames, 12+ character passwords, duplicate protection, disabled-user support, explicit logout and revoke-all.
- Login and registration limited to a small number of attempts per client/account window (in-process limiter).
- Database persists in Docker volume `cdr_save`, not rebuilt on upgrades.
- Private auth API is HTTP; **do not expose it outside localhost**. Use SSH tunneling, never public port-forwarding. Requests are not TLS-protected internally.
- No MFA, password reset, email verification, revocation UI, recovery codes or operator RBAC yet. Rate limit state is in-memory and not suitable for distributed production deployments.

## Critical integration blocker
The original Reborn game protocol sends `C_LOGIN_AUTH` followed by `C_LOGIN_ENTER`, `C_FIGHT_LOGIN` / `C_FIGHT_REQ_LOGIN`. It currently uses shared `SAVE`, `GATE`, and `FIGHT_STATE` and static `offline_sn`/battle keys. Connecting multiple clients would allow account/state confusion.

**Until those state holders are replaced with isolated per-account/per-match objects and authenticated handoff tickets, remote game login is explicitly refused.** The existing local offline simulation remains available on 127.0.0.1. The independently working account API does not imply playable secure multiplayer.

## Before enabling remote game clients
1. Build and verify a client login UI/protocol flow using a private account, rather than a static session or original NetEase credentials.
2. Bind every login, gateway and battle connection to the same verified account by expiring one-use tickets; refuse unauthorized gameplay and debug commands.
3. Move inventory, cosmetics, matchmaking and battle state to account/session-scoped storage; unique player and unit IDs.
4. Add per-message rate limiting, replay defense, account lockout/audit, integration and adversarial concurrent-client tests, secure tunnel or TLS.
5. Add staff RBAC and MFA plus separation of staff credentials from player credentials.
