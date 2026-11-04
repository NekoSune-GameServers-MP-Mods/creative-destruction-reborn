"""Acquire a one-use game ticket for an independent Reborn account.

Requires HTTPS. Run while Creative Destruction is open, immediately before
pressing Play; ticket expires after 45 seconds and can only be used once.
Works with Python 3.9+ on Windows and writes NO password or session bearer.
"""
import argparse
import getpass
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def post_json(url, obj, headers=None):
    data = json.dumps(obj).encode("utf-8")
    request = Request(url, data=data, method="POST", headers=dict(
        {"Content-Type": "application/json"}, **(headers or {})))
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read(8192).decode("utf-8"))


def write_game_ticket(directory, ticket):
    if not isinstance(ticket, str) or not 32 <= len(ticket) <= 256:
        raise ValueError("Invalid game ticket")
    doc = Path(directory) / "Documents"
    if not doc.is_dir():
        raise ValueError("No Documents directory at " + str(doc))
    path = doc / "reborn_game_auth.json"
    tmp = doc / ".reborn_game_auth.tmp"
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump({"game_ticket": ticket}, stream, separators=(",", ":"))
    os.replace(str(tmp), str(path))
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--auth-url", required=True,
                        help="Your Reborn HTTPS account API root (never raw HTTP)")
    parser.add_argument("--game-dir", required=True,
                        help="Creative Destruction installation with Documents folder")
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    auth_url = args.auth_url.rstrip("/")
    if not auth_url.startswith("https://") or auth_url.startswith("https://@"):
        parser.error("The account service MUST be behind HTTPS")
    password = getpass.getpass("Reborn account password: ")
    try:
        logged_in = post_json(auth_url + "/v1/login",
                              {"username": args.username, "password": password})
        password = ""
        bearer = logged_in["token"]
        ticket = post_json(auth_url + "/v1/game-ticket", {},
                           {"Authorization": "Bearer " + bearer})["ticket"]
        bearer = ""
        path = write_game_ticket(args.game_dir, ticket)
        print("One-time login ticket saved to: " + str(path))
        print("Press Play in the already open game now (ticket lifetime: 45 seconds).")
    except (HTTPError, URLError, KeyError, ValueError, OSError) as exc:
        parser.exit(1, "Game login ticket request failed: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
