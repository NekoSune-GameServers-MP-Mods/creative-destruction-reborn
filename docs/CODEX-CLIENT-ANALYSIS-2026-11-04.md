# Codex installed-client investigation — 2026-11-04

Source: user-provided `NETWORK-PROTOCOL.zip` (23 report/data files, static investigation). The complete 29 MB endpoints JSON and original installation data are **not** committed.

## Confirmed investigation scope
- 87 installed files, ~4.33 GB inspected at raw-byte level.
- 169 unique URL literal **candidates** / 44,702 occurrences. These include embedded certificates/metadata and **are not 169 confirmed server APIs**.
- 1,532 Reborn message definitions in protocol matrix; these are not independently proven equivalent to stock game traffic.
- Reborn TCP listeners: 8000 discovery HTTP, 4000 login, 4001 gateway, 4002 battle, 8088 staff UI.
- Original game's KCP/UDP transport and original remote client handshakes **remain unknown**.

## High-priority results
1. **Critical** shared global `SAVE`, `GATE`, `FIGHT_STATE`, and synthetic auth allow cross-player interference. No public servers.
2. **High** unauthenticated `C_LOGIN_WIZ_CMD` dispatch covers simulator/debug controls; requires per-session capability checks.
3. **High** cleartext network protocol and static ticket strings; development must use isolated VPN until authenticated transports are implemented.
4. **High** nested decoder previously trusted child lengths. Bounded decoding and malformed tests are added to this PR.
5. **Medium** installer may implicitly `pip install pycryptodome`; replace with explicit dependency instructions/pinned lockfile.
6. **Medium** staff dashboard is a shared-token, read-only prototype; does not implement secure per-staff identities, MFA, RBAC or moderation.
7. Provenance of bundled `switches.nxs` and DXVK `d3d9.dll` is not established. **No malware-free or RCE-free certification**.
8. Original game installation lacks the Reborn `Documents/nonpatch_user_data.dat` and `reborn/` directory; patcher requires mod installation. Original encrypted patch configuration was not decoded.

## Implementation priorities
- **P0 security:** secure client authentication/handoffs, isolate accounts & matches, authorized debug access, per-message limits, bounded parsing, fuzz/negative tests.
- **P1 deployment/patcher:** establish original game build hash and reproducible compiled mod, validate config formats, add rollback manifests & profile switching, verify remote handoffs using a test VPN, enforce compose validation.
- **P2 gameplay:** independently synchronized game rooms, matchmaking, authoritative movement/combat/inventory, reconnect and match completion.
- **P3 staff:** separate owner/admin/moderator/support accounts, MFA/RBAC, validated moderation API and audit trail.
- **P4 operations:** complete locale catalogs, signed updates, backups, metrics, rollback tests.

## Explicit uncertainty
The Codex analysis was **static only**. It did not decode original NPK scripts or run the stock game against the server; no complete original API map, verified login flow, live matchmaking, or malware scan is demonstrated. The source PR snapshot scanned was `01a1291f384ea7d2998d293d6dbd82dd664236c1`; later commits must be retested.

Keep this PR in draft until game-client integration and multi-user isolation testing are reproducible.
