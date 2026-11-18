# pg-restore-verify

A backup only counts once it has been restored and checked. This tool takes PostgreSQL backups,
restores each one into a throwaway database, compares the restored data with the source, and
exposes the result as Prometheus metrics so a failed restore pages someone before the day it is needed.

## What it does

- **Snapshot-consistent backups.** It opens a `REPEATABLE READ` transaction, exports its snapshot with
  `pg_export_snapshot()`, fingerprints every table inside that transaction, and runs
  `pg_dump --snapshot` against the same snapshot. The dump and the fingerprint describe the same data,
  even while the database keeps taking writes (covered by a test that inserts rows during the backup).
- **Restore tests.** `pgrv verify` creates a scratch database, runs `pg_restore --exit-on-error`,
  fingerprints the result and drops the scratch database. Each table's fingerprint is its row count plus
  an md5 over its rows in a fixed (`COLLATE "C"`) order, so missing, extra or changed rows all fail the check.
- **Storage.** A local directory (`file://`) or any S3-compatible bucket (`s3://bucket/prefix`).
- **Retention.** Keeps the newest N backups and never deletes the newest backup that passed a restore test.
- **Self-service API.** FastAPI endpoints to create, list, verify and prune backups, plus `/metrics`.
- **Alerting.** Prometheus rules in [`deploy/prometheus-rules.yml`](deploy/prometheus-rules.yml) page
  when a restore test fails or no backup has run in 26 hours.
- **Scheduling.** [`scripts/nightly.sh`](scripts/nightly.sh) runs backup, restore test and prune, and
  exits non-zero when the restore test fails, so cron or any scheduler can alert on it.

## Quick start

```bash
docker compose up -d --build pgrv          # source DB, scratch DB, S3 mock and the API on :8080
curl -X POST localhost:8080/backups        # {"id": 1}
curl -X POST localhost:8080/backups/1/verify
curl localhost:8080/metrics | grep pgrv_
```

On a local run against 200,000 rows, the backup took about 2.2 s and the restore test about 2.8 s.

## CLI

```bash
pgrv backup            # snapshot-consistent backup
pgrv verify [ID]       # restore test (newest backup by default)
pgrv list
pgrv prune
pgrv run               # backup + verify + prune; exit 1 if the restore test fails
pgrv serve --port 8080
```

Configuration is through environment variables: `PGRV_SOURCE_DSN`, `PGRV_SCRATCH_DSN`, `PGRV_STORE`,
`PGRV_S3_ENDPOINT`, `PGRV_CATALOG` and `PGRV_RETENTION`.

## Tests

```bash
docker compose --profile test up --build --abort-on-container-exit --exit-code-from tests source scratch tests
```

The suite runs against two real PostgreSQL 16 servers: a clean round trip, writes during the backup,
a truncated archive, changed data, retention, and the HTTP API. GitHub Actions runs the same suite
with ruff on every push.

## Limits

- Logical backups only (`pg_dump`). Point-in-time recovery with WAL archiving is not covered yet.
- The fingerprint reads every row, so restore tests on very large databases need a sampling mode.
- The run catalog is a local SQLite file.
