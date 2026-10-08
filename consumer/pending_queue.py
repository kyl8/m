from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class PendingQueue:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._create()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _create(self) -> None:
        with self._db() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS pending (
                    message_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    queued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT
                )
            """)

    def put(self, reading: dict[str, Any], error: str) -> bool:
        with self._db() as db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO pending(message_id, payload, last_error) VALUES (?, ?, ?)",
                (reading["message_id"], json.dumps(reading, ensure_ascii=False), error),
            )
            return cursor.rowcount == 1

    def items(self, limit: int = 1000) -> Iterator[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute(
                "SELECT message_id, payload, attempts FROM pending ORDER BY queued_at LIMIT ?", (limit,)
            ).fetchall()
        for row in rows:
            yield {"message_id": row["message_id"], "reading": json.loads(row["payload"]), "attempts": row["attempts"]}

    def mark_attempt(self, message_id: str, error: str) -> None:
        with self._db() as db:
            db.execute(
                "UPDATE pending SET attempts = attempts + 1, last_error = ? WHERE message_id = ?",
                (error, message_id),
            )

    def remove(self, message_id: str) -> None:
        with self._db() as db:
            db.execute("DELETE FROM pending WHERE message_id = ?", (message_id,))

    def count(self) -> int:
        with self._db() as db:
            return int(db.execute("SELECT COUNT(*) FROM pending").fetchone()[0])
