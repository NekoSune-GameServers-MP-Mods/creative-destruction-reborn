# Actual Creative Destruction multiplayer — implementation progress

## Goal

Allow **multiple independent players** to register, log into a shared central account system, choose a VPS region, join a room and play together. This is NOT the previous single-IP lab workaround. **No public multiplayer is enabled by this PR**: the legacy game protocol still has to be adapted safely.

## Implemented in this PR

### Persistent identities and profiles

- `player_profiles.py`: SQLite store keyed by an independently **verified** `account_id`, separate from old global `SAVE` and shared `player.json`.
- Profiles use optimistic version checking so two overlapping writes cannot silently overwrite each other.
- Validation limits currency fields, role names and unexpected keys. Currency changes must remain server-authoritative; NEVER pass arbitrary game-client JSON through the profile `save` method.
- Uses existing `AccountStore` for player registration/password validation and session resolution; does not treat `sdkuid=offline_player` or `sauth_json={}` as identity.

### Independent sessions and rooms

- `multiplayer_sessions.py`: internally authorises a verified account token, creates distinct account-scoped sessions, prevents duplicate active sessions and tracks lifecycle/disconnect.
- Each login issues a short-lived single-use gateway ticket; the battle stage requires a separate short-lived single-use ticket. Stage and session binding use the existing `TicketRegistry`.
- Rooms have isolated membership and match-state containers; no unverified client-provided UID may choose another account's profile.
- Tests simulate **two distinct registered users**, simultaneous room membership, cross-session ticket replay rejection, duplicate logins, room cleanup, profile version conflicts and malformed data.

### Explicit limitations

These modules are **not connected to `offline_server.py`**, because the historical game script is roughly 80 kB with many handlers directly using module-global `SAVE`, `GATE`, `FIGHT_STATE`, `PLAYER_UNIT_ID`, bots and match callbacks. Changing just login authentication would turn the existing shared-save simulator into an account-takeover risk.

The Steam `3.0.248.0` client currently sends:
```text
C_LOGIN_AUTH sauth_json={} sdkuid=offline_player
```
Its current modified SDK therefore supplies **no secure per-user credentials**. Before opening the server publicly, the Windows client / login transport must provide independent account authentication via a secure channel. The legacy game TCP transport has `need_encrypt=0`, so do **not** put account passwords, session bearer tokens or long-lived credentials into its `sauth_json` field in cleartext. A compatible, authenticated transport/client bridge must be designed and tested first.

### Next PRs required for actual playable multi-user servers

1. **Secure client auth bridge:** verified player login over TLS plus short-lived handoff bound to the game's session. Verify Steam mod build/rebuild pipeline, client version and compatibility, no leaked tokens, no user-supplied UID trust.
2. **Refactor game handler state:** replace ALL global SAVE, GATE, FIGHT_STATE, player unit, bot task and match state with per-account/per-room state; include per-message permission checks.
3. **Gateway/battle wire integration:** consume one-time gateway/battle tickets in real Steam protocol handlers and verify the matching account, game host and room.
4. **Real gameplay replication:** authoritative positions, damage, items, inventory, combat and match results; multiple clients must see each other with server-controlled events.
5. **Central multi-VPS coordination:** central account database and session validation, region routing, game-node assignment/reconnect and match allocation; SQLite can't be written concurrently by independent remote hosts. Use a transactional central database and authenticated API.
6. **Public security:** TLS/authentication, rate limits, anti-cheat, staff permissions and abuse protection, load tests and monitoring.

## Safety and deployment

- **Do not enable remote logins on the old server**. Current `offline_server.py` continues to reject unverified remote connections.
- This PR has no new public listener or Docker port.
- `compose.yaml` (user's VPS file) is unaffected by this foundation; merging it won't suddenly make Steam login work.
- PR #6's single-player IP-exception branch was closed without merge because it does not meet the user's desired architecture.
