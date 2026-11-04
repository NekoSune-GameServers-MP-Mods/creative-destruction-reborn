# Reborn GUI Launcher for Windows

The graphical launcher is built **only from the client branch**. Open the latest successful [Windows client Actions build](../../actions/workflows/client-build.yml), download the `Creative-Destruction-Reborn-Windows-Client` artifact, extract the ZIP, and copy **everything** into the original Creative Destruction folder beside `client.exe` and `script.npk`.

Double-click **`RebornLauncher.exe`** (or `Play Private Server.bat`; it opens the GUI when available). No Python installation or command-line arguments are required. Keep the included `_internal` directory beside the EXE, as it contains the Python runtime and NeoX protocol tables.

## GUI functions

- **Play** — Reborn username/password, secure account authentication, patch local discovery, launch localhost TLS bridge and start `client.exe`. The game runs while the GUI remains responsive. The password is not saved in configuration.
- **Create Account** — independent username/password signup using an administrator-issued **one-use invite code**. Existing accounts need not register again. Operators can create their own first account directly inside their account-api container; there is deliberately no public administrator-secret field.
- **Settings & Diagnostics** — edit public game DNS hostname, game TLS hostname, HTTPS account URL; save them in `reborn/client-config.json` (no credentials). Test account endpoint and TLS 4000 separately.
- **Error messages** — show HTTP status, known API error codes, and Cloudflare Ray ID without exposing credentials or bearer tokens.

Defaults:

```json
{
  "game_host": "game-cdr.nekosunevr.co.uk",
  "game_tls_hostname": "game-cdr.nekosunevr.co.uk",
  "auth_url": "https://auth-cdr.nekosunevr.co.uk"
}
```

## If account login still returns HTTP 403

**A GUI does not bypass Cloudflare Access/WAF rules.** If fake logins return the expected 401 JSON, but your actual account login returns 403 `text/plain`, the GUI will continue to fail until the service rejecting that request is diagnosed. On the Settings tab, press **Test Connections** to verify both endpoints. Find the reported `CF-Ray` in Cloudflare Security Events and inspect the precise rule/action for the `/v1/login` request, without posting your password. Also check whether the account is created in the shared persistent database and whether the request reached the API container.

## Implementation constraints

The launcher only connects to **your configured Reborn community game**, not official NetEase services. It does not include copyrighted game binaries. Game ports 4000–4002 require a publicly trusted TLS certificate on the VPS; Cloudflare DNS-only records do not configure that. Shared-world player replication and live Steam game behaviour still require additional work and real-client testing.

## Windows source fallback

If the EXE is unavailable, install Python 3.9+ and execute `python reborn/tools/steam_gui.py` from the game directory. This is optional and is not required by the packaged GUI.
