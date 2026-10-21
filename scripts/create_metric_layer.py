#!/usr/bin/env python3
"""Build the PulseIQ metric catalog from the official metric dictionary."""

import csv
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "05_Starter" / "pulseiq.duckdb"
DICTIONARY = ROOT / "03_Data" / "csv" / "metric_dictionary.csv"

def main():
    if not DB.exists():
        raise FileNotFoundError(f"DuckDB database not found: {DB}")
    if not DICTIONARY.exists():
        raise FileNotFoundError(f"Metric dictionary not found: {DICTIONARY}")

    with DICTIONARY.open(newline="", encoding="utf-8-sig") as f:
        metrics = list(csv.DictReader(f))

    expected = {f"M{i:02d}" for i in range(1, 29)}
    found = {m["metric_id"] for m in metrics}
    if found != expected or len(metrics) != 28:
        raise ValueError(
            f"Expected exactly M01-M28; found {len(metrics)} rows: "
            f"missing={sorted(expected-found)}, unexpected={sorted(found-expected)}"
        )

    con = duckdb.connect(str(DB))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS metrics")
        for name in ("v_metric_catalog", "metric_catalog", "metric_catalog_data"):
            obj = con.execute("""
                SELECT table_type
                FROM information_schema.tables
                WHERE table_schema = 'metrics' AND table_name = ?
            """, [name]).fetchone()
            if obj:
                kind = "VIEW" if obj[0] == "VIEW" else "TABLE"
                con.execute(f"DROP {kind} metrics.{name}")

        con.execute("""
            CREATE TABLE metrics.metric_catalog_data (
                metric_id VARCHAR PRIMARY KEY,
                metric_name VARCHAR NOT NULL,
                business_definition VARCHAR,
                formula VARCHAR,
                source_table VARCHAR,
                grain VARCHAR,
                time_period VARCHAR,
                owner_team VARCHAR,
                unit VARCHAR,
                good_direction VARCHAR,
                caveat VARCHAR,
                minimum_group_size VARCHAR,
                threshold_status VARCHAR NOT NULL
            )
        """)

        values = []
        for m in metrics:
            threshold = (m.get("minimum_group_size") or "").strip()
            values.append((
                m["metric_id"], m["metric_name"],
                m["business_definition"], m["formula"],
                m["source_table"], m["grain"], m["time_period"],
                m["owner_team"], m["unit"], m["good_direction"],
                m["caveat"], threshold or None,
                "DEFINED" if threshold else "REVIEW_REQUIRED",
            ))

        con.executemany("""
            INSERT INTO metrics.metric_catalog_data VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, values)

        con.execute("""
            CREATE VIEW metrics.metric_catalog AS
            SELECT * FROM metrics.metric_catalog_data
        """)
        con.execute("""
            CREATE VIEW metrics.v_metric_catalog AS
            SELECT * FROM metrics.metric_catalog
        """)

        count = con.execute(
            "SELECT COUNT(*) FROM metrics.metric_catalog"
        ).fetchone()[0]
        unresolved = con.execute("""
            SELECT metric_id, metric_name
            FROM metrics.metric_catalog
            WHERE threshold_status = 'REVIEW_REQUIRED'
            ORDER BY metric_id
        """).fetchall()

        print(f"Metric catalog created: {count} metrics")
        print("Metrics with undefined privacy thresholds:")
        for metric_id, name in unresolved:
            print(f"  {metric_id}: {name}")
        print("Catalog view: metrics.v_metric_catalog")

    finally:
        con.close()

if __name__ == "__main__":
    main()
