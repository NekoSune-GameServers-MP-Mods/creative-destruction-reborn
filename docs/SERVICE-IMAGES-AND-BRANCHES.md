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

## Selective branch builds (updated)

The workflow `.github/workflows/docker-publish.yml` is installed on all five service branches, not just `main`. A **push to a dedicated service branch** automatically builds and publishes **only that branch's image**, without waiting for a PR to be merged:

| Push branch | Only GHCR image published | Image tag |
| --- | --- | --- |
| `server` | `game-server` | `branch-server` |
| `account` | `account-api` | `branch-account` |
| `staff` | `staff` | `branch-staff` |
| `cluster-api` | `cluster-api` | `branch-cluster-api` |
| `cluster-agent` | `cluster-agent` | `branch-cluster-agent` |

For example, an update pushed to `account` produces:
```text
ghcr.io/nekosune-gameservers-mp-mods/creative-destruction-reborn/account-api:branch-account
```

Pull requests **build without publishing**. A PR against `main`, or a push to `main`, selects only images actually affected by its changed runtime files, compose files or shared Dockerfiles. Shared build definitions can trigger a rebuild of all images, because they affect every target. An unrelated documentation change triggers no image build. `latest` is **reserved for `main`**, and a branch push never overwrites it.

Selectively test a branch image on the VPS by setting its image override in your existing local `.env`, e.g.
```dotenv
CDR_ACCOUNT_API_IMAGE=ghcr.io/nekosune-gameservers-mp-mods/creative-destruction-reborn/account-api:branch-account
```
Then update only that service with your actual Compose filename:
```bash
cd /opt/stacks/creative-destruction
docker compose -f compose.yaml pull account-api
docker compose -f compose.yaml up -d --no-deps account-api
```

This does **not** deploy by itself; publishing GHCR images and updating live VPS containers are separate operations. Use `workflow_dispatch` with `service` to manually build one selected service or `all` to rebuild all. On first deployment, make sure images and access permissions allow the VPS to pull from GHCR. Named volumes remain unchanged; do not run `down -v`.

The `server`, `account`, `staff`, `cluster-api` and `cluster-agent` branches can diverge; changes should still be integrated and tested together before labelling a version public multiplayer-ready.
