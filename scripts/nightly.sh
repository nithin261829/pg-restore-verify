#!/usr/bin/env bash
# Nightly job: backup, restore-test and prune. Exits non-zero (so cron or the scheduler alerts)
# when the restore test fails. Configure with the PGRV_* environment variables.
set -euo pipefail

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

: "${PGRV_SOURCE_DSN:?set PGRV_SOURCE_DSN}"
: "${PGRV_SCRATCH_DSN:?set PGRV_SCRATCH_DSN}"

log "starting backup and restore test"
if output=$(pgrv run); then
  log "ok: ${output}"
else
  log "restore test FAILED: ${output}"
  exit 1
fi
