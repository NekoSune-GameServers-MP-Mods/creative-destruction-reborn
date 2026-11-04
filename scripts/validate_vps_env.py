"""Refuse VPS docker setup with a public IP or placeholder credentials."""
import ipaddress
import pathlib
import sys

def read_env(path):
    result = {}
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if sep:
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result

def validate(config):
    ip = ipaddress.IPv4Address(config["CDR_VPN_IP"])
    # Explicitly support Tailscale CGNAT or RFC1918 private addresses; reject loopback & public IP.
    private = ip in ipaddress.ip_network("100.64.0.0/10") or any(
        ip in net for net in (ipaddress.ip_network("10.0.0.0/8"),
                             ipaddress.ip_network("172.16.0.0/12"),
                             ipaddress.ip_network("192.168.0.0/16"))
    )
    if not private or ip.is_loopback or ip.is_multicast or ip.is_unspecified:
        raise ValueError("CDR_VPN_IP must be RFC1918 or Tailscale CGNAT IPv4, never a public IP")
    token = config["CDR_STAFF_TOKEN"]
    if len(token) < 32 or token.startswith("REPLACE_") or len(set(token)) < 12:
        raise ValueError("CDR_STAFF_TOKEN must be a strong random 32+ character secret")
    return True

if __name__ == "__main__":
    try:
        validate(read_env(sys.argv[1] if len(sys.argv) > 1 else ".env"))
    except (OSError, KeyError, ValueError) as exc:
        sys.exit("Unsafe VPS configuration: %s" % exc)
    print("VPS configuration validated (does not guarantee firewall or game protocol security)")
