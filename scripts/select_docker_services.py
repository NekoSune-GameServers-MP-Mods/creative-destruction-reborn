"""Select only affected GHCR images for a commit range.

Use with a full Git checkout: python scripts/select_docker_services.py <base> <head>
The dedicated service branches own only their service image. Pull requests and
main use path-level dependencies; shared base/image workflow edits rebuild all.
"""
import json
import subprocess
import sys

SERVICES = ("game-server", "account-api", "staff", "cluster-api", "cluster-agent")
BRANCH_OWNER = {"server": "game-server", "account": "account-api",
                "staff": "staff", "cluster-api": "cluster-api",
                "cluster-agent": "cluster-agent"}
ALL_IMAGE_FILES = {
    "Dockerfile", ".dockerignore",
    ".github/workflows/docker-publish.yml",
    "scripts/select_docker_services.py",
}
SOURCES = {
    "game-server": ("reborn/server/offline_server.py", "reborn/server/bots.py",
                    "reborn/server/loot.py", "reborn/server/nexproto.py",
                    "reborn/server/server_config.py", "reborn/server/i18n.py",
                    "reborn/server/data/"),
    "account-api": ("reborn/server/accounts.py", "reborn/server/account_api.py",
                    "reborn/server/player_profiles.py"),
    "staff": ("reborn/server/staff_dashboard.py",),
    "cluster-api": ("reborn/server/cluster_api.py",),
    "cluster-agent": ("reborn/server/cluster_agent.py",),
}
# Game-server has an explicit COPY list, so account/staff edits do not rebuild it.
COMPOSE = {
    "compose.yaml": ("game-server",),
    "compose.vps.yaml": ("game-server", "account-api", "staff"),
    "compose.cluster-control.yaml": ("account-api", "cluster-api"),
    "compose.cluster-node.yaml": ("game-server", "cluster-agent"),
}


def selected(paths, event, branch, manual="auto"):
    if manual not in ("auto",) + SERVICES + ("all",):
        raise ValueError("Invalid requested service")
    if manual == "all":
        return list(SERVICES)
    if manual != "auto":
        return [manual]
    # Ownership beats the path-based selector only on actual branch pushes:
    # a change in server branch must never publish an account/staff image.
    if event == "push" and branch in BRANCH_OWNER:
        return [BRANCH_OWNER[branch]]
    chosen = set()
    for path in paths:
        if path in ALL_IMAGE_FILES:
            chosen.update(SERVICES)
        if path in COMPOSE:
            chosen.update(COMPOSE[path])
        for service, prefixes in SOURCES.items():
            if any(path == prefix or path.startswith(prefix) for prefix in prefixes):
                chosen.add(service)
    return [s for s in SERVICES if s in chosen]


def diff_paths(base, head):
    # No external libraries; run inside actions/checkout with fetch-depth: 0.
    data = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=ACMRT", base, head],
        text=True,
    )
    return [line.strip() for line in data.splitlines() if line.strip()]


def main(argv):
    if len(argv) != 6:
        raise SystemExit("Usage: select_docker_services.py BASE HEAD EVENT BRANCH MANUAL")
    _, base, head, event, branch, manual = argv
    result = selected(diff_paths(base, head), event, branch, manual)
    print(json.dumps({"service": result}, separators=(",", ":")))


if __name__ == "__main__":
    main(sys.argv)
