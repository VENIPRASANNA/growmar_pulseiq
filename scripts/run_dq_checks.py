#!/usr/bin/env python3
"""Run PulseIQ data-quality checks and persist results in public.dq_results."""

import csv
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from privacy_gate import load_thresholds, can_publish

import psycopg

ROOT = Path(__file__).resolve().parents[1]
CHECK_DIR = ROOT / "sql" / "dq_checks"
CATALOG = ROOT / "03_Data" / "csv" / "dq_checks_catalog.csv"

def load_catalog():
    with CATALOG.open(newline="", encoding="utf-8-sig") as f:
        return {r["check_id"]: r for r in csv.DictReader(f)}

def main():
    if not os.getenv("PGPASSWORD"):
        print('Set PGPASSWORD first, or run with: read -rsp "PostgreSQL password: " PGPASSWORD; echo; export PGPASSWORD')
        return 2

    catalog = load_catalog()
    run_id = uuid.uuid4()
    files = sorted(CHECK_DIR.glob("DQ-C*.sql"))
    results = []

    try:
        with psycopg.connect(
            host="127.0.0.1",
            dbname="pulseiq_analytics",
            user="pulseiq_user",
            connect_timeout=10,
        ) as conn:
            with conn.cursor() as cur:
                # Ensure the results table is present; existing table is preserved.
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.dq_results (
                        result_id BIGSERIAL PRIMARY KEY,
                        run_id UUID NOT NULL,
                        check_id TEXT NOT NULL,
                        check_name TEXT NOT NULL,
                        source_table TEXT NOT NULL,
                        bad_rows BIGINT,
                        status TEXT NOT NULL CHECK (status IN ('PASS','FAIL','ERROR')),
                        severity TEXT NOT NULL CHECK (severity IN ('Critical','Warning')),
                        run_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        details TEXT
                    )
                """)

                # Load ETL run history so DQ-C13 can evaluate actual freshness.
                run_log_path = ROOT / "logs" / "etl_run_log.csv"
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.etl_run_log (
                        started_at TIMESTAMPTZ,
                        finished_at TIMESTAMPTZ,
                        status TEXT,
                        error_message TEXT
                    )
                """)
                if run_log_path.exists():
                    with run_log_path.open(newline="", encoding="utf-8") as f:
                        for row in csv.DictReader(f):
                            cur.execute("""
                                INSERT INTO public.etl_run_log
                                    (started_at, finished_at, status, error_message)
                                SELECT %s, %s, %s, %s
                                WHERE NOT EXISTS (
                                    SELECT 1 FROM public.etl_run_log
                                    WHERE started_at = %s AND finished_at = %s
                                )
                            """, (
                                row["started_at"], row["finished_at"],
                                row["status"], row.get("error_message", ""),
                                row["started_at"], row["finished_at"]
                            ))

                for path in files:
                    check_id = path.name.split("_", 1)[0]
                    meta = catalog.get(check_id)
                    if not meta:
                        print(f"SKIP {check_id}: missing from catalog")
                        continue

                    sql = path.read_text(encoding="utf-8")
                    started = time.perf_counter()
                    status, bad_rows, details = "ERROR", None, None

                    try:
                        if check_id == "DQ-C14":
                            thresholds = load_thresholds(
                                ROOT / "03_Data" / "csv" / "metric_dictionary.csv"
                            )
                            assert can_publish("M01", 4, thresholds) is False
                            assert can_publish("M01", 5, thresholds) is True
                            assert can_publish("M22", 4, thresholds) is False
                            try:
                                can_publish("M16", 20, thresholds)
                            except ValueError:
                                pass
                            else:
                                raise AssertionError(
                                    "A metric without a threshold was allowed"
                                )
                            bad_rows = 0
                            status = "PASS"
                            details = (
                                "Privacy policy tests passed. Live reporting queries must "
                                "call can_publish() before releasing metric groups."
                            )
                        else:
                            cur.execute(sql)
                            rows = cur.fetchall()
                            bad_rows = len(rows)
                            status = "PASS" if bad_rows == 0 else "FAIL"

                            if check_id == "DQ-C11":
                                details = (
                                    "As-of-date comparison only; scored_at is absent from "
                                    "fact_attrition_risk, so 24-hour scoring freshness is unverified."
                                )
                            elif check_id == "DQ-C13":
                                details = (
                                    "Latest successful ETL run is checked against the 24-hour limit."
                                )
                    except Exception as exc:
                        conn.rollback()
                        status, bad_rows = "ERROR", None
                        details = f"{type(exc).__name__}: {exc}"
                        # Restore transaction after a failed check.
                        cur.execute("SELECT 1")

                    elapsed = time.perf_counter() - started
                    cur.execute("""
                        INSERT INTO public.dq_results
                            (run_id, check_id, check_name, source_table,
                             bad_rows, status, severity, details)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        str(run_id), check_id, meta["check_name"],
                        meta["logic_sql_or_rule"][:120], bad_rows, status,
                        meta["severity"], details
                    ))
                    results.append((check_id, meta["check_name"], status, bad_rows,
                                    meta["severity"], elapsed, details))

            conn.commit()

    except Exception as exc:
        print(f"Could not connect or persist results: {type(exc).__name__}: {exc}")
        return 2

    print(f"\nPulseIQ DQ run: {run_id}")
    print("-" * 90)
    print(f"{'CHECK':<10} {'SEVERITY':<10} {'STATUS':<8} {'BAD ROWS':>9}  CHECK NAME")
    print("-" * 90)
    for cid, name, status, bad, severity, elapsed, details in results:
        print(f"{cid:<10} {severity:<10} {status:<8} {str(bad):>9}  {name} ({elapsed:.2f}s)")
        if details:
            print(f"    Note: {details}")

    passed = sum(r[2] == "PASS" for r in results)
    failed = sum(r[2] == "FAIL" for r in results)
    errors = sum(r[2] == "ERROR" for r in results)
    print("-" * 90)
    print(f"TOTAL: {len(results)} | PASS: {passed} | FAIL: {failed} | ERROR: {errors}")
    print("Saved results to public.dq_results")

    # Do not return a nonzero exit code just because real data-quality failures were found.
    return 0 if errors == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
