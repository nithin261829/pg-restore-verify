import os
import shutil
import uuid

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from pgrv.catalog import Catalog
from pgrv.config import Config

SOURCE_ADMIN = os.environ.get("PGRV_TEST_SOURCE_ADMIN", "postgresql://postgres:postgres@localhost:5432/postgres")
SCRATCH = os.environ.get("PGRV_TEST_SCRATCH", "postgresql://postgres:postgres@localhost:5433/postgres")


def _reachable(dsn: str) -> bool:
    try:
        psycopg.connect(dsn, connect_timeout=3).close()
        return True
    except psycopg.OperationalError:
        return False


needs_pg = pytest.mark.skipif(
    not (shutil.which("pg_dump") and _reachable(SOURCE_ADMIN) and _reachable(SCRATCH)),
    reason="needs pg_dump/pg_restore and two PostgreSQL servers",
)

SEED = """
CREATE TABLE customers (id serial PRIMARY KEY, name text NOT NULL, tier text, created_at timestamptz DEFAULT now());
CREATE TABLE orders (id bigserial PRIMARY KEY, customer_id int REFERENCES customers(id), amount numeric(12,2),
                     meta jsonb, placed_at timestamptz NOT NULL);
CREATE INDEX orders_customer_idx ON orders (customer_id);
INSERT INTO customers (name, tier) SELECT 'customer ' || g, (ARRAY['gold','silver',NULL])[1 + g % 3]
  FROM generate_series(1, 500) g;
INSERT INTO orders (customer_id, amount, meta, placed_at)
  SELECT 1 + g % 500, round((g * 7.31)::numeric % 5000, 2), jsonb_build_object('n', g, 'note', 'café ' || g),
         timestamptz '2026-01-01' + g * interval '17 minutes'
  FROM generate_series(1, 5000) g;
"""


@pytest.fixture
def source_db():
    name = f"pgrv_src_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(SOURCE_ADMIN, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(SOURCE_ADMIN, dbname=name)
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(SEED)
    yield dsn
    with psycopg.connect(SOURCE_ADMIN, autocommit=True) as admin:
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def cfg(source_db, tmp_path):
    return Config(source_dsn=source_db, scratch_dsn=SCRATCH, store=f"file://{tmp_path}/store",
                  catalog_path=str(tmp_path / "catalog.db"), retention=2)


@pytest.fixture
def catalog(cfg):
    return Catalog(cfg.catalog_path)
