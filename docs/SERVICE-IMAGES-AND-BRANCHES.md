# Separate service images and service branches

Creative Destruction Reborn uses **one repo**, five independently published Docker images, and dedicated development branches. Its single-player simulator still does not permit remote multiplayer login; independent Docker images are an operational improvement, not a gameplay protocol implementation.

## Separate Docker images (AMD64 and ARM64)

| Service | GHCR image (main release) | Runtime |
| --- | --- | --- |
| Game server + HTTP discovery | `ghcr.io/nekosune-gameservers-mp-mods/creative-destruction-reborn/game-server:latest` | `offline_server.py` |
| Account API | `ghcr.io/nekosune-gameservers-mp-mods/creative-destruction-reborn/account-api:latest` | `account_api.py` |
| Staff dashboard | `ghcr.io/nekosune-gameservers-mp-mods/creative-destruction-reborn/staff:latest` | `staff_dashboard.py` |
| Cluster control API | `ghcr.io/nekosune-gameservers-mp-mods/creative-destruction-reborn/cluster-api:latest` | `cluster_api.py` |
| Cluster heartbeat agent | `ghcr.io/nekosune-gameservers-mp-mods/creative-destruction-reborn/cluster-agent:latest` | `cluster_agent.py` |

The shared `Dockerfile` contains **five multi-stage targets**. Account/staff/cluster images copy only the Python sources their service needs; the game-server target retains the game data files. GitHub Actions builds every target independently for `linux/amd64` and `linux/arm64`. Pull requests build without publishing. The `latest` tag is only published by `main`, whereas branch builds publish `branch-<name>` tags and SHA tags for each image.

## Branch responsibilities

| Branch | Development scope |
| --- | --- |
| `server` | Game protocol, Steam/Android discovery, game rooms, multi-node gameplay |
| `account` | Account API and authentication, central player identities |
| `staff` | Staff dashboard and future permissions/moderation |
| `cluster-api` | Central multi-VPS registry and scheduling |
| `cluster-agent` | Heartbeat agent installed on additional game VPS machines |
| `main` | Reviewed, tested, deployable integration baseline |

At branch creation they all begin from the **same shared integration snapshot**, not independent unrelated repositories. Developers should make changes on the relevant branch, open a PR into `main`, and keep the branches updated from `main` when other changes are merged. Docker packages remain separately selectable for deployment. Changing a branch does **not** automatically update the `latest` image until merged to `main`.

## Upgrading an existing VPS deployment

**Do not run `docker compose down -v`.** Before pulling new Compose files, save any local custom mappings (for example, account host port 8091 and staff host port 8089). The new Compose file defaults are configurable via `CDR_ACCOUNT_HOST_PORT` and `CDR_STAFF_HOST_PORT`. Docker *named volume* names are unchanged when the Compose project name and directory stay the same.

After PR merge and successful GitHub Actions publishing:
```bash
cd /opt/creative-destruction-reborn
git pull --ff-only
docker compose -f compose.vps.yaml config --quiet
docker compose -f compose.vps.yaml pull
docker compose -f compose.vps.yaml up -d
docker compose -f compose.vps.yaml ps
docker compose -f compose.vps.yaml logs --tail=80 game-server
```

For local development `docker build .` still produces the game-server image. Build any other service with `docker build --target account-api .` (substitute target name).

## Steam server list regression

The zone list must end in a real line terminator `\n` (one newline byte, not the literal characters backslash and n). The original release advertised a malformed terminal `\\n` after the zone details. After merging and pulling the game-server image, check:
```bash
curl -v http://YOUR_GAME_SERVER_IP:8000/client_zonelist_rel_steam_na.txt
```
This fixes **discovery formatting only**, not the red status / 999ms issue or the intentionally blocked remote login. Do not interpret TCP port availability as proof of playable login.

## Migration safety

The old monolithic image `ghcr.io/nekosune-gameservers-mp-mods/creative-destruction-reborn:latest` is **not automatically removed** by this change. New deployments reference the five service-specific image paths. Avoid launching a second Compose project on the same host ports; switch over the existing project instead.

Only private/protected development instances are appropriate until per-player state isolation and secure authenticated game handoffs are implemented.
