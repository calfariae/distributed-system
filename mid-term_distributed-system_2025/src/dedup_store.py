import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("data/dedup.db")

class DedupStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")  # safer concurrent writes
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_events (
                    topic       TEXT NOT NULL,
                    event_id    TEXT NOT NULL,
                    processed_at TEXT NOT NULL,
                    PRIMARY KEY (topic, event_id)
                )
            """)
            conn.commit()
        logger.info("DedupStore initialised at %s", self.db_path)

    def is_duplicate(self, topic: str, event_id: str) -> bool:
        """Return True if this (topic, event_id) pair has already been processed."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_events WHERE topic = ? AND event_id = ?",
                (topic, event_id),
            ).fetchone()
        return row is not None

    def mark_processed(self, topic: str, event_id: str, processed_at: str) -> None:
        """
        Insert the (topic, event_id) pair.
        Uses INSERT OR IGNORE so calling this multiple times is safe (idempotent).
        """
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO processed_events (topic, event_id, processed_at)
                VALUES (?, ?, ?)
                """,
                (topic, event_id, processed_at),
            )
            conn.commit()