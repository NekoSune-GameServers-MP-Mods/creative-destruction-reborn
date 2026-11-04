"""Independent player identity store. No dependencies beyond Python stdlib.

Account registration and sessions are for the restoration server only, never NetEase.
Tokens are random and only their SHA-256 digests are persisted. All passwords use scrypt.
"""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
import time

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,23}$")
ITER_N = 2 ** 14
TOKEN_TTL = 60 * 60 * 12
MAX_SESSIONS = 5

class AuthError(Exception):
    pass

class AccountStore:
    def __init__(self, db_path):
        self.path = str(db_path)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        with self.db:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                salt BLOB NOT NULL,
                password_hash BLOB NOT NULL,
                created_at INTEGER NOT NULL,
                disabled INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash BLOB PRIMARY KEY,
                account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_account ON sessions(account_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
            """)

    @staticmethod
    def password_hash(password, salt):
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=ITER_N, r=8, p=1, dklen=32)

    @staticmethod
    def check_password(password):
        if not isinstance(password, str) or len(password) < 12 or len(password) > 128:
            raise AuthError("Password must be 12-128 characters")

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode("ascii")).digest()

    def register(self, username, password):
        if not isinstance(username, str) or not NAME_RE.fullmatch(username):
            raise AuthError("Username must be 3-24 alphanumeric, underscore or hyphen characters")
        self.check_password(password)
        salt = os.urandom(16)
        digest = self.password_hash(password, salt)
        with self.lock, self.db:
            try:
                cur = self.db.execute(
                    "INSERT INTO accounts(username,salt,password_hash,created_at) VALUES(?,?,?,?)",
                    (username, salt, digest, int(time.time())))
            except sqlite3.IntegrityError:
                raise AuthError("Username unavailable")
            return {"id": cur.lastrowid, "username": username}

    def login(self, username, password):
        # Always calculate a password hash even if the user is missing.
        if not isinstance(username, str) or not isinstance(password, str) or len(password) > 128:
            raise AuthError("Invalid credentials")
        with self.lock:
            row = self.db.execute("SELECT * FROM accounts WHERE username=?", (username,)).fetchone()
            salt = row["salt"] if row else b"\x00" * 16
            expected = row["password_hash"] if row else b"\x00" * 32
            actual = self.password_hash(password, salt)
            if not hmac.compare_digest(actual, expected) or row is None or row["disabled"]:
                raise AuthError("Invalid credentials")
            return self._issue(row["id"], row["username"])

    def _issue(self, account_id, username):
        raw = secrets.token_urlsafe(48)
        now = int(time.time())
        with self.db:
            self.db.execute("DELETE FROM sessions WHERE expires_at<=?", (now,))
            rows = self.db.execute("SELECT token_hash FROM sessions WHERE account_id=? ORDER BY created_at DESC", (account_id,)).fetchall()
            for row in rows[MAX_SESSIONS-1:]:
                self.db.execute("DELETE FROM sessions WHERE token_hash=?", (row["token_hash"],))
            self.db.execute("INSERT INTO sessions(token_hash,account_id,expires_at,created_at) VALUES(?,?,?,?)",
                            (self.digest(raw), account_id, now + TOKEN_TTL, now))
        return {"token": raw, "expires_at": now + TOKEN_TTL, "account": {"id": account_id, "username": username}}

    def resolve(self, token):
        if not isinstance(token, str) or len(token) > 256 or not token.isascii():
            return None
        now = int(time.time())
        with self.lock:
            row = self.db.execute(
                """SELECT a.id,a.username,a.disabled FROM sessions s
                   JOIN accounts a ON a.id=s.account_id
                   WHERE s.token_hash=? AND s.expires_at>?""",
                (self.digest(token), now)).fetchone()
            if not row or row["disabled"]:
                return None
            return {"id": row["id"], "username": row["username"]}

    def revoke(self, token):
        if not isinstance(token, str) or not token.isascii() or len(token) > 256:
            return
        with self.lock, self.db:
            self.db.execute("DELETE FROM sessions WHERE token_hash=?", (self.digest(token),))

    def revoke_all(self, account_id):
        with self.lock, self.db:
            self.db.execute("DELETE FROM sessions WHERE account_id=?", (account_id,))

    def close(self):
        self.db.close()
