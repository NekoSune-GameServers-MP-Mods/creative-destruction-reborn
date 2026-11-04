# Separate, least-privilege targets for each service (development backend only).
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 cdr && mkdir -p /app/reborn/server/logs /app/reborn/server/save && chown -R cdr:cdr /app
WORKDIR /app/reborn/server
USER cdr

FROM base AS account-api
COPY --chown=cdr:cdr reborn/server/accounts.py reborn/server/account_api.py reborn/server/player_profiles.py ./
CMD ["python", "account_api.py"]

FROM base AS staff
COPY --chown=cdr:cdr reborn/server/staff_dashboard.py ./
CMD ["python", "staff_dashboard.py"]

FROM base AS cluster-api
COPY --chown=cdr:cdr reborn/server/cluster_api.py ./
CMD ["python", "cluster_api.py"]

FROM base AS cluster-agent
COPY --chown=cdr:cdr reborn/server/cluster_agent.py ./
CMD ["python", "cluster_agent.py"]

# Keep game-server last so 'docker build .' remains the local simulator.
FROM base AS game-server
# Only the live game runtime is packaged. Unrelated account/dashboard edits must
# not alter the game image digest or force its CI build.
COPY --chown=cdr:cdr reborn/server/offline_server.py reborn/server/bots.py reborn/server/loot.py reborn/server/nexproto.py reborn/server/server_config.py reborn/server/i18n.py ./
COPY --chown=cdr:cdr reborn/server/data/ ./data/
CMD ["python", "offline_server.py"]
