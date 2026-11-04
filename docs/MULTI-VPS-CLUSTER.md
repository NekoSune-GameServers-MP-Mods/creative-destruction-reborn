# Creative Destruction Reborn — one central API, multiple VPS nodes

**Development/control-plane foundation only.** This is **not** working remote multiplayer. The game client cannot yet authenticate through the central API and the legacy simulator still refuses remote gameplay.

## Architecture

```text
             Private/HTTPS control API (central VPS)
                  cluster-api :8092
                      |
          SQLite registry + per-node secrets
                      |
          +-----------+-----------+
          |                       |
        VPS EU                  VPS US
     game-server             game-server
     cluster-agent           cluster-agent
     own local save          own local save
          \                       /
           ------ 30s heartbeat --
```

On the central VPS, `compose.cluster-control.yaml` hosts the **only** account API and the cluster registry. Accounts and the node registry use different SQLite files but the same persistent `cdr_save` volume. There is **no shared game state yet**. Other VPS machines use `compose.cluster-node.yaml`: game-server + cluster-agent, *not* a second account API.

The central controller uses SQLite as a single authoritative source **on one VPS only**. Do **not** copy that database between multiple running controllers or mount it over an unreliable network filesystem. Future production HA needs a proper transactional database, replicated state and controlled failover.

## 1. Central VPS

Copy `.env.vps.example` to `.env`, then generate **three different** secrets for `CDR_REGISTRATION_KEY`, `CDR_CLUSTER_ADMIN_TOKEN` and any staff token:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set, without publishing:
```dotenv
CDR_REGISTRATION_KEY=YOUR_INDEPENDENT_REGISTRATION_SECRET
CDR_CLUSTER_ADMIN_TOKEN=YOUR_INDEPENDENT_CLUSTER_ADMIN_SECRET
CDR_ACCOUNT_HOST_PORT=8091
CDR_CLUSTER_HOST_PORT=8092
```

Start the central services **on only one VPS**:
```bash
docker compose -f compose.cluster-control.yaml pull
docker compose -f compose.cluster-control.yaml up -d
docker compose -f compose.cluster-control.yaml ps
```

Both APIs bind **localhost on the VPS**, not its public IP:
- Account API: `http://127.0.0.1:8091` (internal container port 8090)
- Cluster operator API: `http://127.0.0.1:8092` (internal container port 8092)

For remote nodes, place the **cluster API only** behind a TLS-terminating reverse proxy with strict access restriction (VPN/allowlist, certificate verification, preferably mTLS), pointing to `127.0.0.1:8092`. Use `https://cluster.example.com` in the node agent. The agent deliberately refuses cleartext HTTP to remote hosts, even RFC1918/VPN addresses. Do **not** expose the account API or controller API directly on the public IP.

## 2. Register each VPS

Use the operator API locally on the **central VPS**. Replace placeholders and substitute different IDs/IPs per node. Keep the returned `node_key` secret: the server stores only its hash and does not print it again.

```bash
curl --fail-with-body -sS http://127.0.0.1:8092/v1/cluster/nodes \
  -H "Authorization: Bearer $CDR_CLUSTER_ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"node_id":"eu-one","region":"EU","advertised_ip":"100.88.10.11"}'
```

Do not paste tokens into your shell history or Git. For example, load your secret in an interactive shell with `read -rs CDR_CLUSTER_ADMIN_TOKEN` and then `export CDR_CLUSTER_ADMIN_TOKEN`; avoid placing tokens on command lines. If a key is leaked, remove/re-register that node to rotate the credential.

To list nodes:
```bash
curl --fail-with-body -sS http://127.0.0.1:8092/v1/cluster/nodes \
  -H "Authorization: Bearer $CDR_CLUSTER_ADMIN_TOKEN"
```

To remove/disable a node:
```bash
curl --fail-with-body -sS -X POST http://127.0.0.1:8092/v1/cluster/remove \
  -H "Authorization: Bearer $CDR_CLUSTER_ADMIN_TOKEN" \
  -H 'Content-Type: application/json' -d '{"node_id":"eu-one"}'
```

## 3. Each game-node VPS

Configure **different** `CDR_NODE_ID`, `CDR_NODE_KEY` and `CDR_NODE_BIND_IP` per VPS in that node's local `.env`:

```dotenv
CDR_NODE_ID=eu-one
CDR_NODE_KEY=THE_NODE_KEY_RETURNED_BY_CENTRAL_REGISTRATION
CDR_NODE_BIND_IP=100.88.10.11
CDR_CLUSTER_URL=https://cluster.example.com
CDR_LANGUAGE=en
```

The bind IP must exist on that VPS. Prefer a private network IP for game development; these game ports remain insecure until the authentication and state-isolation work is complete.

```bash
docker compose -f compose.cluster-node.yaml pull
docker compose -f compose.cluster-node.yaml up -d
docker compose -f compose.cluster-node.yaml logs -f --tail=40 cluster-agent
```

The agent tests TCP connectivity to `game-server:4000` on its own Docker network, then sends a heartbeat every 30 seconds. Entries become `unavailable` if the heartbeat is older than 90 seconds or the local TCP test fails.

**A reachable node does not imply a playable node.** Do not automatically advertise it to clients until server login/rooms are fully authenticated and implemented.

## API overview

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/v1/cluster/nodes` | central admin bearer | Register a node; returns secret once |
| GET | `/v1/cluster/nodes` | central admin bearer | List registered VPS, region, IP, health |
| POST | `/v1/cluster/heartbeat` | `X-CDR-Node-Key` | Update only this node's reachability |
| POST | `/v1/cluster/remove` | central admin bearer | Revoke/remove a node |

No public unauthenticated endpoints and no remote account API access. The node agent does not require the registration key, staff token or player passwords.

## Still needed before real shared multiplayer

- Wire client authentication to the one central account service through a secure transport.
- Isolate `SAVE`, `GATE`, `FIGHT_STATE` into player and room instances; persist profiles centrally.
- Add secure server-to-server session/ticket validation at login, gateway and battle.
- Support cross-node match routing, reconnect/recovery and player transfers without sharing plaintext account credentials.
- Validate the exact Steam client version and server status probe, plus implement rate limiting and stronger fleet management.

Avoid running `compose.vps.yaml` on every node if you want centralized accounts: it starts an independent local account API per machine.
