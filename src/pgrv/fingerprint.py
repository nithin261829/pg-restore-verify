"""Content fingerprints for every user table.

The fingerprint of a table is its row count plus an md5 over its rows in a fixed order,
so two databases match only if every table holds the same rows.
"""
from psycopg import sql

USER_TABLES = """
    SELECT n.nspname, c.relname
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind IN ('r', 'p')
      AND n.nspname NOT IN ('pg_catalog', 'information_schema')
      AND n.nspname NOT LIKE 'pg_toast%'
    ORDER BY 1, 2
"""


def table_fingerprints(conn) -> dict[str, dict]:
    """Return {"schema.table": {"rows": n, "md5": hex}} using the connection's current snapshot."""
    out = {}
    with conn.cursor() as cur:
        cur.execute(USER_TABLES)
        tables = cur.fetchall()
        for schema, table in tables:
            ident = sql.Identifier(schema, table)
            cur.execute(
                sql.SQL(
                    "SELECT count(*), coalesce(md5(string_agg(t::text, '|' ORDER BY t::text COLLATE \"C\")), '') FROM {} t"
                ).format(ident)
            )
            rows, digest = cur.fetchone()
            out[f"{schema}.{table}"] = {"rows": rows, "md5": digest}
    return out


def diff(expected: dict, actual: dict) -> list[str]:
    """Human-readable differences between two fingerprint maps; empty means they match."""
    problems = []
    for name in sorted(set(expected) | set(actual)):
        if name not in actual:
            problems.append(f"{name}: missing after restore")
        elif name not in expected:
            problems.append(f"{name}: unexpected table after restore")
        elif expected[name] != actual[name]:
            e, a = expected[name], actual[name]
            problems.append(f"{name}: rows {e['rows']} -> {a['rows']}, md5 {e['md5'][:8]} -> {a['md5'][:8]}")
    return problems
