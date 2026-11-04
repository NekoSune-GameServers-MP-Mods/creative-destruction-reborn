"""Per-verified-account legacy game state, isolated using contextvars.

Each connection callback and background battle worker must run with its
CURRENT_SESSION context. No unverified remote socket may bind a player state.
"""
import contextvars
import json
import os
import sqlite3
import threading
import time
from collections.abc import MutableMapping

CURRENT_SESSION = contextvars.ContextVar("cdr_game_session", default=None)


class GameStates:
    def __init__(self, db_path, legacy_save):
        self.lock = threading.RLock()
        self.legacy_save = legacy_save
        self.db = sqlite3.connect(str(db_path), timeout=10, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("PRAGMA journal_mode=WAL")
        with self.db:
            self.db.execute("""CREATE TABLE IF NOT EXISTS game_player_saves(
                account_id INTEGER PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )""")
        self.sessions = {}    # verified session_id -> state bundle

    def attach(self, session_id, account_id, name):
        if not session_id or type(account_id) is not int or account_id <= 0:
            raise ValueError("Verified account and session required")
        with self.lock:
            if session_id in self.sessions:
                return self.sessions[session_id]
            row = self.db.execute(
                "SELECT payload FROM game_player_saves WHERE account_id=?", (account_id,)).fetchone()
            if row:
                save = json.loads(row["payload"])
                if not isinstance(save, dict):
                    raise ValueError("Corrupt player save")
            else:
                save = {"name": "", "gender": 1, "guide_finish": 255,
                        "gold": 0, "star": 0, "diamond": 0}
            save["uid"] = 100000 + account_id
            save["aid"] = account_id
            bundle = {
                "account_id": account_id, "save": save,
                "gate": {"conn": None}, "fight": {"fight_id": 0},
            }
            self.sessions[session_id] = bundle
            return bundle

    def get(self):
        sid = CURRENT_SESSION.get()
        if sid is None:
            return None
        with self.lock:
            return self.sessions.get(sid)

    def save_current(self):
        bundle = self.get()
        if bundle is None:
            raise ValueError("No verified player session")
        save = bundle["save"]
        if save.get("uid") != 100000 + bundle["account_id"] or save.get("aid") != bundle["account_id"]:
            raise ValueError("Cannot persist changed player identity")
        data = json.dumps(save, ensure_ascii=False, separators=(",", ":"))
        if len(data.encode("utf-8")) > 1048576:
            raise ValueError("Player save too large")
        with self.lock, self.db:
            self.db.execute(
                """INSERT INTO game_player_saves(account_id,payload,updated_at)
                   VALUES(?,?,?) ON CONFLICT(account_id)
                   DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at""",
                (bundle["account_id"], data, int(time.time())))

    def detach(self, session_id):
        with self.lock:
            self.sessions.pop(session_id, None)


class ContextMapping(MutableMapping):
    def __init__(self, states, key, local_fallback):
        self.states, self.key, self.local = states, key, local_fallback

    def target(self):
        bundle = self.states.get()
        if CURRENT_SESSION.get() is not None and bundle is None:
            raise PermissionError("Expired game session")
        return bundle[self.key] if bundle is not None else self.local

    def __getitem__(self, key):
        return self.target()[key]

    def __setitem__(self, key, value):
        self.target()[key] = value

    def __delitem__(self, key):
        del self.target()[key]

    def __iter__(self):
        return iter(self.target())

    def __len__(self):
        return len(self.target())

    def __repr__(self):
        return repr(self.target())
