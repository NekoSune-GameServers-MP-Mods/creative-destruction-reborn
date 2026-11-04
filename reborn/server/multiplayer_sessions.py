"""Multi-account session and room isolation for a future authenticated game gateway.

All methods are INTERNAL server APIs, never directly exposed to the legacy
unencrypted game protocol. Only a verified AccountStore token obtained over a
secure channel may open a session. No client-supplied UID/profile is trusted.
"""
import secrets
import threading
from game_tickets import TicketRegistry


class SessionRejected(Exception):
    pass


class MultiplayerRegistry:
    def __init__(self, account_store, profile_store, max_players=128,
                 max_rooms=32, max_room_players=16, clock=None):
        if not 1 <= max_players <= 10000 or not 1 <= max_rooms <= 1000:
            raise ValueError("Invalid multiplayer capacity")
        if not 1 <= max_room_players <= max_players:
            raise ValueError("Invalid room capacity")
        self.accounts = account_store
        self.profiles = profile_store
        self.max_players = max_players
        self.max_rooms = max_rooms
        self.max_room_players = max_room_players
        self.lock = threading.RLock()
        self.tickets = TicketRegistry(ttl=60, capacity=min(10000, max_players * 3), clock=clock)
        self.sessions = {}       # server-generated ID -> verified session
        self.account_sessions = {}  # one active connection per account
        self.rooms = {}          # room ID -> {members, match_state}

    def open_authenticated(self, bearer_token):
        """Resolve a bearer token only inside a trusted authenticated service."""
        account = self.accounts.resolve(bearer_token)
        if account is None:
            raise SessionRejected("Invalid or expired account session")
        return self.open_verified_identity(account)

    def open_verified_identity(self, account):
        """Accept only the account store's verified account row (server internal)."""
        if not isinstance(account, dict) or type(account.get("id")) is not int or not account.get("username"):
            raise SessionRejected("Verified account identity required")
        account_id = account["id"]
        with self.lock:
            if account_id in self.account_sessions:
                raise SessionRejected("Account already connected")
            if len(self.sessions) >= self.max_players:
                raise SessionRejected("Server full")
            profile = self.profiles.load_or_create(account_id)
            session_id = secrets.token_urlsafe(32)
            self.sessions[session_id] = {
                "account_id": account_id, "username": account["username"],
                "profile": profile, "stage": "login", "room_id": None,
                "gateway": None, "battle": None,
            }
            self.account_sessions[account_id] = session_id
            gateway_ticket = self.tickets.issue(account_id, "gateway", session_id)
            return {"session_id": session_id, "account_id": account_id,
                    "gateway_ticket": gateway_ticket}

    def redeem_gateway(self, session_id, ticket, connection):
        with self.lock:
            s = self.sessions.get(session_id)
            if s is None or s["stage"] != "login":
                return False
            if self.tickets.redeem(ticket, "gateway", session_id) != s["account_id"]:
                return False
            s["gateway"] = connection
            s["stage"] = "gateway"
            return True

    def join_room(self, session_id, room_id):
        if not isinstance(room_id, str) or not 1 <= len(room_id) <= 64:
            raise ValueError("Invalid room ID")
        with self.lock:
            s = self.sessions.get(session_id)
            if s is None or s["stage"] not in ("gateway", "battle"):
                raise SessionRejected("Gateway not authenticated")
            room = self.rooms.get(room_id)
            if room is None:
                if len(self.rooms) >= self.max_rooms:
                    raise SessionRejected("All rooms occupied")
                room = {"members": set(), "match_state": {"tick": 0, "events": []}}
                self.rooms[room_id] = room
            if session_id not in room["members"] and len(room["members"]) >= self.max_room_players:
                raise SessionRejected("Room full")
            old = s["room_id"]
            if old is not None and old != room_id:
                self._leave(session_id, old)
            room["members"].add(session_id)
            s["room_id"] = room_id
            return {"room_id": room_id, "players": len(room["members"])}

    def issue_battle(self, session_id):
        with self.lock:
            s = self.sessions.get(session_id)
            if s is None or s["stage"] != "gateway" or s["room_id"] is None:
                raise SessionRejected("Must authenticate gateway and join a room first")
            return self.tickets.issue(s["account_id"], "battle", session_id)

    def redeem_battle(self, session_id, ticket, connection):
        with self.lock:
            s = self.sessions.get(session_id)
            if s is None or s["stage"] != "gateway" or s["room_id"] is None:
                return False
            if self.tickets.redeem(ticket, "battle", session_id) != s["account_id"]:
                return False
            s["battle"] = connection
            s["stage"] = "battle"
            return True

    def account_snapshot(self, session_id):
        with self.lock:
            s = self.sessions.get(session_id)
            if s is None:
                raise SessionRejected("Unknown session")
            # Return a fresh copy; never expose another account's mutable profile.
            return {"account_id": s["account_id"], "username": s["username"],
                    "profile": dict(s["profile"]["profile"]),
                    "profile_version": s["profile"]["version"]}

    def room_members(self, session_id):
        with self.lock:
            s = self.sessions.get(session_id)
            if s is None or s["room_id"] is None:
                raise SessionRejected("No authenticated room")
            room = self.rooms[s["room_id"]]
            return frozenset(self.sessions[sid]["account_id"] for sid in room["members"])

    def _leave(self, session_id, room_id):
        room = self.rooms.get(room_id)
        if room is None:
            return
        room["members"].discard(session_id)
        if not room["members"]:
            del self.rooms[room_id]

    def disconnect(self, session_id):
        with self.lock:
            s = self.sessions.pop(session_id, None)
            if s is None:
                return
            self.tickets.revoke_session(session_id)
            self.account_sessions.pop(s["account_id"], None)
            if s["room_id"] is not None:
                self._leave(session_id, s["room_id"])
