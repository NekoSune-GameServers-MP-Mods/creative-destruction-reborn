# Authenticated remote Steam login — separate accounts, Steam bridge and TLS

This implementation is on the **`server` branch** (account issuance on `account`). It replaces the original unconditional `S_LOGIN_AUTH err_code=1` remote rejection with **verified, account-scoped handoffs** when explicitly enabled. It is **not a finished shared-world multiplayer release**: matches remain isolated per player, and cross-player visibility, server-authoritative combat/anti-cheat, testing with two real Steam clients, and moderation still need work.

## What the original VPS log established

Steam 3.0.248.0 reached TCP 4000 with `C_LOGIN_AUTH`, but the precompiled local mod always sent `sauth_json={}` and `sdkuid=offline_player`. Those are **not credentials**, so permitting them as public accounts would let anybody impersonate anybody.

## New authenticated connection sequence

1. A Reborn player uses `steam_bridge.py` on their own Windows PC. The bridge binds **only 127.0.0.1** ports 8000, 4000, 4001, 4002 and can be used with the existing precompiled `switches.nxs` without recompilation.
2. The bridge sends the player's username/password through **HTTPS** to `account-api /v1/login`. The bearer token remains **in the bridge process memory**, never written to disk.
3. The game uses the localhost HTTP discovery bridge. It sees the real zone name but a **local login endpoint**.
4. At each Steam `C_LOGIN_AUTH`, the bridge obtains a fresh, one-use **45-second ticket** via HTTPS `/v1/game-ticket` and injects it as `sauth_json={"game_ticket":"..."}`.
5. The bridge establishes certificate-verified **TLS** connections from Windows to the VPS for TCP login 4000, gateway 4001 and battle 4002. The legacy NeoX game sees ordinary plaintext only on Windows loopback.
6. The VPS game server atomically redeems that ticket from the shared account SQLite database. Reuse or expired tickets return `err_code=1`. A verified login receives `S_LOGIN_AUTH err_code=0` and an independent one-use `auth_sn`.
7. The bridge rewrites the successful zone's gateway IP to `127.0.0.1`. The game then redeems the `auth_sn` on its gateway connection; an unauthenticated gateway cannot invoke gameplay handlers.
8. Match selection creates a **separate, per-player match** and an expiring one-use battle key. The bridge rewrites the battle IP to loopback, and the server verifies the battle key and the player's UID.
9. Player save, lobby pointer, active battle, unit ID, and battle metadata are **scoped to the authenticated connection**. Save rows are keyed by verified account ID in SQLite, not by the legacy global `player.json`.

**Important limitation:** Players can have distinct verified logins on the same VPS, but they do **not yet see each other or fight in a shared live room**. The stage-isolation code is an intermediate step toward genuine multiplayer, not a claim of functional shared matches.

## VPS setup using YOUR existing compose.yaml

These commands use `/opt/stacks/creative-destruction`, and the deployment file is **`compose.yaml`** (not `compose.vps.yaml`). Do not overwrite locally customised host ports or secrets.

Before running anything, ensure you have a DNS hostname for the game TLS certificate, e.g. `game.example.com`, and a separate **HTTPS** account API address, e.g. `https://auth.example.com`. The game server needs a certificate whose DNS SAN matches the bridge's `--game-tls-hostname`. Use a CA-trusted certificate and **do not disable certificate verification**. Publish only TCP 8000, 4000, 4001 and 4002 on the game service; keep the raw account API bound to 127.0.0.1 on the host, behind your HTTPS reverse proxy. Do not expose account port 8090/8091 directly.

On the VPS:
```bash
cd /opt/stacks/creative-destruction
git fetch origin server account
git show origin/server:compose.authenticated.yaml > compose.authenticated.yaml
```

Create protected host files containing the game TLS certificate and private key. The key must be readable by the non-root Docker UID **10001** but not world-readable. Use secure backups and rotate them when certificates renew. Add **paths only** to your local `.env`:

```dotenv
CDR_GAME_TLS_CERT_HOST=/opt/stacks/creative-destruction/secrets/game-fullchain.pem
CDR_GAME_TLS_KEY_HOST=/opt/stacks/creative-destruction/secrets/game-key.pem

CDR_GAME_SERVER_IMAGE=ghcr.io/nekosune-gameservers-mp-mods/creative-destruction-reborn/game-server:branch-server
CDR_ACCOUNT_API_IMAGE=ghcr.io/nekosune-gameservers-mp-mods/creative-destruction-reborn/account-api:branch-account
```

**Both containers must mount the SAME persistent `/app/reborn/server/save` data volume.** Otherwise the game server cannot consume account tickets created by the account API. The standard `compose.vps.yaml` does this; verify it on your customised `compose.yaml`.

Check the Compose merge BEFORE deploying, then update only the two relevant containers:
```bash
docker compose -f compose.yaml -f compose.authenticated.yaml config --quiet
docker compose -f compose.yaml -f compose.authenticated.yaml config --services
docker compose -f compose.yaml -f compose.authenticated.yaml pull game-server account-api
docker compose -f compose.yaml -f compose.authenticated.yaml up -d --no-deps game-server account-api
docker compose -f compose.yaml -f compose.authenticated.yaml ps
docker compose -f compose.yaml -f compose.authenticated.yaml logs --tail=60 game-server account-api
```

If your service names or save mounts differ, align the overlay with the actual `compose.yaml` first. **Do not run `down -v`**; it deletes persistent game/account storage.

Ensure the account API is published through an HTTPS reverse proxy to its **loopback host port**, such as 8091, and that the HTTPS certificate is valid. HTTP discovery on 8000 remains plaintext because it only distributes public login-list information; the three game TCP ports require TLS when authenticated mode is enabled.

## Invite and register other players

Registration remains closed to unauthorised strangers. The administrator generates a single-use invite via `POST /v1/admin/invitations` using the existing **private** 32+ character `X-Registration-Key`, over HTTPS. Example request body: `{"lifetime_seconds":86400}`. Never publish or share the administrator key. The response includes an `invite_code` which you give privately to a player. Each code expires and works once.

On **each player's own Windows PC**, with Python 3.9+ installed in their game directory:

```powershell
cd "D:\\SteamLibrary\\steamapps\\common\\CreativeDestruction"
python .\\reborn\\tools\\steam_register.py --auth-url https://auth.example.com --username MyRebornUser
```

The script prompts privately for the **invite** and **account password**. Every player has their own username/password. Do **not** give others your private `CDR_REGISTRATION_KEY`.

## Connect using the EXISTING switches.nxs on Windows

First make sure the old offline localhost server is **not** running, because the bridge needs local ports 8000, 4000, 4001 and 4002.

In each player's game folder, tell the original mod to use localhost discovery (this creates a backup):
```powershell
python .\\reborn\\tools\\patch_server.py --game-dir . --server-ip 127.0.0.1
```

Start the bridge, using your real VPS IPv4 and the **DNS name matching the VPS game TLS certificate**:
```powershell
python .\\reborn\\tools\\steam_bridge.py --game-server 75.119.148.51 --game-tls-hostname game.example.com --auth-url https://auth.example.com --username MyRebornUser
```

Enter your account password at the prompt. Leave this bridge running, start your own installed Steam Creative Destruction client normally, choose the server, and press Play. The bridge obtains a NEW one-use ticket for each login automatically. No manual 45-second timing and **no rebuilt `switches.nxs` are required for this bridge path**.

Check server logs:
```bash
docker compose -f compose.yaml -f compose.authenticated.yaml exec -T game-server \
  tail -n 100 -f /app/reborn/server/logs/server.log
```

Expected first successful authentication line: `[login] verified account <id>; gateway handoff issued` and `S_LOGIN_AUTH err_code=0`. The server logs now redact `sauth_json`, `auth_sn`, `login_key`, `device_id` and related fields. **Never paste real tickets or passwords into issue reports.**

## Current verification and risk

The repository has unit tests for account registration, one-use tickets, two-player save isolation, and framed Steam login/gateway/battle packet rewriting. This is not proof of compatibility with the actual Steam client `3.0.248.0` until real Windows gameplay is tested.

Still missing: public shared-world replication and matchmaking, reconnect persistence beyond current test cases, full server-authoritative inventory/combat validation, account email/password recovery, sophisticated abuse protections, multi-VPS shared-state coordination, and performance/load testing. The existing `switches.nxs` has not been rebuilt; instead the Windows bridge adapts its packets while using an authenticated TLS connection. Do not describe this as a finished secure public battle royale server.

### Reverting

Remove the auth overlay from the Compose invocation and recreate the game server using your original `compose.yaml`. Remote login returns to fail-closed; existing account/save volumes should be preserved. Do not delete them.
