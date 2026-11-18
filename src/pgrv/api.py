"""Self-service HTTP API over the same engine the CLI uses."""
import json

from fastapi import FastAPI, HTTPException, Response

from . import engine
from .catalog import Catalog
from .config import Config
from .metrics import render


def create_app(cfg: Config | None = None) -> FastAPI:
    cfg = cfg or Config.from_env()
    catalog = Catalog(cfg.catalog_path)
    app = FastAPI(title="pg-restore-verify")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/backups")
    def list_backups():
        return [
            {"id": r["id"], "key": r["key"], "created_at": r["created_at"], "size_bytes": r["size_bytes"],
             "tables": len(json.loads(r["fingerprint"]))}
            for r in catalog.live_backups()
        ]

    @app.post("/backups", status_code=201)
    def create_backup():
        return {"id": engine.backup(cfg, catalog)}

    @app.post("/backups/{backup_id}/verify")
    def verify_backup(backup_id: int):
        try:
            result = engine.verify(cfg, catalog, backup_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="backup not found")
        return {"backup_id": result.backup_id, "ok": result.ok, "duration_s": round(result.duration_s, 3),
                "problems": result.problems}

    @app.post("/prune")
    def prune_backups():
        return {"removed": engine.prune(cfg, catalog)}

    @app.get("/metrics")
    def metrics():
        return Response(render(catalog), media_type="text/plain; version=0.0.4")

    return app
