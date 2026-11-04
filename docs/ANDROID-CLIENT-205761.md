# Android Creative Destruction 2.0.5761 discovery investigation

A user-provided, original NetEase-signed Android APK `com.titan.cd.gb` version `2.0.5761` was inspected.

## Source-confirmed behavior

The APK has an encrypted `assets/patch_config.json` using the same AES-256-CFB8 format as the existing Reborn Windows patcher. The decrypted JSON lists:
- `loginlist: loginlist_rel_na.txt`
- `zonelist: client_zonelist_rel_na.txt`
- `is_ignore_patch: 0`
- `npk_version: g95_patchlist_android`

The file contains **no configurable `http_url_prefix` entry**. The supplied APK contains `assets/Documents/placeholder.txt` but does **not** include the expected `script.npk` and many `res/*.npk` game asset bundles. Those are listed in `assets/obb_filelist.txt` / `assets/patch_obb_filelist.txt`, requiring separate OBB/game data not present in the APK.

## This PR

Adds aliases for `loginlist_rel_na.txt` and `client_zonelist_rel_na.txt` to the HTTP discovery server. These aliases return the same **development simulator** data as PC/Steam. It does **not** establish that Android can parse the responses.

## Android client compatibility blockers

- No confirmed mechanism to override the Android client's HTTP host from the APK alone. Merely adding `assets/Documents/nonpatch_user_data.dat` is exploratory: the game may not extract/read it. Requires runtime logcat or code inspection with the matching OBB scripts.
- The Android client version 2.0.5761 differs from Steam 3.0.248.0 and the Reborn PC protocol baseline; game wire protocol compatibility untested.
- Remote game login is deliberately disabled, since the simulator still shares mutable `SAVE`, `GATE`, `FIGHT_STATE` state and lacks encrypted authenticated handoffs.
- Modifying the APK invalidates its original NetEase signature. Test packages must be signed with independent signing keys, will not normally install as updates over the original, and may fail additional integrity verification.
- We do not redistribute game assets or signing keys in Git.

## After merging the server alias

Wait for the server image workflow to publish, then on the VPS:
```bash
docker compose -f compose.vps.yaml pull
docker compose -f compose.vps.yaml up -d
curl -i http://127.0.0.1:8000/loginlist_rel_na.txt  # replace host as required by current bind
curl -i http://127.0.0.1:8000/client_zonelist_rel_na.txt
```

For testing, limit access to a trusted environment. Never send production NetEase credentials to a replacement server or expose the incomplete simulator to public players.
