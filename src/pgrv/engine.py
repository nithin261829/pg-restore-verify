"""Backup, restore-verify and retention.

A backup is taken from an exported snapshot, and the source fingerprint is computed inside the
same transaction, so the dump and the fingerprint describe exactly the same data even while the
database keeps taking writes.
"""
import json
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from .catalog import Catalog
from .config import Config
from .fingerprint import diff, table_fingerprints
from .store import open_store


@dataclass
class VerifyResult:
    backup_id: int
    ok: bool
    duration_s: float
    problems: list[str] = field(default_factory=list)


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        tool = os.path.basename(cmd[0])
        raise RuntimeError(f"{tool} exited {proc.returncode}: {proc.stderr.strip()[:500]}")


def backup(cfg: Config, catalog: Catalog) -> int:
    started = time.monotonic()
    dbname = conninfo_to_dict(cfg.source_dsn).get("dbname", "db")
    key = f"{dbname}-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.dump"
    with tempfile.TemporaryDirectory() as tmp, psycopg.connect(cfg.source_dsn) as conn:
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        snapshot = conn.execute("SELECT pg_export_snapshot()").fetchone()[0]
        fingerprint = table_fingerprints(conn)
        archive = os.path.join(tmp, key)
        # The exporting transaction stays open until pg_dump finishes, so the snapshot stays valid.
        _run(["pg_dump", "--format=custom", f"--snapshot={snapshot}", f"--file={archive}",
              f"--dbname={cfg.source_dsn}"])
        conn.rollback()
        size = os.path.getsize(archive)
        open_store(cfg.store).put(archive, key)
    return catalog.add_backup(key, size, time.monotonic() - started, fingerprint)


def verify(cfg: Config, catalog: Catalog, backup_id: int) -> VerifyResult:
    """Restore a backup into a throwaway database and compare it with the source fingerprint."""
    started = time.monotonic()
    row = catalog.backup(backup_id)
    expected = json.loads(row["fingerprint"])
    scratch_db = f"pgrv_verify_{backup_id}_{uuid.uuid4().hex[:8]}"
    problems: list[str] = []
    with psycopg.connect(cfg.scratch_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(scratch_db)))
        try:
            with tempfile.TemporaryDirectory() as tmp:
                archive = os.path.join(tmp, row["key"])
                open_store(cfg.store).get(row["key"], archive)
                target = make_conninfo(cfg.scratch_dsn, dbname=scratch_db)
                _run(["pg_restore", "--no-owner", "--no-acl", "--exit-on-error", f"--dbname={target}", archive])
                with psycopg.connect(target) as conn:
                    problems = diff(expected, table_fingerprints(conn))
        except Exception as exc:  # noqa: BLE001 - any failed restore is a verification result, not a crash
            problems = [str(exc)]
        finally:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(scratch_db)))
    result = VerifyResult(backup_id, not problems, time.monotonic() - started, problems)
    catalog.add_verification(backup_id, result.ok, result.duration_s, problems)
    return result


def prune(cfg: Config, catalog: Catalog) -> list[str]:
    """Keep the newest `retention` backups, and never delete the newest backup that passed a restore test."""
    live = catalog.live_backups()
    protected = catalog.db.execute(
        "SELECT b.id FROM backups b JOIN verifications v ON v.backup_id = b.id "
        "WHERE v.ok = 1 AND b.deleted = 0 ORDER BY b.created_at DESC, b.id DESC LIMIT 1"
    ).fetchone()
    keep = {r["id"] for r in live[: cfg.retention]} | ({protected["id"]} if protected else set())
    store = open_store(cfg.store)
    removed = []
    for r in live:
        if r["id"] not in keep:
            store.delete(r["key"])
            catalog.mark_deleted(r["id"])
            removed.append(r["key"])
    return removed
