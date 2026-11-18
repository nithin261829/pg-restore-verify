"""Prometheus metrics built from the catalog on each scrape."""
from prometheus_client import CollectorRegistry, Gauge, generate_latest

from .catalog import Catalog


def render(catalog: Catalog) -> bytes:
    reg = CollectorRegistry()
    live = catalog.live_backups()
    Gauge("pgrv_backups_live", "Backups currently kept in the store", registry=reg).set(len(live))
    if live:
        newest = live[0]
        Gauge("pgrv_last_backup_timestamp_seconds", "When the newest backup finished",
              registry=reg).set(newest["created_at"])
        Gauge("pgrv_last_backup_size_bytes", "Size of the newest backup", registry=reg).set(newest["size_bytes"])
        Gauge("pgrv_last_backup_duration_seconds", "How long the newest backup took",
              registry=reg).set(newest["duration_s"])
    last = catalog.latest_verification()
    if last:
        Gauge("pgrv_last_verification_success", "1 if the latest restore test passed",
              registry=reg).set(last["ok"])
        Gauge("pgrv_last_verification_timestamp_seconds", "When the latest restore test ran",
              registry=reg).set(last["verified_at"])
        Gauge("pgrv_last_verification_duration_seconds", "How long the latest restore test took",
              registry=reg).set(last["duration_s"])
    return generate_latest(reg)
