# Android (experimental)

**Target:** Creative Destruction Android, version `2.0.5761.0`.

- Server discovery: `http://game-cdr.nekosunevr.co.uk:8000/`
- Reproducible patcher: [reborn/tools/patch_android_apk.py](../../reborn/tools/patch_android_apk.py)
- Compatibility investigation: [docs/ANDROID-CROSSPLAY-STATUS.md](../../docs/ANDROID-CROSSPLAY-STATUS.md)
- Windows Steam uses the separate `client` branch.

## Updated APK

Locally generated test-signed file:

`CreativeDestruction-Android-Reborn-EXPERIMENTAL-v2.0.5761-game-cdr-test-signed.apk`

SHA-256: `5ec31f7237b712528ef21f125e81b6337ac75c748e36977f4eb59087562e7b85`

Size: `81,514,162` bytes.

**The APK binary is not in this branch unless it is explicitly uploaded and a GitHub file/release URL is confirmed.** Its signature is experimental and has not been verified on a real Android device. This is not a production release.

To upload an APK that you **own or have permission to redistribute** from your Windows PC via Git CLI:

```powershell
git clone --branch mobileapps https://github.com/NekoSune-GameServers-MP-Mods/creative-destruction-reborn.git
cd creative-destruction-reborn
Copy-Item "C:\path\to\your\updated.apk" "mobileapps\android\CreativeDestruction-Android-Reborn-EXPERIMENTAL-v2.0.5761-game-cdr-test-signed.apk"
git add mobileapps/android/*.apk
git commit -m "build(mobileapps): upload permitted experimental Android test APK"
git push origin mobileapps
```

GitHub supports Git objects below its 100 MiB hard limit, but warns above 50 MiB. For long-term app binaries, prefer release assets or Git LFS. Do not upload private signing keys. Public repository files are publicly downloadable.

**Crossplay status:** the Android login ticket/TLS transport, Android protocol compatibility, and real cross-platform shared game replication are unimplemented; new DNS alone does not enable gameplay.
