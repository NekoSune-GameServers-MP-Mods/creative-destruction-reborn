# Private VPS development deployment

**Experimental single-player simulator; NOT a functional public multiplayer service.**
The game currently shares account/match state, does not authenticate clients securely and uses an unencrypted protocol.
No public port forwarding or exposure.

## Requirements
- VPS with Docker Engine + Docker Compose v2.
- Working Tailscale or WireGuard VPN with a **private, IPv4 address** on the host.
- Linux firewall denies public access to 8000, 4000-4002, 8088.
- A legitimate local client copy matching 3.0.210.0.
- Two **independent** random secrets in `.env`: `CDR_STAFF_TOKEN` and `CDR_REGISTRATION_KEY`.

## Install
```sh
git clone https://github.com/NekoSune-GameServers-MP-Mods/creative-destruction-reborn.git
cd creative-destruction-reborn
cp .env.vps.example .env
# Edit .env and use YOUR VPN IPv4 and random staff token.
python3 scripts/validate_vps_env.py .env
docker compose -f compose.vps.yaml pull
docker compose -f compose.vps.yaml up -d
docker compose -f compose.vps.yaml ps
docker compose -f compose.vps.yaml logs --tail=80
```

**Important:** Docker-published ports may bypass some host firewalls. Binding only to the VPN IP is necessary but not a complete firewall/security control. Audit upstream provider firewall and DOCKER-USER/nftables as appropriate.

## Staff dashboard
Never expose 8088 publicly. From your desktop, use an SSH tunnel:
```sh
ssh -L 8088:127.0.0.1:8088 username@your-vps
```
Open `http://127.0.0.1:8088` on your desktop and enter your `CDR_STAFF_TOKEN`.
The first version is read-only: shows dashboard process status, last local save and recent logs. The dashboard does **not** prove the game server is running or healthy.

## Patch original game client (Windows)
Copy the repository's `reborn` directory and patcher files next to your original `client.exe`, run the existing installer, then:
```powershell
python .\reborn\tools\patch_server.py --game-dir . --server-ip 100.88.2.3
```
Replace `100.88.2.3` with your private VPN server IP. To undo:
```powershell
python .\reborn\tools\patch_server.py --game-dir . --restore
```

Only the known `Documents/nonpatch_user_data.dat` HTTP discovery URL is modified. The server advertises VPN IP in login and battle responses. **This does not establish that the stock game client can authenticate/connect remotely; full Windows testing requires a legal copy of the game and additional reverse engineering.**

## Security checklist
- Keep the project unmerged until CI passes and original client has been tested.
- Ensure your .env is private and is excluded from Git.
- Staff token must be cryptographically random, at least 32 characters. Example generator: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.
- Do not reuse NetEase credentials or real player accounts.
- Remove VPN exposure when not actively testing.
- See `SECURITY-AUDIT.md` and `ROADMAP-MULTIPLAYER.md`.

## Secure account API (private development)
The new account service is available **only** on VPS localhost port **8090**. Forward it with `ssh -L 8090:127.0.0.1:8090 username@your-vps`. See [ACCOUNTS.md](ACCOUNTS.md) for registration, login, logout, tokens and limitations.

**Important:** This backend persists independently authenticated accounts but is **not connected to the original game client yet**. Remote legacy game login is disabled until per-player/match state and authenticated handshake tickets are implemented. The loopback-only offline simulator still works as before.

## GitHub Actions Docker images
GitHub Actions publishes a multi-platform development server image to:
`ghcr.io/nekosune-gameservers-mp-mods/creative-destruction-reborn:latest`

On new commits to `main` that change server source, Dockerfile, or the workflow, GHCR receives a refreshed `latest` image. Git tags matching `v*` receive an identically named Docker image tag if the workflow's path filters match. A short Git SHA tag also identifies each published build. PR runs build without publishing; `workflow_dispatch` allows manually triggering a build.

VPS updates after the image is published:
```sh
git pull --ff-only
docker compose -f compose.vps.yaml pull
docker compose -f compose.vps.yaml up -d```
All three services use the same prebuilt image with different commands and retained storage. The container is a development simulator; remote gameplay is still deliberately blocked by default.

If GHCR reports `unauthorized` / `denied`, the organization may need to allow Actions package publishing, or the container package may require public visibility / a read-only registry login on the VPS. Do not put GitHub tokens in your compose file or Git.
