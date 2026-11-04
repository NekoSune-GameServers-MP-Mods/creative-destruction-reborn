# Creative Destruction Reborn — Mobile Apps

Dedicated **mobileapps** branch for the Android and prospective iOS client projects. The existing `server`, `account`, `client`, and other branches remain independent.

## Folders

- [Android](android/README.md) — Android 2.0.5761.0 experimental APK, endpoint patching, signatures, compatibility notes.
- [iOS](ios/README.md) — Placeholder for future source/build setup. No iOS IPA, source, Apple provisioning profile, or signed build has been supplied.

The Android endpoint is `http://game-cdr.nekosunevr.co.uk:8000/` for server discovery only. This **does not enable Steam/Android multiplayer or an Android authenticated account login**. Those require Android game protocol adaptation and shared battle sessions.

## APK uploads

The user-provided updated APK is approximately 81,514,162 bytes (77.7 MiB) and must be uploaded with **Git CLI/Git LFS or a suitable GitHub release uploader**, not GitHub's 25 MiB web file uploader. Only publish third-party game APKs where you have distribution rights; otherwise keep them private and publish only your original patches and source. See [Android upload instructions](android/README.md).
