import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    source_dsn: str
    scratch_dsn: str
    store: str
    catalog_path: str
    retention: int

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            source_dsn=os.environ.get("PGRV_SOURCE_DSN", "postgresql://postgres:postgres@localhost:5432/app"),
            scratch_dsn=os.environ.get("PGRV_SCRATCH_DSN", "postgresql://postgres:postgres@localhost:5433/postgres"),
            store=os.environ.get("PGRV_STORE", "file://./backups"),
            catalog_path=os.environ.get("PGRV_CATALOG", "catalog.db"),
            retention=int(os.environ.get("PGRV_RETENTION", "7")),
        )
