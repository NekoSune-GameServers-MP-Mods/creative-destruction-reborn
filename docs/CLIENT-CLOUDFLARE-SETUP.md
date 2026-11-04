# Creative Destruction Reborn — Windows client setup (Cloudflare domains)

This is the **`client` branch**, separate from the `server`, `account`, `staff` and `cluster-*` backend branches.

## What you download

Go to [Client GitHub Actions](../../actions/workflows/client-build.yml) and open the newest **successful** `Build Windows Reborn Client Package` run on branch `client`. Download the `Creative-Destruction-Reborn-Windows-Client` artifact and extract its inner ZIP into **your existing, legitimately installed** Creative Destruction game directory, next to `client.exe` and `script.npk`. It contains only the Reborn client mod, a local launcher/bridge, and the public config; it contains no original game binaries, credentials or TLS private keys.

If Reborn is not installed, first run the existing installer to install `Documents/nonpatch_user_data.dat` and `Documents/script/switches.nxs` (it makes backups). Do not replace your original game binaries with files from strangers.

## Cloudflare domain configuration

The client package contains `reborn/client-config.json`:

```json
{
  "game_host": "game.cdr.nekosunevr.co.uk",
  "game_tls_hostname": "game.cdr.nekosunevr.co.uk",
  "auth_url": "https://auth.cdr.nekosunevr.co.uk"
}
```

These are **proposed/locally configured addresses**, not a proof DNS/TLS services are working.

- `auth.cdr.nekosunevr.co.uk`: public HTTPS Cloudflare Tunnel address to the account API, which must be running on the VPS and reachable through its private Docker network.
- `game.cdr.nekosunevr.co.uk`: a **DNS-only** Cloudflare A record to the VPS IP; do not enable orange-cloud HTTP proxy. The VPS must publish TCP 4000 (login), 4001 (gateway), 4002 (battle) with certificate-verified TLS. Port 8000 serves game discovery via HTTP and is requested by the local bridge.
- The game server **must** have a publicly trusted TLS certificate with SAN for `game.cdr.nekosunevr.co.uk`; a Cloudflare Origin CA certificate is generally **not trusted** by the Python client. DNS records alone don't configure the VPS certificate.
- Standard Cloudflare Tunnel public hostname routing is HTTP-oriented and **does not transparently handle these raw game TCP ports for an unmodified Steam client**. This client bridge sends game traffic directly to the DNS-only game hostname.
- Each player needs a separate registered Reborn account. The account administrator can issue single-use invitations, then players register with `reborn/tools/steam_register.py`. Never share the administrator registration key.

## One-click steps on Windows

1. Ensure Python 3 is installed and on PATH (`py -3` or `python`).
2. Close your old offline game server, if running. The new bridge must own localhost TCP 4000, 4001, 4002 and HTTP 8000.
3. **Double-click `Play Private Server.bat`** in the game directory.
4. Enter your registered Reborn username and password at the prompts.
5. The launcher securely logs into `https://auth.cdr.nekosunevr.co.uk`, automatically patches the game discovery endpoint to `127.0.0.1:8000` (with a backup), starts the local secure bridge, then launches `client.exe`.
6. Choose your game server and Play. The bridge silently obtains a fresh single-use ticket and verifies the game's remote TLS certificate. Closing the game stops the launcher/bridge.

No typing of `--game-server`, `--game-tls-hostname` or `--auth-url` is needed for ordinary play.

## Troubleshooting

- **Cannot log into account**: verify the Cloudflare Tunnel HTTPS route and `account-api` Docker container. New accounts must be registered first.
- **Game hostname cannot connect**: check grey-cloud A record, VPS TCP 4000/4001/4002 firewall, game server certificate SAN and `CDR_MULTIUSER_ENABLED=1` in the authenticated VPS Compose overlay.
- **Local port already in use**: close the previous local Python offline game server, other proxies or stale Reborn launcher. Do not kill unrelated Python apps.
- **Server discovery fails**: ensure the client's `Documents/nonpatch_user_data.dat` was installed. The launcher patches it to localhost. VPS HTTP 8000 must be reachable.
- **The game reports failed login**: inspect the VPS `game-server` logs for `S_LOGIN_AUTH err_code`; never send real one-use tickets or account passwords in screenshots.
- **Account API and game server containers are on different SQLite volumes**: login tickets cannot be validated. Both must share the same persistent account database.
- **Existing game mod compilation**: the included `switches.nxs` is the existing mod. No modified compiled mod is needed for the **bridge path**; the bridge injects verified tickets at the network layer.

**Current scope:** Remote authenticated login and independently saved characters are implemented and covered by protocol tests. The actual Steam 3.0.248.0 game still requires hands-on verification, and cross-player gameplay in a shared world is **not yet implemented**.
