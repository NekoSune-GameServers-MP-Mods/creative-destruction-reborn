# Steam server-list visibility and remote login — current status

## What is confirmed from the Steam PC client

The captured client (version 3.0.248.0) uses HTTP discovery:
- `GET /loginlist_rel_steam_na.txt`
- `GET /client_zonelist_rel_steam_na.txt`

The HTTP discovery endpoints are implemented on `main`. They return the TCP login address and a zone entry. This branch renames the zone display label from `Offline` to `Reborn-Dev` to avoid implying that the server health was measured. **The red marker and 999 ms are client-side status results, not proven network outages**; discovery HTTP by itself cannot establish the legacy client status probe.

## What this branch implements

- A concurrency-safe, expiring, one-use `TicketRegistry`, phase-bound to either gateway or battle, and bound to an already-verified session ID. Invalid, expired, wrong-session, wrong-stage, and replayed tickets are rejected. A full registry refuses more tickets rather than evicting valid clients.
- Tests for expiration, replay, concurrency, phase separation, session binding and revocation.
- A remote login command guard preventing `C_LOGIN_CREATE` or other handlers from being dispatched on an unauthenticated login socket after the legacy `C_LOGIN_AUTH` rejection.

## Why multiplayer is NOT enabled by this branch

The `TicketRegistry` is a **foundation**, not wired to the client protocol or the AccountStore yet. Issuing a random ticket without verifying a user would not authenticate anyone. Game actions still reference shared `SAVE`, `GATE` and `FIGHT_STATE` global dictionaries. Also, the legacy TCP client uses unencrypted traffic (`need_encrypt=0`). Simply removing the remote-login block would allow unsafe shared player state and spoofed game actions.

Before enabling remote gameplay, remaining work includes:

1. Implement client-compatible credential proof in `C_LOGIN_AUTH.sauth_json`, **without sending passwords or bearer tokens across unencrypted public TCP**. Verify the Steam client's JSON field and client build first. A protected client-to-server transport is required.
2. Link verified accounts to a persistent player profile per account, and refactor every game handler to use `conn.player` / `conn.session` instead of shared globals.
3. Issue the gateway ticket only after authentication and consume it at the gateway after verifying the wire handoff. Repeat for battle login with stage-specific tickets.
4. Isolate lobby/game rooms, validate all client mutations server-side, and add tests for two simultaneously connected users, reconnects, ticket replay, and malicious cross-account requests.
5. Capture the Steam client's server-status request / response to determine the red icon/999ms protocol rather than claiming a port opening fixes it.

Do **not** expose remote game services as a public multiplayer server yet. Follow `docs/ROADMAP-MULTIPLAYER.md`.

## Deploying after merge

The existing GitHub Actions workflow rebuilds the published image when `reborn/server/**` changes. After the publish job succeeds:

```sh
docker compose -f compose.vps.yaml pull
docker compose -f compose.vps.yaml up -d
docker compose -f compose.vps.yaml logs --tail=80 game-server
```

The visible entry is expected to become `Reborn-Dev`; it does **not** imply the server can accept authenticated public players.
