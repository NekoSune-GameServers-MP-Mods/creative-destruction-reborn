"""Worker node reports game TCP reachability to private central cluster API.

Only use a trusted private network or an authenticated HTTPS endpoint.
Never send node keys over the public Internet using HTTP.
"""
import ipaddress
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request


def validate_control_url(url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Invalid cluster URL")
    # Cleartext is permitted only to localhost: outside containers use a private
    # tunnel/VPN + TLS, never a public or private plaintext HTTP hop.
    if parts.scheme == "http" and parts.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("Remote control plane requires HTTPS")
    if parts.path not in ("", "/"):
        raise ValueError("Cluster URL must be an origin without path")
    return url.rstrip("/")


def run_once(url, node_id, key, target_host, target_port=4000):
    if not 1 <= int(target_port) <= 65535:
        raise ValueError("Invalid game port")
    # This is only local service reachability; NOT playable matchmaking health.
    try:
        with socket.create_connection((target_host, target_port), timeout=2):
            reachable = True
    except OSError:
        reachable = False
    payload = json.dumps({"node_id": node_id, "game_reachable": reachable}).encode("utf-8")
    req = urllib.request.Request(url + "/v1/cluster/heartbeat", data=payload,
        headers={"Content-Type": "application/json", "X-CDR-Node-Key": key}, method="POST")
    with urllib.request.urlopen(req, timeout=8) as response:
        if response.status != 200:
            raise RuntimeError("Cluster heartbeat rejected")
    return reachable


def main():
    url = validate_control_url(os.environ["CDR_CLUSTER_URL"])
    node_id = os.environ["CDR_NODE_ID"]
    key = os.environ["CDR_NODE_KEY"]
    if len(key) < 32:
        raise ValueError("CDR_NODE_KEY must be the generated node credential")
    target_host = os.getenv("CDR_GAME_SERVICE", "game-server")
    while True:
        try:
            reachable = run_once(url, node_id, key, target_host)
            print("cluster heartbeat: game tcp %s" % ("reachable" if reachable else "unavailable"), flush=True)
        except (urllib.error.URLError, OSError, ValueError, RuntimeError) as exc:
            print("cluster heartbeat failed: %s" % exc.__class__.__name__, flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
