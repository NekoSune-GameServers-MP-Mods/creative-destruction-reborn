# Guarded remote single-player Steam test (NOT multiplayer)

## Why Steam login currently fails

The Steam client version `3.0.248.0` successfully reaches the VPS and sends `C_LOGIN_AUTH` with `sdkuid=offline_player` and `sauth_json={}`. The historical simulation rejected it because it uses a **single shared** `SAVE`, `GATE`, and `FIGHT_STATE`.

This branch adds a deliberately limited **single-player remote test** admission path. **It does NOT establish user identity**: the original client sends no secure credentials. Therefore this is suitable only for a private controlled trial where *one source IP is explicitly allowed* and all other traffic is blocked by the VPS provider firewall.

## Safety and scope

- Disabled by default. Explicit opt-in requires `CDR_REMOTE_SINGLE_PLAYER_TEST=1` **and** `CDR_REMOTE_TEST_IP` matching the gaming PC's public IPv4.
- Checks the observed `3.0.248.0` Steam test version, `offline_player` SDK identity, and empty `sauth_json`.
- Only one login/gateway/battle game session may be active. No simultaneous separate player identities, shared account logins, public matchmaking or cross-VPS match handoffs.
- Random one-time `auth_sn` exchanged at `C_LOGIN_CREATE` / `C_LOGIN_ENTER`, and random match ticket validated at `C_FIGHT_LOGIN` / `C_FIGHT_REQ_LOGIN`. Tickets expire after 60 seconds; gateway state is cleaned up on disconnect.
- Before stage validation, no gameplay or debug messages can reach the legacy state-mutating handlers. Logs redact ticket fields.
- The client wire stream is **unencrypted** and the first login has no proof of identity. An attacker with the allowlisted network source may impersonate the test player. Never expose the server to arbitrary public users.

## How to test using your EXISTING compose.yaml

Ensure PR is merged and the main GHCR `game-server:latest` image has finished publishing. Back up `.env`, `compose.yaml` and your Docker volume first. Keep `compose.yaml` in the same folder and do not use `docker compose down -v`.

Set **only the single PC public IPv4**, not your VPS IP, in the VPS's local `.env`:

```dotenv
CDR_REMOTE_TEST_IP=YOUR_PC_PUBLIC_IPV4
CDR_REMOTE_TEST_CLIENT_VERSION=3.0.248.0
```

The `compose.remote-lab.yaml` overlay opts in for the `game-server` service without changing the regular Compose stack, including your existing account/staff port mappings.

```bash
cd /opt/stacks/creative-destruction
docker compose -f compose.yaml -f compose.remote-lab.yaml config --quiet
docker compose -f compose.yaml -f compose.remote-lab.yaml pull game-server
docker compose -f compose.yaml -f compose.remote-lab.yaml up -d game-server
docker compose -f compose.yaml -f compose.remote-lab.yaml logs -f --tail=80 game-server
```

**If your current compose.yaml uses a different game service name**, update `compose.remote-lab.yaml` to match that service. Check `docker compose -f compose.yaml config --services` first.

Most importantly, **restrict ingress at the VPS provider's firewall to YOUR_PC_PUBLIC_IPV4/32** for TCP 4000,4001,4002 and optionally 8000. On Docker, normal UFW rules may not protect forwarded published ports. Do not keep a globally reachable game service during this test.

To inspect detailed logs:
```bash
docker compose -f compose.yaml exec -T game-server tail -n 80 -f /app/reborn/server/logs/server.log
```

A successful `C_LOGIN_AUTH` response means only that the *login stage* passed. It does not prove gateway/client compatibility, lobby loading, or gameplay. For each failure capture: the last **redacted** `[login]`, `[gate]`, `[battle]` lines and the in-game error (without publishing any generated `auth_sn`, match `login_key`, server secrets, or player IP if you want it private).

## Turning off test mode

Recreate game-server with the **normal Compose only** (without the overlay):
```bash
docker compose -f compose.yaml up -d --force-recreate game-server
```
The game-server reverts to fail-closed remote login.

## What still requires implementation

Real independent account authentication with secure transport, eliminating all global player/match state, per-user persistence, full client version compatibility, central multi-VPS matchmaking, and authoritative anti-cheat. This patch is not production multiplayer.
