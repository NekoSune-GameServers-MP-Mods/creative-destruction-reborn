"""Account-scoped, persistent player profiles. No global SAVE object.

This is a backend building block. Legacy offline_server.py is NOT migrated and
must remain fail-closed for remote gameplay until all handlers use this store.
"""
import json
import sqlite3
import threading
import time

MAX_PROFILE_BYTES = 16384
DEFAULT_PROFILE = {
    "name": "", "gender": 1, "guide_finish": 0,
    "gold": 0, "star": 0, "diamond": 0,
}


class VersionConflict(Exception):
    pass


class PlayerProfileStore:
    def __init__(self, db_path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(db_path), timeout=10, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("PRAGMA journal_mode=WAL")
        with self.db:
            self.db.execute("""CREATE TABLE IF NOT EXISTS player_profiles (
                account_id INTEGER PRIMARY KEY,
                version INTEGER NOT NULL DEFAULT 1,
                payload TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )""")

    @staticmethod
    def _account_id(account_id):
        if type(account_id) is not int or account_id <= 0:
            raise ValueError("Verified positive integer account_id required")
        return account_id

    @staticmethod
    def _encode(profile):
        if not isinstance(profile, dict):
            raise ValueError("Profile must be a JSON object")
        if set(profile) != set(DEFAULT_PROFILE):
            raise ValueError("Unexpected profile keys")
        if not isinstance(profile["name"], str) or len(profile["name"]) > 24:
            raise ValueError("Invalid role name")
        for key in ("gender", "guide_finish", "gold", "star", "diamond"):
            if type(profile[key]) is not int:
                raise ValueError("Invalid profile field: " + key)
        if profile["gender"] not in (1, 2) or not 0 <= profile["guide_finish"] <= 255:
            raise ValueError("Invalid gender or guide progress")
        if any(not 0 <= profile[k] <= 999999999 for k in ("gold", "star", "diamond")):
            raise ValueError("Invalid currency")
        raw = json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if len(raw.encode("utf-8")) > MAX_PROFILE_BYTES:
            raise ValueError("Profile exceeds size limit")
        return raw

    def load_or_create(self, verified_account_id):
        account_id = self._account_id(verified_account_id)
        with self.lock, self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO player_profiles(account_id,version,payload,updated_at) VALUES (?,1,?,?)",
                (account_id, self._encode(DEFAULT_PROFILE), int(time.time())))
            row = self.db.execute(
                "SELECT version,payload FROM player_profiles WHERE account_id=?", (account_id,)
            ).fetchone()
            return {"account_id": account_id, "version": row["version"],
                    "profile": json.loads(row["payload"])}

    def save(self, verified_account_id, expected_version, profile):
        account_id = self._account_id(verified_account_id)
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError("Expected positive profile version")
        payload = self._encode(profile)
        with self.lock, self.db:
            cur = self.db.execute(
                """UPDATE player_profiles SET payload=?,version=version+1,updated_at=?
                   WHERE account_id=? AND version=?""",
                (payload, int(time.time()), account_id, expected_version))
            if cur.rowcount != 1:
                raise VersionConflict("Profile missing or modified by another session")
            return expected_version + 1

    def close(self):
        with self.lock:
            self.db.close()
