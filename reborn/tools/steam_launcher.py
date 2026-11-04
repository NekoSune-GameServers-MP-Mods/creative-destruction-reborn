"""One-click authenticated Creative Destruction Steam client launcher.

Reads reborn/client-config.json. Config contains only public hostnames, never
credentials. Binds Steam discovery/game ports to 127.0.0.1 through steam_bridge.
"""
import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

TOOLS = Path(__file__).resolve().parent
REBORN = TOOLS.parent
GAME = REBORN.parent
sys.path.insert(0, str(TOOLS))
from patch_server import patch  # noqa: E402
from steam_bridge import AccountLogin, run, validate_game_host  # noqa: E402


def load_config(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("Client configuration must be a JSON object")
    game_host = validate_game_host(doc.get("game_host"))
    tls_host = validate_game_host(doc.get("game_tls_hostname"))
    if game_host in ("127.0.0.1", "0.0.0.0"):
        raise ValueError("Game host must be your DNS-only Cloudflare A record")
    if tls_host != game_host:
        # Different server/certificate names are possible, but require
        # explicit advanced configuration rather than an accidental mismatch.
        raise ValueError("game_tls_hostname must match game_host")
    auth_url = doc.get("auth_url")
    if not isinstance(auth_url, str):
        raise ValueError("auth_url must be a valid HTTPS URL")
    parts = urlsplit(auth_url)
    if (parts.scheme != "https" or not parts.hostname or parts.username or
            parts.password or parts.path not in ("", "/") or parts.query or parts.fragment):
        raise ValueError("auth_url must be a plain HTTPS hostname")
    if any(key not in ("game_host", "game_tls_hostname", "auth_url") for key in doc):
        raise ValueError("Unexpected config key; do not store login secrets in client-config.json")
    return game_host, tls_host, auth_url.rstrip("/")


def launch(username, config_path):
    game = GAME / "client.exe"
    if not game.is_file() or not (GAME / "script.npk").is_file():
        raise FileNotFoundError("Copy the reborn folder into your own installed Creative Destruction game directory")
    host, tls_host, auth_url = load_config(config_path)
    print("Game: " + host)
    print("Account API: " + auth_url)
    if not username or len(username) > 24:
        raise ValueError("Enter a valid Reborn account username")
    password = getpass.getpass("Reborn account password: ")
    try:
        account = AccountLogin(auth_url, username, password)
    finally:
        del password
    # Switch ONLY the game's public discovery to local bridge. The original
    # endpoint is backed up automatically by patch_server.patch.
    patch(str(GAME), "http://127.0.0.1:8000/")
    # run() starts local bridge listeners before launching client.exe.
    run(host, account, tls_host, game_executable=game)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", help="Reborn account username")
    parser.add_argument("--config", default=str(REBORN / "client-config.json"))
    args = parser.parse_args()
    username = args.username or input("Reborn username: ").strip()
    try:
        launch(username, args.config)
    except KeyboardInterrupt:
        print("Launcher stopped.")
    except Exception as exc:
        # Do not expose credentials or login/session tokens in error messages.
        print("Unable to launch: " + type(exc).__name__ + ": " + str(exc)
              if isinstance(exc, (ValueError, FileNotFoundError, OSError))
              else "Unable to launch: " + type(exc).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
