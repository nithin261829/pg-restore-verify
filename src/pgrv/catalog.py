"""Run history in SQLite: every backup, its source fingerprint, and each restore test."""
import json
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS backups (
    id INTEGER PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL,
    size_bytes INTEGER NOT NULL,
    duration_s REAL NOT NULL,
    fingerprint TEXT NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS verifications (
    id INTEGER PRIMARY KEY,
    backup_id INTEGER NOT NULL REFERENCES backups(id),
    verified_at REAL NOT NULL,
    ok INTEGER NOT NULL,
    duration_s REAL NOT NULL,
    problems TEXT NOT NULL
);
"""


class Catalog:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def add_backup(self, key: str, size: int, duration: float, fingerprint: dict) -> int:
        cur = self.db.execute(
            "INSERT INTO backups (key, created_at, size_bytes, duration_s, fingerprint) VALUES (?, ?, ?, ?, ?)",
            (key, time.time(), size, duration, json.dumps(fingerprint)),
        )
        self.db.commit()
        return cur.lastrowid

    def add_verification(self, backup_id: int, ok: bool, duration: float, problems: list[str]) -> None:
        self.db.execute(
            "INSERT INTO verifications (backup_id, verified_at, ok, duration_s, problems) VALUES (?, ?, ?, ?, ?)",
            (backup_id, time.time(), int(ok), duration, json.dumps(problems)),
        )
        self.db.commit()

    def backup(self, backup_id: int) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM backups WHERE id = ?", (backup_id,)).fetchone()
        if row is None:
            raise KeyError(f"no backup {backup_id}")
        return row

    def live_backups(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM backups WHERE deleted = 0 ORDER BY created_at DESC, id DESC").fetchall()

    def latest_verification(self) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM verifications ORDER BY verified_at DESC, id DESC LIMIT 1").fetchone()

    def mark_deleted(self, backup_id: int) -> None:
        self.db.execute("UPDATE backups SET deleted = 1 WHERE id = ?", (backup_id,))
        self.db.commit()
