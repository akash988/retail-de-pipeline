"""Load gold Parquet into a DuckDB warehouse file and (re)create reporting views.

Run:  python -m warehouse.load
"""
import logging
from pathlib import Path

import duckdb

from ingestion import config

log = logging.getLogger("warehouse")

TABLES = ["dim_date", "dim_city", "dim_product", "dim_customer",
          "fact_orders", "daily_sales_summary"]


def split_sql(text: str) -> list[str]:
    """Split a SQL file into statements, skipping comment-only chunks."""
    stmts = []
    for chunk in text.split(";"):
        lines = [l for l in chunk.splitlines()
                 if l.strip() and not l.strip().startswith("--")]
        if lines:
            stmts.append(chunk.strip())
    return stmts


def load_warehouse(gold: Path, db_path: Path, views_file: Path) -> dict:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    counts = {}
    try:
        con.execute("BEGIN")
        # drop views first so tables can be replaced cleanly
        for (name,) in con.execute(
                "SELECT view_name FROM duckdb_views() WHERE NOT internal").fetchall():
            con.execute(f"DROP VIEW IF EXISTS {name}")

        for t in TABLES:
            src = (gold / t / f"{t}.parquet").as_posix()
            con.execute(f"CREATE OR REPLACE TABLE {t} AS SELECT * FROM read_parquet('{src}')")
            loaded = con.execute(f"SELECT count(*) FROM {t}").fetchall()[0][0]
            expected = con.execute(f"SELECT count(*) FROM read_parquet('{src}')").fetchall()[0][0]
            if loaded != expected:
                raise RuntimeError(f"Row count mismatch for {t}: {loaded} vs {expected}")
            counts[t] = loaded
            log.info("Warehouse: %-20s %6d rows", t, loaded)

        for stmt in split_sql(views_file.read_text(encoding="utf-8")):
            con.execute(stmt)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    return counts


def main() -> None:
    config.LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(config.LOG_DIR / "warehouse.log"),
                  logging.StreamHandler()],
    )
    log.info("=== Warehouse load started ===")
    load_warehouse(config.GOLD, config.SERVING_DB, config.SQL_DIR / "views.sql")
    log.info("=== Warehouse load finished: %s ===", config.SERVING_DB)


if __name__ == "__main__":
    main()