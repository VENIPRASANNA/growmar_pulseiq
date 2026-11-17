
#!/usr/bin/env python3
"""
PulseIQ Task 17: Export privacy-reviewed aggregate datasets
for Streamlit Community Cloud.

The local DuckDB warehouse remains unchanged.
Only approved aggregate datasets are exported.
"""

from pathlib import Path
import json
import shutil
import tempfile
from datetime import datetime, timezone

import duckdb
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "05_Starter" / "pulseiq.duckdb"
OUTPUT_DIR = ROOT / "data" / "hosted"

MIN_GROUP_SIZE = 10

# Column names that must never appear in public datasets.
FORBIDDEN_COLUMNS = {
    "employee_id",
    "employee_key",
    "full_name",
    "manager_id",
    "client_id",
    "client_name",
    "vendor_id",
    "vendor_name",
    "invoice_id",
    "invoice_number",
    "payment_id",
    "transaction_id",
    "payroll_item_id",
    "task_id",
    "assignee_employee_id",
    "prediction_id",
    "record_id",
    "result_id",
    "reason_text",
    "contact_email",
    "gst_registration",
    "bill_reference",
    "reference_no",
    "source_id",
}


EXPORT_QUERIES = {

    # 1. Workforce headcount by month and department.
    "workforce_monthly": """
        SELECT
            month_start_date,
            department_id,
            department_name,
            headcount,
            group_size
        FROM metrics.m29_department_headcount
        WHERE group_size >= 10
    """,

    # 2. Company-wide quarterly workforce movements.
    # Department-level movements are excluded for privacy.
    # Publish only complete quarters with at least 10 hires and 10 exits.
    "workforce_movements_quarterly": """
        SELECT
            DATE_TRUNC('quarter', month_start_date)::DATE AS quarter,
            SUM(hires) AS hires,
            SUM(exits) AS exits,
            SUM(hires) - SUM(exits) AS net_movement
        FROM raw.fact_headcount_monthly
        WHERE department_id != 'D00'
          AND month_start_date >= DATE '2025-04-01'
          AND month_start_date < DATE '2026-10-01'
        GROUP BY DATE_TRUNC('quarter', month_start_date)
        HAVING COUNT(DISTINCT month_start_date) = 3
           AND SUM(hires) >= 10
           AND SUM(exits) >= 10
        ORDER BY quarter
    """,

    # 3. Company-wide rolling 12-month attrition.
    # Publish rates only; exact counts and department breakdowns stay private.
    "attrition_rolling_12m": """
        WITH monthly AS (
            SELECT
                month_start_date,
                SUM(exits) AS exits,
                SUM(voluntary_exits) AS voluntary_exits,
                SUM(headcount_end) AS headcount_end
            FROM raw.fact_headcount_monthly
            WHERE department_id != 'D00'
            GROUP BY month_start_date
        ),
        rolling AS (
            SELECT
                month_start_date,
                SUM(exits) OVER (
                    ORDER BY month_start_date
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
                ) AS exits_12m,
                SUM(voluntary_exits) OVER (
                    ORDER BY month_start_date
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
                ) AS voluntary_exits_12m,
                AVG(headcount_end) OVER (
                    ORDER BY month_start_date
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
                ) AS avg_headcount_12m,
                COUNT(*) OVER (
                    ORDER BY month_start_date
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
                ) AS months_in_window
            FROM monthly
        )
        SELECT
            month_start_date,
            ROUND(
                100.0 * exits_12m / NULLIF(avg_headcount_12m, 0),
                2
            ) AS attrition_rate_12m_pct,
            ROUND(
                100.0 * voluntary_exits_12m / NULLIF(avg_headcount_12m, 0),
                2
            ) AS voluntary_attrition_rate_12m_pct
        FROM rolling
        WHERE months_in_window = 12
          AND exits_12m >= 10
          AND voluntary_exits_12m >= 10
          AND EXTRACT(MONTH FROM month_start_date) = 9
        ORDER BY month_start_date
    """,

    # 4. Payroll aggregates.
    "payroll_monthly": """
        SELECT
            g.month_start_date,
            g.department_id,
            d.department_name,
            g.gross_pay,
            n.net_pay,
            c.employer_cost,
            h.cost_per_head,
            o.overtime_share_pct,
            v.variable_pay_share_pct,
            g.employee_count
        FROM metrics.m07_gross_pay g
        JOIN metrics.m08_net_pay n
          USING (month_start_date, department_id)
        JOIN metrics.m09_payroll_employer_cost c
          USING (month_start_date, department_id)
        JOIN metrics.m10_cost_per_head h
          USING (month_start_date, department_id)
        JOIN metrics.m11_overtime_share o
          USING (month_start_date, department_id)
        JOIN metrics.m12_variable_pay_share v
          USING (month_start_date, department_id)
        JOIN raw.dim_department d
          USING (department_id)
        WHERE g.group_size >= 10
          AND n.group_size >= 10
          AND c.group_size >= 10
          AND h.group_size >= 10
          AND o.group_size >= 10
          AND v.group_size >= 10
    """,

    # 4B. Company-wide payroll aggregates.
    "payroll_company_monthly": """
        SELECT
            d.month_start_date,
            SUM(p.gross_pay) AS gross_pay,
            SUM(p.net_pay) AS net_pay,
            SUM(p.employer_cost) AS employer_cost,
            COUNT(DISTINCT p.employee_id) AS employee_count
        FROM metrics.v_payroll_clean p
        JOIN raw.dim_date d
          USING (date_key)
        GROUP BY d.month_start_date
        ORDER BY d.month_start_date
    """,

    # 5. Attendance and late-arrival aggregates.
    # Unpaid leave days are excluded from public exports.
    "attendance_monthly": """
        SELECT
            a.month_start_date,
            a.department_id,
            d.department_name,
            a.attendance_rate_pct,
            l.late_arrivals_per_100_present_days,
            a.employee_count
        FROM metrics.m13_attendance_rate a
        JOIN metrics.m14_late_arrival_rate l
          USING (month_start_date, department_id)
        JOIN raw.dim_department d
          USING (department_id)
        WHERE a.group_size >= 10
          AND l.group_size >= 10
    """,

    # 6. Team productivity by sprint.
    "productivity_sprint": """

        SELECT
            c.team_id,
            t.team_name,
            c.sprint_id,
            s.sprint_name,
            s.start_date,
            s.end_date,
            c.completed_tasks,
            c.eligible_tasks,
            c.task_completion_rate_pct,
            o.completed_on_time_tasks,
            o.on_time_delivery_rate_pct,
            v.completed_story_points,
            y.average_cycle_time_days,
            c.group_size
        FROM metrics.m22_task_completion_rate c
        JOIN metrics.m23_on_time_delivery_rate o
          USING (team_id, sprint_id)
        JOIN metrics.m24_velocity v
          USING (team_id, sprint_id)
        JOIN metrics.m25_average_cycle_time y
          USING (team_id, sprint_id)
        JOIN raw.dim_team t
          USING (team_id)
        JOIN raw.dim_sprint s
          USING (sprint_id)
        WHERE c.group_size >= 10
          AND o.group_size >= 10
          AND v.group_size >= 10
          AND y.group_size >= 10
          AND (c.completed_tasks = 0 OR c.completed_tasks >= 10)
          AND (o.completed_on_time_tasks = 0 OR o.completed_on_time_tasks >= 10)
          AND (y.valid_completed_tasks = 0 OR y.valid_completed_tasks >= 10)
    """,

    # 7. Company-level financial performance.
    "finance_monthly": """
        SELECT
            r.month_start_date,
            r.revenue,
            p.net_profit,
            m.operating_margin_pct,
            l.payroll_cost_ledger,
            l.payroll_pct_revenue
        FROM metrics.m16_revenue r
        JOIN metrics.m17_net_profit p
          USING (month_start_date)
        JOIN metrics.m18_operating_margin m
          USING (month_start_date)
        JOIN metrics.m19_payroll_pct_revenue l
          USING (month_start_date)
    """,

    # 8. Company-level receivables and DSO.
    "receivables_summary": """
        SELECT
            report_date,
            closing_receivables,
            credit_sales_90d,
            dso_days
        FROM metrics.m20_dso
    """,

    # 8B. Company-wide receivables ageing.
    # Combine all overdue buckets to avoid exposing small groups.
    "receivables_ageing": """
        SELECT
            CASE
                WHEN days_past_due_at_cutoff > 0 THEN 'Overdue'
                ELSE 'Not yet due'
            END AS ageing_category,
            COUNT(*) AS invoice_count,
            SUM(balance_due) AS outstanding_amount
        FROM raw.fact_invoice
        WHERE status IN ('SENT', 'OVERDUE', 'PARTIALLY_PAID')
          AND balance_due > 0
        GROUP BY 1
        HAVING COUNT(*) >= 10
        ORDER BY ageing_category
    """,

    # 8C. Broad company-wide invoice status.
    # Exclude draft and cancelled invoices.
    "invoice_status_summary": """
        SELECT
            CASE
                WHEN status = 'PAID' THEN 'Paid'
                ELSE 'Open'
            END AS invoice_category,
            COUNT(*) AS invoice_count,
            SUM(total_amount) AS invoice_value,
            SUM(amount_paid) AS total_paid,
            SUM(balance_due) AS outstanding_amount
        FROM raw.fact_invoice
        WHERE status IN (
            'PAID', 'SENT', 'OVERDUE', 'PARTIALLY_PAID'
        )
        GROUP BY 1
        HAVING COUNT(*) >= 10
        ORDER BY invoice_category
    """,

    # 8D. Company-wide monthly cash flow.
    "cashflow_monthly": """
        WITH cash_in AS (
            SELECT
                DATE_TRUNC('month', payment_date)::DATE
                    AS month_start_date,
                SUM(amount) AS cash_inflow
            FROM raw.fact_invoice_payment
            WHERE payment_date IS NOT NULL
            GROUP BY 1
        ),
        cash_out AS (
            SELECT
                DATE_TRUNC('month', paid_date)::DATE
                    AS month_start_date,
                SUM(total_amount) AS cash_outflow
            FROM raw.fact_expense
            WHERE paid_date IS NOT NULL
              AND status = 'PAID'
            GROUP BY 1
        )
        SELECT
            COALESCE(i.month_start_date, o.month_start_date)
                AS month_start_date,
            COALESCE(i.cash_inflow, 0) AS cash_inflow,
            COALESCE(o.cash_outflow, 0) AS cash_outflow,
            COALESCE(i.cash_inflow, 0)
              - COALESCE(o.cash_outflow, 0) AS net_cash_flow
        FROM cash_in i
        FULL OUTER JOIN cash_out o
            ON i.month_start_date = o.month_start_date
        ORDER BY month_start_date
    """,

    # 9. Department workforce distribution.
    "department_distribution": """
        SELECT
            department_id,
            department_name,
            department_headcount,
            total_headcount,
            headcount_share_pct
        FROM metrics.m32_department_headcount_share
        WHERE department_headcount >= 10
    """,

    # 10. Location distribution.
    "location_distribution": """
        SELECT
            city_tier,
            tier_number,
            headcount
        FROM metrics.m30_location_tier_headcount
    """,

    # 11. Work-mode distribution.
    "work_mode_distribution": """
        SELECT
            work_mode,
            headcount
        FROM metrics.m31_work_mode_headcount
    """,

    # 12. Company-wide anomaly summary.
    # Small categories are combined to prevent disclosure.
    "anomaly_summary": f"""
        WITH source AS (
            SELECT *
            FROM read_csv_auto(
                '{(ROOT / "data" / "clean" / "fact_anomaly.csv").as_posix()}'
            )
        ),
        grouped AS (
            SELECT
                CASE
                    WHEN reason_code IN (
                        'GROSS_ABOVE_NORM',
                        'LONG_UNPAID_ABSENCE',
                        'NO_ATTENDANCE',
                        'PATTERN_SHIFT',
                        'STATISTICAL_OUTLIER'
                    )
                    THEN reason_code
                    ELSE 'Other (suppressed categories)'
                END AS anomaly_category,
                COUNT(*) AS flagged_count,
                COUNT(money_at_risk) AS exposure_record_count,
                SUM(COALESCE(money_at_risk, 0)) AS total_exposure,
                AVG(anomaly_score) AS average_anomaly_score
            FROM source
            WHERE flagged = 'Y'
            GROUP BY 1
        )
        SELECT
            anomaly_category,
            flagged_count,
            CASE
                WHEN anomaly_category = 'Other (suppressed categories)'
                  OR exposure_record_count < 10
                THEN NULL
                ELSE exposure_record_count
            END AS exposure_record_count,
            CASE
                WHEN anomaly_category = 'Other (suppressed categories)'
                  OR exposure_record_count < 10
                THEN NULL
                ELSE ROUND(total_exposure, 2)
            END AS total_exposure,
            CASE
                WHEN anomaly_category = 'Other (suppressed categories)'
                  OR exposure_record_count < 10
                THEN NULL
                ELSE ROUND(average_anomaly_score, 3)
            END AS average_anomaly_score
        FROM grouped
        WHERE flagged_count >= 10
        ORDER BY flagged_count DESC
    """,

    # 13. Company-wide forecasts only.
    # Department-level forecasts and forecast identifiers are excluded.
    "forecast_company": f"""
        SELECT
            metric,
            CAST(forecast_month AS DATE) AS forecast_month,
            forecast_value,
            lower_80,
            upper_80,
            method,
            trained_through,
            model_version
        FROM read_csv_auto(
            '{(ROOT / "data" / "clean" / "fact_forecast.csv").as_posix()}'
        )
        WHERE department_id = 'ALL'
        ORDER BY metric, forecast_month
    """,

    # 14. Company-wide attrition risk distribution.
    # No employee, department, individual score or reason is exported.
    "attrition_risk_summary": f"""
        SELECT
            CAST(as_of_date AS DATE) AS as_of_date,
            risk_band,
            COUNT(*) AS prediction_count
        FROM read_csv_auto(
            '{(ROOT / "data" / "clean" / "fact_attrition_risk.csv").as_posix()}'
        )
        GROUP BY 1, 2
        HAVING COUNT(*) >= 10
        ORDER BY risk_band
    """,

    # 15. Company-wide actuals for AI forecast comparison.
    # Monthly aggregates only; no department or employee details.
    "ai_actuals_monthly": """
        SELECT
            month_start_date,
            SUM(headcount_end) AS actual_headcount,
            ROUND(
                100.0 * SUM(exits)
                / NULLIF(SUM(headcount_start), 0),
                2
            ) AS actual_attrition_rate_pct
        FROM raw.fact_headcount_monthly
        WHERE department_id != 'D00'
        GROUP BY month_start_date
        HAVING SUM(headcount_start) >= 10
           AND SUM(headcount_end) >= 10
        ORDER BY month_start_date
    """,

    # Department-level AI attrition is excluded from public exports.
}


def validate_columns(dataset_name, table):
    """Reject datasets containing known sensitive identifiers."""

    columns = {name.lower() for name in table.column_names}
    forbidden = columns.intersection(FORBIDDEN_COLUMNS)

    if forbidden:
        raise ValueError(
            f"{dataset_name}: forbidden columns found: "
            f"{sorted(forbidden)}"
        )


def export_dataset(con, dataset_name, query, output_dir):
    """Run a query, validate its schema, and export Parquet."""

    table = con.execute(query).to_arrow_table()

    validate_columns(dataset_name, table)

    output_path = output_dir / f"{dataset_name}.parquet"

    pq.write_table(
        table,
        output_path,
        compression="zstd"
    )

    return {
        "dataset": dataset_name,
        "rows": table.num_rows,
        "columns": table.column_names,
        "size_bytes": output_path.stat().st_size,
    }


def main():
    if not DB.exists():
        raise FileNotFoundError(f"DuckDB database not found: {DB}")

    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)

    staging_dir = Path(tempfile.mkdtemp(
        prefix=".hosted-staging-",
        dir=OUTPUT_DIR.parent
    ))

    backup_dir = OUTPUT_DIR.with_name(
        f".{OUTPUT_DIR.name}-backup-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    )

    con = None
    published = False

    try:
        con = duckdb.connect(str(DB), read_only=True)
        results = []

        print("======================================")
        print(" PULSEIQ HOSTED DATA EXPORT")
        print("======================================")
        print(f"Minimum group size: {MIN_GROUP_SIZE}")
        print(f"Staging directory: {staging_dir}")
        print()

        # Export every dataset into staging first.
        for name, query in EXPORT_QUERIES.items():
            result = export_dataset(con, name, query, staging_dir)
            results.append(result)

            print(
                f"PASS: {name}.parquet | "
                f"Rows: {result['rows']} | "
                f"Size: {result['size_bytes']:,} bytes"
            )

        # Build manifest only after all datasets succeed.
        manifest = {
            "project": "PulseIQ",
            "exported_at_utc": datetime.now(timezone.utc).isoformat(),
            "minimum_group_size": MIN_GROUP_SIZE,
            "database": "Local DuckDB warehouse",
            "format": "Parquet",
            "datasets": results,
            "total_datasets": len(results),
            "total_rows": sum(item["rows"] for item in results),
            "total_size_bytes": sum(item["size_bytes"] for item in results),
        }

        manifest_path = staging_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, default=str),
            encoding="utf-8"
        )

        # Publish the complete directory in one replacement step.
        if OUTPUT_DIR.exists():
            OUTPUT_DIR.rename(backup_dir)

        try:
            staging_dir.rename(OUTPUT_DIR)
            published = True
        except Exception:
            if backup_dir.exists():
                backup_dir.rename(OUTPUT_DIR)
            raise

        # Remove the previous version only after successful publication.
        if backup_dir.exists():
            shutil.rmtree(backup_dir)

        print()
        print("======================================")
        print(" EXPORT SUMMARY")
        print("======================================")
        print(f"Datasets exported: {len(results)}")
        print(f"Total rows: {manifest['total_rows']}")
        print(f"Total size: {manifest['total_size_bytes']:,} bytes")
        print(f"Manifest: {OUTPUT_DIR / 'manifest.json'}")
        print()
        print("EXPORT COMPLETED SUCCESSFULLY")

    finally:
        if con is not None:
            con.close()

        if staging_dir.exists():
            shutil.rmtree(staging_dir)

        # Keep the backup if publication did not complete.
        if published and backup_dir.exists():
            shutil.rmtree(backup_dir)


if __name__ == "__main__":
    main()
