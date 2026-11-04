"""Opt-in, ONE client IP, ONE player lab admission for the legacy offline simulator.

This is NOT account authentication and is NOT safe for public multiplayer.
Only enable with host-level/provider firewall IP restrictions in a controlled lab.
Tickets protect the gateway/battle handoff, but the initial legacy Steam login
has no user credential; anyone at the allowed source IP can start a new session.
"""
import hmac
import ipaddress
import os
import secrets
import threading
import time


class RemoteLab:
    def __init__(self, enabled=False, allowed_ip="", client_version="3.0.248.0", clock=None):
        self.enabled = bool(enabled)
        self.clock = clock or time.monotonic
        self.client_version = client_version
        self.lock = threading.RLock()
        self.allowed_ip = ""
        self.session = None
        if self.enabled:
            try:
                address = ipaddress.IPv4Address(allowed_ip)
            except ValueError as exc:
                raise ValueError("CDR_REMOTE_TEST_IP must be an IPv4 address") from exc
            if address.is_unspecified or address.is_multicast or address.is_loopback:
                raise ValueError("CDR_REMOTE_TEST_IP must be the one trusted client IP")
            self.allowed_ip = str(address)
            if not client_version or len(client_version) > 32:
                raise ValueError("Invalid CDR_REMOTE_TEST_CLIENT_VERSION")

    @classmethod
    def from_environment(cls):
        flag = os.getenv("CDR_REMOTE_SINGLE_PLAYER_TEST", "0")
        if flag not in ("0", "1"):
            raise ValueError("CDR_REMOTE_SINGLE_PLAYER_TEST must be 0 or 1")
        return cls(flag == "1", os.getenv("CDR_REMOTE_TEST_IP", ""),
                   os.getenv("CDR_REMOTE_TEST_CLIENT_VERSION", "3.0.248.0"))

    def allowed(self, ip):
        return self.enabled and ip == self.allowed_ip

    def issue_login(self, ip, version, sdkuid, sauth_json):
        """Issue a one-use auth_sn, only for the explicitly allowed test client."""
        if not self.allowed(ip) or version != self.client_version:
            return None
        if sdkuid != "offline_player" or sauth_json != "{}":
            return None
        with self.lock:
            # One game session only. Do not steal it while a gateway is active.
            if self.session is not None and self.session.get("gateway") is not None:
                return None
            ticket = secrets.token_urlsafe(32)
            self.session = {
                "ip": ip, "auth_sn": ticket, "login_exp": self.clock() + 60,
                "gateway": None, "battle_ticket": None, "battle_exp": 0,
                "battle": None,
            }
            return ticket

    def pending(self, ip):
        with self.lock:
            s = self.session
            return bool(self.allowed(ip) and s is not None and s["ip"] == ip
                        and s["auth_sn"] and self.clock() < s["login_exp"]
                        and s["gateway"] is None)

    def enter_gateway(self, conn, auth_sn):
        with self.lock:
            s = self.session
            if not self.pending(conn.addr[0]) or not isinstance(auth_sn, str):
                return False
            if not hmac.compare_digest(auth_sn, s["auth_sn"]):
                return False
            s["auth_sn"] = None    # consume handshake ticket
            s["gateway"] = conn
            conn.lab_gateway = True
            return True

    def issue_battle(self, conn):
        with self.lock:
            s = self.session
            if s is None or s["gateway"] is not conn:
                return None
            ticket = secrets.token_urlsafe(32)
            s["battle_ticket"] = ticket
            s["battle_exp"] = self.clock() + 60
            return ticket

    def enter_battle(self, conn, ticket):
        with self.lock:
            s = self.session
            if not self.allowed(conn.addr[0]) or s is None:
                return False
            if s["gateway"] is None or s["battle"] is not None:
                return False
            if not isinstance(ticket, str) or not s["battle_ticket"] or self.clock() >= s["battle_exp"]:
                return False
            if not hmac.compare_digest(ticket, s["battle_ticket"]):
                return False
            s["battle_ticket"] = None
            s["battle"] = conn
            conn.lab_battle = True
            return True

    def disconnect(self, conn):
        with self.lock:
            s = self.session
            if s is None:
                return
            if s["battle"] is conn:
                s["battle"] = None
            if s["gateway"] is conn:
                self.session = None


def wire_str(value):
    """Protocol VARSTR decodes to bytes; reject invalid or huge input."""
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    return value if isinstance(value, str) and len(value) <= 256 else None
