from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from project_io import iso_now


class StateStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._create()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

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
            db.executescript("""
                CREATE TABLE IF NOT EXISTS counters (
                    name TEXT PRIMARY KEY,
                    value INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS metadata (
                    name TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    device_id TEXT,
                    frame_counter INTEGER,
                    generated_at TEXT,
                    published_at TEXT,
                    received_at TEXT,
                    validated_at TEXT,
                    written_at TEXT,
                    confirmed_at TEXT,
                    status TEXT,
                    original_json TEXT,
                    error TEXT,
                    latency_ms REAL
                );
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    last_frame INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS simulator_frames (
                    device_id TEXT PRIMARY KEY,
                    last_frame INTEGER NOT NULL
                );
            """)

    def increment(self, name: str, amount: int = 1) -> None:
        with self._db() as db:
            db.execute(
                "INSERT INTO counters(name, value) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET value = value + excluded.value",
                (name, amount),
            )

    def counters(self) -> dict[str, int]:
        with self._db() as db:
            return {row["name"]: row["value"] for row in db.execute("SELECT name, value FROM counters")}

    def set_meta(self, name: str, value: str) -> None:
        with self._db() as db:
            db.execute(
                "INSERT INTO metadata(name, value) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET value = excluded.value",
                (name, value),
            )

    def get_meta(self, name: str) -> str | None:
        with self._db() as db:
            row = db.execute("SELECT value FROM metadata WHERE name = ?", (name,)).fetchone()
        return str(row["value"]) if row else None

    def first_seen(self, reading: dict[str, Any]) -> bool:
        with self._db() as db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO messages(message_id, device_id, frame_counter, generated_at, "
                "received_at, status, original_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    reading["message_id"], reading.get("device_id"), reading.get("frame_counter"),
                    reading.get("sent_at"), iso_now(), "received", json.dumps(reading, ensure_ascii=False),
                ),
            )
            return cursor.rowcount == 1

    def stage(
        self,
        message_id: str,
        stage: str,
        *,
        error: str | None = None,
        latency_ms: float | None = None,
        occurred_at: str | None = None,
    ) -> None:
        columns = {
            "published": "published_at",
            "received": "received_at",
            "validated": "validated_at",
            "written": "written_at",
            "confirmed": "confirmed_at",
        }
        timestamp_column = columns.get(stage)
        if not timestamp_column:
            raise ValueError(f"etapa desconhecida: {stage}")
        with self._db() as db:
            db.execute(
                f"UPDATE messages SET {timestamp_column} = ?, status = ?, error = COALESCE(?, error), "
                "latency_ms = COALESCE(?, latency_ms) WHERE message_id = ?",
                (occurred_at or iso_now(), stage, error, latency_ms, message_id),
            )

    def reject(self, message_id: str, error: str) -> None:
        with self._db() as db:
            db.execute("UPDATE messages SET status = 'rejected', error = ? WHERE message_id = ?", (error, message_id))

    def frame_status(self, device_id: str, frame_counter: Any) -> tuple[str, list[int]]:
        if not isinstance(frame_counter, int):
            return "unknown", []
        with self._db() as db:
            row = db.execute("SELECT last_frame FROM devices WHERE device_id = ?", (device_id,)).fetchone()
            if row is None:
                db.execute("INSERT INTO devices(device_id, last_frame) VALUES (?, ?)", (device_id, frame_counter))
                return "first", []
            last = row["last_frame"]
            if frame_counter <= last:
                return "out_of_order", []
            db.execute("UPDATE devices SET last_frame = ? WHERE device_id = ?", (frame_counter, device_id))
            missing = list(range(last + 1, frame_counter))
            return ("gap" if missing else "ordered"), missing

    def next_simulator_frame(self, device_id: str) -> int:
        with self._db() as db:
            row = db.execute(
                "SELECT last_frame FROM simulator_frames WHERE device_id = ?", (device_id,)
            ).fetchone()
            frame = 1 if row is None else int(row["last_frame"]) + 1
            db.execute(
                "INSERT INTO simulator_frames(device_id, last_frame) VALUES (?, ?) "
                "ON CONFLICT(device_id) DO UPDATE SET last_frame = excluded.last_frame",
                (device_id, frame),
            )
        return frame

    def get_message(self, message_id: str) -> dict[str, Any] | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM messages WHERE message_id = ?", (message_id,)).fetchone()
        return dict(row) if row else None

    def recent(self, limit: int = 1) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM messages ORDER BY received_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def latencies(self, limit: int = 1000) -> list[float]:
        with self._db() as db:
            rows = db.execute(
                "SELECT latency_ms FROM messages WHERE latency_ms IS NOT NULL ORDER BY received_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [float(row["latency_ms"]) for row in rows]
