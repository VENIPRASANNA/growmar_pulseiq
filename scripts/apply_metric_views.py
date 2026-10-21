#!/usr/bin/env python3
"""Apply metric-layer SQL views to the PulseIQ DuckDB database."""

from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "05_Starter" / "pulseiq.duckdb"
SQL_FILE = ROOT / "sql" / "metric_views.sql"

def main():
    sql = SQL_FILE.read_text(encoding="utf-8")
    con = duckdb.connect(str(DB))
    try:
        con.execute(sql)
        views = con.execute("""
            SELECT table_name
            FROM information_schema.views
            WHERE table_schema = 'metrics'
            ORDER BY table_name
        """).fetchall()
        print(f"Metric views currently created: {len(views)}")
        for (name,) in views:
            rows = con.execute(f"SELECT COUNT(*) FROM metrics.{name}").fetchone()[0]
            print(f"  {name}: {rows} rows")
    finally:
        con.close()

if __name__ == "__main__":
    main()
