# Security audit / threat model

## Scope and limitations

This is an initial static/source audit, **NOT** a clean-malware certificate and not a public deployment approval.
Python server source and installer were inspected. `reborn/dxvk/d3d9.dll` and compiled `reborn/client_mod/switches.nxs` have **not** been independently reproduced or analyzed dynamically. Do not disable antivirus protection to run either file.

## Current findings

| Severity | Finding | Status |
| --- | --- | --- |
| Critical | No account/session isolation: global SAVE, GATE and FIGHT_STATE; static login tokens | OPEN — block public multiplayer |
| Critical | Unauthenticated unencrypted original game protocol (need_encrypt=0) | OPEN — use private VPN only |
| High | Client-authoritative combat/state, insufficient message-level validation | OPEN — block public multiplayer |
| High | Protocol parser dynamic exec of decompiled `*_pto.py` source | REMOVED: JSON definitions required |
| High | Untrusted compiled client mod and third-party d3d9.dll provenance | OPEN — independent hash, reproducible build & AV needed |
| Medium | Thread-per-connection resource exhaustion | PARTIAL: concurrent slots bounded; further rate limits needed |
| Medium | Malformed framing could busy-loop | FIXED: invalid lengths rejected |
| Medium | Static Python installer may install pycryptodome from package index | OPEN: pin and hash-lock for release |
| Medium | Original launcher kills all processes with offline_server.py in command line | OPEN |
| Medium | Game packet logs and saved player data may contain sensitive material | OPEN — redact, rotate, access control |
| Medium | Container exposed binding misconfiguration | MITIGATED: VPN IP binding; fail closed for non-private host IP |
| Low | No automated binary scanning / supply-chain attestations | OPEN |

## Defenses added
- Container runs non-root, read-only FS, dropped Linux capabilities, limited resources, persistent volumes.
- VPS Compose published game ports must bind a **private** IP address; operator dashboard binds host loopback only.
- Endpoint patcher edits a JSON config, not executables; validates URL and creates a reversible backup.
- Dashboard uses a high-entropy bearer token, constant-time comparison, read-only endpoints and restricted host bind.
- CI compiles sources, validates JSON, checks dependencies and builds Docker.

## Before inviting players
- Verify server trust boundaries and per-player auth, per-match state, packet-level limits and authoritative gameplay.
- Verify original game assets and client mod binary hash/provenance.
- Fuzz packet decode, isolate save writes, lock dependencies, implement intrusion monitoring and firewalls.
- Do not upload or publicly redistribute copyrighted original game archives.
