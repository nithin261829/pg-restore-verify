import argparse
import json
import sys

from . import engine
from .catalog import Catalog
from .config import Config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pgrv", description="PostgreSQL backups that are proven restorable.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("backup", help="take a snapshot-consistent backup")
    v = sub.add_parser("verify", help="restore a backup into a scratch database and compare it")
    v.add_argument("backup_id", nargs="?", type=int, help="defaults to the newest backup")
    sub.add_parser("list", help="list kept backups")
    sub.add_parser("prune", help="apply the retention policy")
    sub.add_parser("run", help="backup, verify and prune; exits 1 if the restore test fails")
    s = sub.add_parser("serve", help="run the HTTP API")
    s.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)

    cfg = Config.from_env()
    catalog = Catalog(cfg.catalog_path)

    if args.cmd == "serve":
        import uvicorn

        from .api import create_app

        uvicorn.run(create_app(cfg), host="0.0.0.0", port=args.port)
        return 0
    if args.cmd == "backup":
        print(json.dumps({"id": engine.backup(cfg, catalog)}))
        return 0
    if args.cmd == "list":
        for r in catalog.live_backups():
            print(f"{r['id']}\t{r['key']}\t{r['size_bytes']} bytes")
        return 0
    if args.cmd == "prune":
        print(json.dumps({"removed": engine.prune(cfg, catalog)}))
        return 0
    if args.cmd == "verify":
        backup_id = args.backup_id or catalog.live_backups()[0]["id"]
        result = engine.verify(cfg, catalog, backup_id)
    else:  # run
        result = engine.verify(cfg, catalog, engine.backup(cfg, catalog))
        engine.prune(cfg, catalog)
    print(json.dumps({"backup_id": result.backup_id, "ok": result.ok, "problems": result.problems}))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
