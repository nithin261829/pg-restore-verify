import json
import threading
from pathlib import Path

import psycopg

from pgrv import engine
from pgrv.metrics import render
from pgrv.store import open_store

from .conftest import needs_pg


@needs_pg
def test_backup_restores_with_identical_data(cfg, catalog):
    backup_id = engine.backup(cfg, catalog)
    result = engine.verify(cfg, catalog, backup_id)
    assert result.ok, result.problems
    tables = set(json.loads(catalog.backup(backup_id)["fingerprint"]))
    assert tables == {"public.customers", "public.orders"}


@needs_pg
def test_writes_during_backup_do_not_break_verification(cfg, catalog):
    stop = threading.Event()

    def writer():
        with psycopg.connect(cfg.source_dsn, autocommit=True) as conn:
            while not stop.is_set():
                conn.execute("INSERT INTO orders (customer_id, amount, placed_at) VALUES (1, 9.99, now())")

    t = threading.Thread(target=writer)
    t.start()
    try:
        backup_id = engine.backup(cfg, catalog)
    finally:
        stop.set()
        t.join()
    result = engine.verify(cfg, catalog, backup_id)
    assert result.ok, result.problems


@needs_pg
def test_corrupted_archive_fails_verification(cfg, catalog):
    backup_id = engine.backup(cfg, catalog)
    key = catalog.backup(backup_id)["key"]
    path = Path(open_store(cfg.store).root) / key
    data = path.read_bytes()
    path.write_bytes(data[: len(data) // 2])
    result = engine.verify(cfg, catalog, backup_id)
    assert not result.ok
    assert "pg_restore" in result.problems[0]
    assert b"pgrv_last_verification_success 0.0" in render(catalog)


@needs_pg
def test_changed_data_is_caught(cfg, catalog):
    backup_id = engine.backup(cfg, catalog)
    row = catalog.backup(backup_id)
    fp = json.loads(row["fingerprint"])
    fp["public.orders"]["rows"] += 1  # pretend the source had one more row than the archive holds
    catalog.db.execute("UPDATE backups SET fingerprint = ? WHERE id = ?", (json.dumps(fp), backup_id))
    catalog.db.commit()
    result = engine.verify(cfg, catalog, backup_id)
    assert not result.ok
    assert result.problems[0].startswith("public.orders: rows 5001 -> 5000")


@needs_pg
def test_prune_keeps_newest_verified_backup(cfg, catalog):
    verified = engine.backup(cfg, catalog)
    assert engine.verify(cfg, catalog, verified).ok
    newer = [engine.backup(cfg, catalog) for _ in range(3)]
    removed = engine.prune(cfg, catalog)
    kept = {r["id"] for r in catalog.live_backups()}
    assert kept == {verified, newer[-1], newer[-2]}
    assert len(removed) == 1
