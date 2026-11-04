"""Patch only the documented Creative Destruction Reborn discovery URL.

No binary modification, downloads, registry access or elevation required.
Run after install.py has installed the client mod.
"""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import shutil
import sys
from urllib.parse import urlsplit

FILE = Path("Documents/nonpatch_user_data.dat")
BACKUP = Path("reborn/backup/server_endpoint_original.dat")

def validate_url(value):
    parts = urlsplit(value)
    if parts.scheme != "http" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Expected an HTTP IPv4 discovery URL without credentials")
    try:
        ipaddress.IPv4Address(parts.hostname)
    except ValueError as exc:
        raise ValueError("Only literal IPv4 addresses are supported") from exc
    if parts.port != 8000 or parts.path not in ("", "/") or parts.query or parts.fragment:
        raise ValueError("Discovery endpoint must use port 8000 and path /")
    return "http://%s:8000/" % parts.hostname

def patch(game_dir, endpoint, restore=False):
    root = Path(game_dir).resolve()
    if not (root / "client.exe").is_file() or not (root / "script.npk").is_file():
        raise ValueError("Game directory must contain client.exe and script.npk")
    target = root / FILE
    backup = root / BACKUP
    if not target.is_file() and not (restore and backup.is_file()):
        raise FileNotFoundError("Client mod not installed: missing " + str(target))
    if restore:
        if not backup.is_file():
            raise FileNotFoundError("No endpoint backup to restore")
        data = backup.read_bytes()
    else:
        url = validate_url(endpoint)
        current = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(current, dict) or "http_url_prefix" not in current:
            raise ValueError("Unexpected endpoint config format")
        if not backup.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
        current["http_url_prefix"] = url
        data = (json.dumps(current, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    temp = target.with_name(target.name + ".tmp")
    try:
        temp.write_bytes(data)
        os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink()
    return target

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", default=".", help="Game installation directory")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--server-ip", help="Numeric IPv4 of your VPN-protected game server")
    group.add_argument("--restore", action="store_true")
    args = parser.parse_args(argv)
    try:
        path = patch(args.game_dir, ("http://%s:8000/" % args.server_ip) if args.server_ip else None, args.restore)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(1, "Patch failed: %s\n" % exc)
    print("Updated: %s" % path)

if __name__ == "__main__":
    main()
