# Fix Docker persistent-volume PermissionError

On first deployment, Docker creates named volumes owned by root. The Creative Destruction image intentionally runs the game and account API as unprivileged UID 10001, so `logs/server.log` and `save/accounts.sqlite3` can fail with `PermissionError` / `sqlite3.OperationalError: unable to open database file`.

## Fix in this PR
Both Compose stacks include a one-shot `volume-init` service that:
- mounts the **existing** `cdr_logs` and `cdr_save` volumes without deleting their contents;
- runs the single `chown -R 10001:10001` command, with only the CHOWN capability;
- finishes before the game server and account API start;
- retains non-root, read-only runtime containers.

Existing player data and account databases are preserved. Do **not** run `docker compose down -v`.

## VPS upgrade (after merge)
```bash
cd /opt/creative-destruction-reborn
git pull --ff-only
docker compose -f compose.vps.yaml pull
docker compose -f compose.vps.yaml up -d
docker compose -f compose.vps.yaml ps
docker compose -f compose.vps.yaml logs --tail=50
```

If port 8090 is already used, add `CDR_ACCOUNT_HOST_PORT=8091` to `.env` (keep container port 8090). If port 8088 is used, add `CDR_STAFF_HOST_PORT=8089`. Staff and account APIs still bind to VPS loopback only.

If you have made local edits to `compose.vps.yaml`, save a copy or move your host port customizations into `.env` before pulling.

To inspect service ownership:
```bash
docker compose -f compose.vps.yaml run --rm --no-deps volume-init
docker compose -f compose.vps.yaml up -d
```

The server still **does not allow remote multiplayer login**, and its staff API is read-only. This fixes startup permissions only.
