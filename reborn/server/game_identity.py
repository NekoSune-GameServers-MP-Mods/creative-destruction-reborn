"""Identity-to-game session bridge for Steam Reborn TCP client.

A short-lived ticket issued via authenticated HTTPS is redeemed at C_LOGIN_AUTH,
then server-issued phase tickets bind the gateway and battle sockets. No account
password or long-lived bearer token travels through the legacy cleartext socket.
"""
import hashlib
import json
import os
import threading
import time
from accounts import AccountStore
from multiplayer_sessions import MultiplayerRegistry, SessionRejected
from player_profiles import PlayerProfileStore


class GameIdentity:
    def __init__(self, db_path):
        self.accounts = AccountStore(db_path)
        self.profiles = PlayerProfileStore(db_path)
        self.sessions = MultiplayerRegistry(self.accounts, self.profiles)
        self.lock = threading.RLock()
        self.gateway_pending = {}  # sha256(ticket) -> (session_id, monotonic expiry)
        self.battle_pending = {}   # sha256(ticket) -> (session_id, monotonic expiry)
        self.state_store = None

    def prune(self):
        """Forget abandoned login stages; they must not permanently lock accounts."""
        now = time.monotonic()
        with self.lock:
            for key, (sid, expiry) in list(self.gateway_pending.items()):
                if now >= expiry:
                    del self.gateway_pending[key]
                    self.sessions.disconnect(sid)
                    if self.state_store is not None:
                        self.state_store.detach(sid)
            for key, (_, expiry) in list(self.battle_pending.items()):
                if now >= expiry:
                    del self.battle_pending[key]

    @staticmethod
    def digest(raw):
        return hashlib.sha256(raw.encode("ascii")).digest()

    def authenticate(self, sauth_json):
        if isinstance(sauth_json, bytes):
            try:
                sauth_json = sauth_json.decode("ascii")
            except UnicodeDecodeError:
                return None
        if not isinstance(sauth_json, str) or len(sauth_json) > 512:
            return None
        try:
            data = json.loads(sauth_json)
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict) or set(data) != {"game_ticket"}:
            return None
        raw = data["game_ticket"]
        self.prune()
        with self.lock:
            account = self.accounts.consume_game_login_ticket(raw)
            if account is None:
                return None
            try:
                stage = self.sessions.open_verified_identity(account)
            except SessionRejected:
                return None
            self.gateway_pending[self.digest(stage["gateway_ticket"])] = (
                stage["session_id"], time.monotonic() + 60)
            return {
                "session_id": stage["session_id"], "account_id": account["id"],
                "username": account["username"], "auth_sn": stage["gateway_ticket"],
                "profile": self.sessions.account_snapshot(stage["session_id"]),
            }

    def gate(self, ticket, conn):
        if isinstance(ticket, bytes):
            try:
                ticket = ticket.decode("ascii")
            except UnicodeDecodeError:
                return None
        if not isinstance(ticket, str) or not 32 <= len(ticket) <= 256:
            return None
        self.prune()
        with self.lock:
            entry = self.gateway_pending.pop(self.digest(ticket), None)
            if entry is None:
                return None
            sid, expires = entry
            if time.monotonic() >= expires:
                return None
            if not self.sessions.redeem_gateway(sid, ticket, conn):
                self.sessions.disconnect(sid)
                return None
            conn.session_id = sid
            return self.sessions.account_snapshot(sid)

    def start_match(self, conn, room_id):
        sid = getattr(conn, "session_id", None)
        with self.lock:
            self.sessions.join_room(sid, room_id)
            ticket = self.sessions.issue_battle(sid)
            self.battle_pending[self.digest(ticket)] = (sid, time.monotonic() + 60)
            return ticket

    def battle(self, ticket, conn):
        if isinstance(ticket, bytes):
            try:
                ticket = ticket.decode("ascii")
            except UnicodeDecodeError:
                return None
        if not isinstance(ticket, str) or not 32 <= len(ticket) <= 256:
            return None
        self.prune()
        with self.lock:
            entry = self.battle_pending.pop(self.digest(ticket), None)
            if entry is None:
                return None
            sid, expires = entry
            if time.monotonic() >= expires or not self.sessions.redeem_battle(sid, ticket, conn):
                return None
            conn.session_id = sid
            return self.sessions.account_snapshot(sid)

    def leave(self, conn):
        sid = getattr(conn, "session_id", None)
        if sid is None:
            return
        with self.lock:
            self.sessions.disconnect(sid)
            for pending in (self.gateway_pending, self.battle_pending):
                for key, (value, _) in list(pending.items()):
                    if value == sid:
                        del pending[key]
            conn.session_id = None

    def close(self):
        self.profiles.close()
        self.accounts.close()
