# Development-only single-player simulation server, NOT production multiplayer.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY reborn/server/ /app/reborn/server/
RUN useradd --create-home --uid 10001 cdr && mkdir -p /app/reborn/server/logs /app/reborn/server/save && chown -R cdr:cdr /app
USER cdr
WORKDIR /app/reborn/server
CMD ["python", "offline_server.py"]
