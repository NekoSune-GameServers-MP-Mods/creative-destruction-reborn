"""Fail-closed listener config. Remote listening is NOT a multiplayer security model."""
import ipaddress
import os

def listener_host():
    host = os.getenv("CDR_BIND_HOST", "127.0.0.1").strip()
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("CDR_BIND_HOST must be an IP address, not a hostname") from exc
    if not address.is_loopback and os.getenv("CDR_ALLOW_REMOTE") != "1":
        raise ValueError(
            "Non-loopback bind refused. Remote mode is experimental and unencrypted. "
            "Set CDR_ALLOW_REMOTE=1 only inside a trusted VPN/firewalled test network."
        )
    return host

def connection_limit():
    value = int(os.getenv("CDR_MAX_CONNECTIONS", "32"))
    if not 1 <= value <= 256:
        raise ValueError("CDR_MAX_CONNECTIONS must be between 1 and 256")
    return value

def advertised_host():
    """Address sent to the game client; never send Docker's wildcard bind address."""
    value = os.getenv("CDR_ADVERTISE_HOST", "127.0.0.1").strip()
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError("CDR_ADVERTISE_HOST must be a numeric IP address") from exc
    return value
