# Android Reborn 2.0.5761.0 — experimental DNS migration and Steam crossplay readiness

## Inspected APK (user-provided experimental build)

- Package asset `assets/user_data.xml` reports `2.0.5761.0` / engine `2.0.5761.299033`.
- Five classes DEX files and native libraries for both `armeabi-v7a` and `arm64-v8a` are present.
- Existing **experimental** resources `assets/nonpatch_user_data.dat` and `assets/Documents/nonpatch_user_data.dat` both contained `{"http_url_prefix":"http://75.119.148.51:8000/","language":3}`.
- This differs from the earlier investigation into another APK that did not find a configurable URL; **this specific uploaded APK does have two override files**.
- The encrypted `assets/patch_config.json` and any other game data were **not changed**.
- The supplied APK contained `META-INF/CDRTEST.RSA` (experimental test-signing evidence), which is invalidated by repackaging.

## What has been implemented

`reborn/tools/patch_android_apk.py` updates BOTH existing Reborn URL assets to:

`http://game-cdr.nekosunevr.co.uk:8000/`

It preserves the existing `language` key and unmodified game files. It intentionally removes old signature artifacts because editing any APK invalidates them. The result must be signed again using the developer's own Android signing configuration (prefer `apksigner` with modern v2/v3 signing) and installed/tested on a phone. A test-signed APK is not a verified Android release. Keep the original APK for rollback.

**IMPORTANT:** Game discovery is only plaintext HTTP metadata. It is NOT the account API. Do not change it to `https://auth-cdr.nekosunevr.co.uk`; the game won't understand that as its login-list endpoint.

## Steam vs Android status

| Subsystem | Steam 3.0.248.0 | Android 2.0.5761.0 | Crossplay status |
|---|---|---|---|
| Login-list discovery | `loginlist_rel_steam_na.txt` | `loginlist_rel_na.txt` per earlier decrypted configuration investigation | Both URLs are available in the Reborn server, parsing on Android unverified |
| Account authentication | Windows Python bridge injects one-use `game_ticket` | No demonstrated injection into Android's `C_LOGIN_AUTH` | **Blocked** |
| Game TCP transport | Windows bridge wraps raw 4000/4001/4002 with verified TLS | Existing Android game TCP transport is unknown; no Android TLS bridge | **Blocked** |
| Protocol schema | PC protocol table for Steam version | Not extracted/validated against Android version | **Blocked** |
| Real shared matchmaking | Isolated per-player match `solo-<aid>` | Same missing shared-world backend | **Not implemented** |
| Combat and actor replication | No authoritative cross-player replication | No compatible client state sync established | **Not implemented** |
| Game assets / OBB | PC assets | APK alone doesn't provide Android OBB/full runtime game data | **Unverified** |

Both players cannot see or fight each other merely because their APK and Windows client use the same game hostname. The new authenticated PC server will refuse a mobile client that cannot supply a verified game ticket and proper TLS. Do **not** bypass the verification to make a game screen turn green.

## Work required for actual crossplay

1. **Run Android and capture safe protocol metadata**: Android logcat during discovery/login, actual client version and login command IDs/field schemas; redact account identifiers/tokens.
2. **Implement Android authenticated transport**: a separate Android launcher/service or verified native game hook must obtain per-player one-use Reborn tickets via HTTPS and transport game TCP over authenticated TLS. The Android APK currently has no demonstrated mechanism for this.
3. **Compare packet definitions**: encode/decode Android login/gateway/battle packets alongside the Steam 3.0.248.0 NeoX schema; build translation for incompatible fields (not speculative equivalences).
4. **Introduce shared server match and per-player actors**: server room instances, authoritative movement/combat/inventory, team matchmaking, spawn/despawn replication, spectator policies, and disconnect/reconnect handling. The existing `solo-<account>` routing is not crossplay matchmaking.
5. **Test two real devices**: simultaneous Steam+Android login; character persistence, same world/room, both-direction motion, damage and match result; repeat under packet loss/network handoff.
6. **Security and distribution**: don't use legacy shared offline account credentials, don't ship backend signing keys or copyrighted OBBs, and sign Android builds with your own protected release key using compatible APK Signature Scheme versions.

## Example patch command (source-controlled)

```bash
python reborn/tools/patch_android_apk.py \
  ./CreativeDestruction-Android-Reborn-EXPERIMENTAL.apk \
  ./CreativeDestruction-Android-Reborn-game-cdr-UNSIGNED.apk \
  --game-host game-cdr.nekosunevr.co.uk
```

**Do not distribute an unsigned or incorrectly signed APK as production-ready.**

The Windows launcher code remains maintained on the `client` branch; backend account and game server code remain on `account` and `server`. The `android` branch is Android-specific and should remain independent until protocol compatibility is established.
