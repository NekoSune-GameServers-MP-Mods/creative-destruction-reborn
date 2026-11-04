# Creative Destruction Reborn — server & multiplayer roadmap

> Status: **NOT production ready.** This fork is independent from NetEase. This PR does not provide public multiplayer.

## What this PR delivers
- Configurable operator language (English, French, German, Spanish, Portuguese).
- Safe-by-default loopback binding and explicit remote bind acknowledgement.
- TCP connection cap, malformed frame rejection and deterministic socket cleanup.
- CI compile/tests and Python dependency audit.
- Deployment guidance for isolated private/VPN development.

## P0 — Must fix before public access
1. **Per-session state isolation:** eliminate global `SAVE`, `GATE`, `FIGHT_STATE` and one shared `PLAYER_UNIT_ID`. Make each connection an authenticated session, and each match an independent room.
2. **Authentication:** issue short-lived unpredictable session tokens, bind game/gate/battle handoffs to the authenticated session, and refuse spoofed identities. Never trust client-provided currencies, position, damage or inventory.
3. **Network security:** game protocol currently advertises `need_encrypt=0`. Use an authenticated encrypted transport tunnel or robust protocol adaptation; unencrypted public TCP is unacceptable.
4. **Authoritative gameplay:** server-side hit validation, positions, inventory, loot, match results, rate limits and anti-cheat; never accept client authority.
5. **Abuse resistance:** message-specific rate limits, packet parsing fuzz tests, max player/match limits, bounded worker pools, safe log truncation, health checks and persistent user storage.
6. **Client compatibility:** reliably rebuild `switches.nxs` from reviewed source, configure remote discovery (currently loopback), and verify original game asset hashes and DXVK binary provenance.
7. **Reproducible releases:** lock dependencies, verify binaries, create signed release manifests and provide Windows/Linux build validation.

## P1 — Private multiplayer alpha
- Single VPS dedicated server with persistent players, rooms and game state.
- VPN-only access (WireGuard/Tailscale) during testing; explicit firewall allowlists.
- Configurable advertised IP, login/gateway/battle endpoints, and tested client-side endpoint overrides.
- Docker/Linux service image, health checks and persistent volume after backend refactor.
- Account creation/login (no original NetEase credentials), migration, backups and admin commands.
- Localization of **game UI** needs client asset localization/recompilation, separate from operator logs.

## P2 — Production operations
- Multi-instance region/room routing, metrics, audit logs, moderation, bans, DDoS protection.
- Compatibility and load testing, integration tests using a lawful original client copy.
- Community launcher only after malware analysis and provenance verification.

## Current warning
This architecture is single-player/local simulation. Changing the bind address alone is **not** multiplayer; two users may share state and overwrite saves. Never port-forward 4000/4001/8000 or advertise this build as public hosting.
