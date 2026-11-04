"""Create an independent Reborn account using a single-use invitation.

Uses HTTPS and interactive secret prompts. No passwords or invitations are
saved locally, and no administrator registration key is needed by players.
"""
import argparse
import getpass
import json
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def register(auth_url, username, password, invite_code):
    address = urlsplit(auth_url)
    if address.scheme != "https" or not address.hostname or address.username or address.password:
        raise ValueError("Account API must use HTTPS without embedded credentials")
    payload = json.dumps({
        "username": username, "password": password, "invite_code": invite_code,
    }).encode("utf-8")
    request = Request(auth_url.rstrip("/") + "/v1/register", data=payload,
                      headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read(8192))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--auth-url", required=True, help="HTTPS Reborn account API")
    parser.add_argument("--username", required=True, help="3-24 character Reborn username")
    args = parser.parse_args()
    invite = getpass.getpass("Your single-use invitation: ")
    password = getpass.getpass("Choose a password (12+ characters): ")
    check = getpass.getpass("Repeat password: ")
    if password != check:
        parser.exit(1, "Passwords do not match.\n")
    try:
        result = register(args.auth_url, args.username, password, invite)
        print("Account registered: " + result["account"]["username"])
        print("Use steam_bridge.py to log in and play.")
    except (HTTPError, URLError, ValueError, KeyError) as exc:
        code = exc.code if isinstance(exc, HTTPError) else type(exc).__name__
        parser.exit(1, "Registration failed: %s\n" % code)


if __name__ == "__main__":
    main()
