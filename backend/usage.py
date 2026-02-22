import hashlib
import hmac
import sqlite3
from datetime import datetime, timezone

from fastapi import Request


def hash_ip(ip: str, salt: str) -> str:
    """HMAC-SHA256 of IP with salt, truncated to 16 hex chars."""
    return hmac.new(salt.encode(), ip.encode(), hashlib.sha256).hexdigest()[:16]


def get_client_ip(request: Request) -> str:
    """Extract real client IP from proxy headers."""
    if ip := request.headers.get("x-real-ip"):
        return ip
    if xff := request.headers.get("x-forwarded-for"):
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class UsageTracker:
    def __init__(self, db_path: str, salt: str):
        self.salt = salt
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage (
                ip_hash TEXT NOT NULL,
                date TEXT NOT NULL,
                generation_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (ip_hash, date)
            )
            """
        )
        self.conn.commit()

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def record(self, ip_hash: str) -> None:
        self.conn.execute(
            """
            INSERT INTO usage (ip_hash, date, generation_count)
            VALUES (?, ?, 1)
            ON CONFLICT(ip_hash, date) DO UPDATE SET generation_count = generation_count + 1
            """,
            (ip_hash, self._today()),
        )
        self.conn.commit()

    def get_today(self, ip_hash: str) -> int:
        row = self.conn.execute(
            "SELECT generation_count FROM usage WHERE ip_hash = ? AND date = ?",
            (ip_hash, self._today()),
        ).fetchone()
        return row[0] if row else 0

    def get_total(self, ip_hash: str) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(generation_count), 0) FROM usage WHERE ip_hash = ?",
            (ip_hash,),
        ).fetchone()
        return row[0]

    def get_global_today(self) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(generation_count), 0) FROM usage WHERE date = ?",
            (self._today(),),
        ).fetchone()
        return row[0]

    def get_global_total(self) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(generation_count), 0) FROM usage"
        ).fetchone()
        return row[0]

    def get_unique_today(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(DISTINCT ip_hash) FROM usage WHERE date = ?",
            (self._today(),),
        ).fetchone()
        return row[0]
