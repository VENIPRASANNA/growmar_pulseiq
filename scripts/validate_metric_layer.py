#!/usr/bin/env python3
"""Validate PulseIQ metric views, privacy, catalog, and hand-calculated results."""

from pathlib import Path
import math
import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "05_Starter" / "pulseiq.duckdb"

METRIC_VIEWS = [
    "m01_headcount", "m02_hires", "m03_exits",
    "m04_attrition_monthly", "m05_attrition_rolling_12m",
    "m06_voluntary_attrition_rate", "m07_gross_pay",
    "m08_net_pay", "m09_payroll_employer_cost",
    "m10_cost_per_head", "m11_overtime_share",
    "m12_variable_pay_share", "m13_attendance_rate",
    "m14_late_arrival_rate", "m15_leave_without_pay_days",
    "m16_revenue", "m17_net_profit", "m18_operating_margin",
    "m19_payroll_pct_revenue", "m20_dso",
    "m21_overdue_receivables_internal",
    "m22_task_completion_rate", "m23_on_time_delivery_rate",
    "m24_velocity", "m25_average_cycle_time",
    "m26_anomaly_flag_rate", "m27_high_risk_share",
    "m28_forecast_error_mape",
]

passed = 0
failed = 0

def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS: {label}" + (f" — {detail}" if detail else ""))
    else:
        failed += 1
        print(f"FAIL: {label}" + (f" — {detail}" if detail else ""))

def close_enough(a, b, tolerance=0.02):
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(float(a), float(b), rel_tol=1e-7, abs_tol=tolerance)

def first_row(con, sql):
    return con.execute(sql).fetchone()

def main():
    global passed, failed
    con = duckdb.connect(str(DB), read_only=True)
    try:
        print("=== METRIC LAYER VALIDATION ===")

        existing = {
            r[0] for r in con.execute("""
                SELECT table_name
                FROM information_schema.views
                WHERE table_schema = 'metrics'
            """).fetchall()
        }
        missing = sorted(set(METRIC_VIEWS) - existing)
        check("All 28 metric views exist", not missing,
              f"missing={missing}" if missing else "M01-M28 present")

        catalog_count = con.execute("""
            SELECT COUNT(*) FROM metrics.v_metric_catalog
        """).fetchone()[0]
        check("Catalog contains 28 definitions", catalog_count == 28,
              f"rows={catalog_count}")

        catalog_ids = {
            r[0] for r in con.execute("""
                SELECT metric_id FROM metrics.v_metric_catalog
            """).fetchall()
        }
        expected_ids = {f"M{i:02d}" for i in range(1, 29)}
        check("Catalog contains M01-M28 exactly",
              catalog_ids == expected_ids)

        unresolved = con.execute("""
            SELECT COUNT(*) FROM metrics.v_metric_catalog
            WHERE threshold_status = 'REVIEW_REQUIRED'
        """).fetchone()[0]
        check("Missing thresholds explicitly flagged",
              unresolved == 9, f"review_required={unresolved}")

        # Privacy: no published payroll view should expose employee identifiers.
        payroll_views = [
            "m07_gross_pay", "m08_net_pay", "m09_payroll_employer_cost",
            "m10_cost_per_head", "m11_overtime_share",
            "m12_variable_pay_share", "m15_leave_without_pay_days",
        ]
        privacy_ok = True
        for view in payroll_views:
            columns = {
                r[0] for r in con.execute(
                    f"DESCRIBE metrics.{view}"
                ).fetchall()
            }
            if "employee_id" in columns:
                privacy_ok = False
        check("Published payroll views hide employee identifiers",
              privacy_ok)

        risk_columns = {
            r[0] for r in con.execute(
                "DESCRIBE metrics.m27_high_risk_share"
            ).fetchall()
        }
        check("High-risk view does not expose named employees",
              "employee_id" not in risk_columns)

        small_hr_groups = con.execute("""
            SELECT COUNT(*) FROM metrics.m04_attrition_monthly
            WHERE group_size < 10
        """).fetchone()[0]
        check("Monthly attrition suppresses groups below 10",
              small_hr_groups == 0, f"undersized_rows={small_hr_groups}")

        small_pay_groups = con.execute("""
            SELECT COUNT(*) FROM metrics.m07_gross_pay
            WHERE group_size < 5
        """).fetchone()[0]
        check("Gross pay suppresses groups below 5",
              small_pay_groups == 0, f"undersized_rows={small_pay_groups}")

        # Hand-check 1: headcount equals the source fact for an eligible row.
        row = first_row(con, """
            SELECT v.month_start_date, v.department_id, v.headcount,
                   h.headcount_end
            FROM metrics.m01_headcount v
            JOIN raw.fact_headcount_monthly h
              USING (month_start_date, department_id)
            ORDER BY v.month_start_date, v.department_id
            LIMIT 1
        """)
        check("Hand-check 1: headcount matches source",
              row is not None and row[2] == row[3],
              str(row) if row else "no eligible row")

        # Hand-check 2: monthly attrition = exits / starting headcount * 100.
        row = first_row(con, """
            SELECT attrition_rate_pct,
                   ROUND(100.0 * exits / NULLIF(headcount_start, 0), 2)
            FROM metrics.m04_attrition_monthly
            WHERE headcount_start > 0
            ORDER BY month_start_date, department_id
            LIMIT 1
        """)
        check("Hand-check 2: monthly attrition formula",
              row is not None and close_enough(row[0], row[1]),
              str(row) if row else "no eligible row")

        # Hand-check 3: gross pay excludes only the two identified injected IDs.
        row = first_row(con, """
            SELECT v.gross_pay,
                   ROUND(SUM(p.gross_pay), 2)
            FROM metrics.m07_gross_pay v
            JOIN raw.dim_date d
              ON d.month_start_date = v.month_start_date
            JOIN raw.fact_payroll p
              ON p.date_key = d.date_key
             AND p.department_id = v.department_id
             AND p.payroll_item_id NOT IN ('PI-X0001', 'PI-X0002')
            GROUP BY v.month_start_date, v.department_id, v.gross_pay
            ORDER BY v.month_start_date, v.department_id
            LIMIT 1
        """)
        check("Hand-check 3: gross pay excludes known duplicates",
              row is not None and close_enough(row[0], row[1]),
              str(row) if row else "no eligible row")

        # Hand-check 4: attendance formula matches the raw aggregation.
        row = first_row(con, """
            SELECT v.attendance_rate_pct,
                   ROUND(100.0 * (
                       SUM(a.present_days) + 0.5 * SUM(a.half_days_unpaid)
                   ) / NULLIF(SUM(a.scheduled_days), 0), 2)
            FROM metrics.m13_attendance_rate v
            JOIN raw.dim_date d
              ON d.month_start_date = v.month_start_date
            JOIN raw.fact_attendance_monthly a
              ON a.date_key = d.date_key
             AND a.department_id = v.department_id
            GROUP BY v.month_start_date, v.department_id,
                     v.attendance_rate_pct
            ORDER BY v.month_start_date, v.department_id
            LIMIT 1
        """)
        check("Hand-check 4: attendance formula",
              row is not None and close_enough(row[0], row[1]),
              str(row) if row else "no eligible row")

        # Hand-check 5: revenue uses only ledger accounts 4001-4004.
        row = first_row(con, """
            SELECT v.revenue,
                   ROUND(-SUM(l.signed_amount_debit_positive), 2)
            FROM metrics.m16_revenue v
            JOIN raw.fact_ledger l
              ON DATE_TRUNC('month', l.entry_date)::DATE = v.month_start_date
            WHERE l.account_code IN ('4001', '4002', '4003', '4004')
            GROUP BY v.month_start_date, v.revenue
            ORDER BY v.month_start_date
            LIMIT 1
        """)
        check("Hand-check 5: revenue account scope",
              row is not None and close_enough(row[0], row[1]),
              str(row) if row else "no eligible row")

        # Known source limitations: these are explicit outcomes, not fabricated values.
        anomaly_rows = con.execute("""
            SELECT COUNT(*) FROM metrics.m26_anomaly_flag_rate
        """).fetchone()[0]
        check("M26 stays unavailable for incomplete scored population",
              anomaly_rows == 0, f"rows={anomaly_rows}")

        mape_rows = con.execute("""
            SELECT COUNT(*) FROM metrics.m28_forecast_error_mape
        """).fetchone()[0]
        check("M28 only scores matching actual forecast months",
              mape_rows == 0, f"scored_rows={mape_rows}")

        print("\n=== ROW COUNTS ===")
        for view in METRIC_VIEWS:
            count = con.execute(
                f"SELECT COUNT(*) FROM metrics.{view}"
            ).fetchone()[0]
            print(f"{view}: {count}")

        print(f"\nRESULT: {passed} passed, {failed} failed")
        if failed:
            raise SystemExit(1)
    finally:
        con.close()

if __name__ == "__main__":
    main()
