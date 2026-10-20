#!/usr/bin/env python3
"""Test DQ SQL rules using isolated temporary tables and rollback."""

import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
CHECK_DIR = ROOT / "sql" / "dq_checks"

# Each test replaces the referenced warehouse table with a temporary table
# containing controlled rows. No permanent warehouse data is changed.
TESTS = {
    "DQ-C01": {
        "setup": """
            CREATE TEMP TABLE fact_payroll (
                period_end_date date, employer_cost numeric
            );
            CREATE TEMP TABLE fact_ledger (
                posting_period text, debit numeric, account_code integer
            );
            INSERT INTO fact_payroll VALUES ('2026-01-31', 100);
            INSERT INTO fact_ledger VALUES ('2026-01', 90, 5001);
        """,
        "sql": """
            WITH payroll AS (
                SELECT TO_CHAR(period_end_date, 'YYYY-MM') AS month,
                       SUM(employer_cost) AS payroll_cost
                FROM fact_payroll GROUP BY 1
            ),
            ledger AS (
                SELECT posting_period AS month, SUM(debit) AS ledger_cost
                FROM fact_ledger
                WHERE account_code BETWEEN 5001 AND 5005 GROUP BY 1
            )
            SELECT p.month
            FROM payroll p LEFT JOIN ledger l USING (month)
            WHERE ABS(p.payroll_cost - COALESCE(l.ledger_cost, 0)) > 0.01
        """,
    },
    "DQ-C02": {
        "setup": """
            CREATE TEMP TABLE fact_ledger (
                entry_id text, debit numeric, credit numeric
            );
            INSERT INTO fact_ledger VALUES ('BAD-1', 100, 90);
        """,
        "sql": """
            SELECT entry_id FROM fact_ledger GROUP BY entry_id
            HAVING ABS(SUM(debit) - SUM(credit)) > 0.005
        """,
    },
    "DQ-C03": {
        "setup": """
            CREATE TEMP TABLE fact_payroll (employee_id text, run_id text);
            INSERT INTO fact_payroll VALUES ('EMP-1', 'RUN-1'), ('EMP-1', 'RUN-1');
        """,
        "sql": """
            SELECT employee_id, run_id FROM fact_payroll
            GROUP BY employee_id, run_id HAVING COUNT(*) > 1
        """,
    },
    "DQ-C04": {
        "setup": """
            CREATE TEMP TABLE fact_payroll (
                payroll_item_id text, employee_id text, employee_key integer
            );
            CREATE TEMP TABLE dim_employee (employee_key integer, employee_id text);
            INSERT INTO fact_payroll VALUES ('PAY-1', 'EMP-MISSING', 999);
        """,
        "sql": """
            SELECT f.payroll_item_id FROM fact_payroll f
            WHERE f.employee_key <> -1
              AND NOT EXISTS (
                SELECT 1 FROM dim_employee d
                WHERE d.employee_key = f.employee_key
                  AND d.employee_id = f.employee_id
              )
        """,
    },
    "DQ-C05": {
        "setup": """
            CREATE TEMP TABLE fact_attendance_monthly (
                attendance_fact_id integer, employee_id text,
                period_end_date date, employee_key integer
            );
            CREATE TEMP TABLE dim_employee (
                employee_key integer, exit_date date
            );
            INSERT INTO dim_employee VALUES (1, '2026-01-15');
            INSERT INTO fact_attendance_monthly
            VALUES (1, 'EMP-1', '2026-02-28', 1);
        """,
        "sql": """
            SELECT a.attendance_fact_id
            FROM fact_attendance_monthly a
            JOIN dim_employee d ON d.employee_key = a.employee_key
            WHERE d.exit_date IS NOT NULL
              AND a.period_end_date >
                  (date_trunc('month', d.exit_date) + interval '1 month - 1 day')::date
        """,
    },
    "DQ-C06": {
        "setup": """
            CREATE TEMP TABLE fact_attendance_monthly (
                employee_id text, period_end_date date, unpaid_absence_days numeric
            );
            CREATE TEMP TABLE fact_payroll (
                employee_id text, period_end_date date, lop_days numeric
            );
            INSERT INTO fact_attendance_monthly VALUES ('EMP-1', '2026-01-31', 3);
            INSERT INTO fact_payroll VALUES ('EMP-1', '2026-01-31', 1);
        """,
        "sql": """
            WITH a AS (
                SELECT employee_id, period_end_date,
                       SUM(unpaid_absence_days) unpaid_days
                FROM fact_attendance_monthly GROUP BY 1,2
            ),
            p AS (
                SELECT employee_id, period_end_date, SUM(lop_days) lop_days
                FROM fact_payroll GROUP BY 1,2
            )
            SELECT a.employee_id FROM a LEFT JOIN p USING (employee_id, period_end_date)
            WHERE a.unpaid_days > 0 AND COALESCE(p.lop_days, 0) + 0.5 < a.unpaid_days
        """,
    },
    "DQ-C07": {
        "setup": """
            CREATE TEMP TABLE fact_invoice (
                invoice_id text, amount_paid numeric, total_amount numeric,
                balance_due numeric
            );
            INSERT INTO fact_invoice VALUES ('INV-BAD', 120, 100, -20);
        """,
        "sql": """
            SELECT invoice_id FROM fact_invoice
            WHERE amount_paid > total_amount + 0.01 OR balance_due < -0.01
        """,
    },
    "DQ-C08": {
        "setup": """
            CREATE TEMP TABLE fact_expense (
                expense_id text, amount_excl_gst numeric, gst_amount numeric,
                total_amount numeric
            );
            INSERT INTO fact_expense VALUES ('EXP-BAD', 100, 18, 130);
        """,
        "sql": """
            SELECT expense_id FROM fact_expense
            WHERE ABS(total_amount - (amount_excl_gst + gst_amount)) > 0.01
        """,
    },
    "DQ-C09": {
        "setup": """
            CREATE TEMP TABLE fact_task (
                task_id text, started_date date, completed_date date, status text
            );
            INSERT INTO fact_task VALUES ('TASK-BAD', '2026-02-10', '2026-02-01', 'Done');
        """,
        "sql": """
            SELECT task_id FROM fact_task
            WHERE completed_date < started_date
               OR (status = 'Done' AND completed_date IS NULL)
        """,
    },
    "DQ-C10": {
        "setup": """
            CREATE TEMP TABLE fact_leave (
                leave_request_id text, start_date date, end_date date
            );
            INSERT INTO fact_leave VALUES ('LEAVE-BAD', '2026-02-10', '2026-02-01');
        """,
        "sql": """
            SELECT leave_request_id FROM fact_leave WHERE end_date < start_date
        """,
    },
    "DQ-C11": {
        "setup": """
            CREATE TEMP TABLE fact_attrition_risk (
                prediction_id text, as_of_date date
            );
            INSERT INTO fact_attrition_risk VALUES
                ('P-OLD', '2026-01-01'), ('P-NEW', '2026-01-20');
        """,
        "sql": """
            SELECT prediction_id FROM fact_attrition_risk
            WHERE as_of_date < (SELECT MAX(as_of_date) FROM fact_attrition_risk) - 7
        """,
    },
    "DQ-C12": {
        "setup": """
            CREATE TEMP TABLE dim_employee (
                employee_id text, employee_key integer, valid_from date, valid_to date
            );
            INSERT INTO dim_employee VALUES
                ('EMP-1', 1, '2026-01-01', '2026-01-20'),
                ('EMP-1', 2, '2026-01-15', '2026-02-01');
        """,
        "sql": """
            SELECT a.employee_id FROM dim_employee a JOIN dim_employee b
              ON a.employee_id = b.employee_id
             AND a.employee_key < b.employee_key
             AND a.valid_from <= b.valid_to
             AND b.valid_from <= a.valid_to
        """,
    },
    "DQ-C13": {
        "setup": """
            CREATE TEMP TABLE etl_run_log (
                finished_at timestamptz, status text
            );
            INSERT INTO etl_run_log
            VALUES (NOW() - INTERVAL '48 hours', 'SUCCESS');
        """,
        "sql": """
            SELECT finished_at FROM etl_run_log
            WHERE status = 'SUCCESS' AND finished_at < NOW() - INTERVAL '24 hours'
        """,
    },
}

def main():
    if not os.getenv("PGPASSWORD"):
        print("PGPASSWORD is not set; use the secure password prompt.")
        return 2

    passed = failed = 0
    with psycopg.connect(
        host="127.0.0.1", dbname="pulseiq_analytics",
        user="pulseiq_user", connect_timeout=10
    ) as conn:
        for check_id, test in TESTS.items():
            try:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(test["setup"])
                        cur.execute(test["sql"])
                        rows = cur.fetchall()
                        if not rows:
                            raise AssertionError("Bad test row was not detected")
                        print(f"PASS {check_id}: detected deliberately bad test data ({len(rows)} row(s))")
                        passed += 1
                        # Force rollback so the temporary test data never persists.
                        raise RuntimeError("ROLLBACK_TEST_TRANSACTION")
            except RuntimeError as exc:
                if str(exc) != "ROLLBACK_TEST_TRANSACTION":
                    print(f"FAIL {check_id}: {exc}")
                    failed += 1
            except Exception as exc:
                print(f"FAIL {check_id}: {type(exc).__name__}: {exc}")
                failed += 1

    print(f"\nBad-row detection tests: {passed} passed, {failed} failed")
    print("Note: C13 is tested against an isolated stale-run example; the production check still needs a real ETL run log.")
    print("Note: C14 is covered by src/privacy_gate.py unit tests, not SQL.")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
