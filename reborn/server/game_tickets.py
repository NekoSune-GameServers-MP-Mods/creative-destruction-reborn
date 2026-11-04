"""One-time, phase-bound, in-memory game handoff tickets.

Foundation only: the legacy game wire protocol is unencrypted and does NOT use this
registry yet. Never accept a client-supplied account ID in place of identity verified
against AccountStore. The remote gameplay safety gate remains enabled.
"""
import hashlib
import hmac
import secrets
import threading
import time


class TicketRegistry:
    """Issues unguessable one-use tickets for a verified account/session.

    A redeemed login ticket can only be exchanged at the designated stage, so
    a captured battle ticket cannot be reused at the gateway and vice versa.
    """

    VALID_PURPOSES = frozenset(("gateway", "battle"))

    def __init__(self, ttl=60, capacity=256, clock=None):
        if not 1 <= ttl <= 600 or not 1 <= capacity <= 10000:
            raise ValueError("Invalid ticket lifetime or capacity")
        self.ttl = ttl
        self.capacity = capacity
        self.clock = clock or time.time
        self._lock = threading.Lock()
        self._entries = {}

    @staticmethod
    def _digest(ticket):
        return hashlib.sha256(ticket.encode("ascii")).digest()

    def issue(self, account_id, purpose, session_id):
        if purpose not in self.VALID_PURPOSES:
            raise ValueError("Unknown ticket purpose")
        if not isinstance(account_id, int) or account_id <= 0:
            raise ValueError("Verified account ID is required")
        if not isinstance(session_id, str) or len(session_id) < 16:
            raise ValueError("Verified session ID is required")
        now = self.clock()
        with self._lock:
            self._expire(now)
            if len(self._entries) >= self.capacity:
                raise RuntimeError("Game ticket capacity exhausted")
            ticket = secrets.token_urlsafe(48)
            self._entries[self._digest(ticket)] = (
                account_id, purpose, session_id, now + self.ttl
            )
            return ticket

    def redeem(self, ticket, purpose, session_id):
        if purpose not in self.VALID_PURPOSES:
            return None
        if not isinstance(ticket, str) or not 32 <= len(ticket) <= 256 or not ticket.isascii():
            return None
        if not isinstance(session_id, str) or len(session_id) < 16:
            return None
        now = self.clock()
        with self._lock:
            self._expire(now)
            key = self._digest(ticket)
            entry = self._entries.get(key)
            if entry is None:
                return None
            account_id, stored_purpose, stored_session, expires_at = entry
            if not hmac.compare_digest(stored_purpose, purpose):
                return None
            if not hmac.compare_digest(stored_session, session_id):
                return None
            # Consume atomically, before a handoff can be replayed.
            del self._entries[key]
            return account_id

    def revoke_session(self, session_id):
        with self._lock:
            for digest, entry in list(self._entries.items()):
                if entry[2] == session_id:
                    del self._entries[digest]

    def _expire(self, now):
        for digest, entry in list(self._entries.items()):
            if entry[3] <= now:
                del self._entries[digest]
