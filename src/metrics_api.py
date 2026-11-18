from pathlib import Path
import csv
import duckdb

from fastapi import FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "05_Starter" / "pulseiq.duckdb"
ETL_LOG = ROOT / "logs" / "etl_run_log.csv"
HOSTED_LOG = ROOT / "logs" / "hosted_refresh.log"

app = FastAPI(
    title="PulseIQ Metrics API",
    description="API for five governed PulseIQ workforce and operational KPIs.",
    version="1.0.0",
)


METRICS = {
    "M01": {
        "name": "Headcount",
        "formula": "Headcount at month end, using headcount_end from the monthly fact",
        "source_table": "raw.fact_headcount_monthly",
        "source_view": "metrics.m01_headcount",
        "grain": "Department x month",
        "unit": "employees",
        "minimum_group_size": 5,
        "value_column": "headcount",
        "dimensions": ["month_start_date", "department_id"],
        "lineage": [
            "raw.fact_headcount_monthly",
            "Filter department_id <> D00 and headcount_end >= 5",
            "metrics.m01_headcount",
            "headcount",
        ],
        "catalog_note": (
            "The metric catalog describes an active-employee distinct-count formula. "
            "The published SQL view uses headcount_end from the monthly fact."
        ),
    },
    "M04": {
        "name": "Monthly Attrition Rate",
        "formula": "Exits / headcount_start x 100",
        "source_table": "raw.fact_headcount_monthly",
        "source_view": "metrics.m04_attrition_monthly",
        "grain": "Department x month",
        "unit": "percent",
        "minimum_group_size": 10,
        "value_column": "attrition_rate_pct",
        "dimensions": ["month_start_date", "department_id"],
        "lineage": [
            "raw.fact_headcount_monthly",
            "Calculate 100 x exits / headcount_start",
            "Apply minimum group size of 10",
            "metrics.m04_attrition_monthly",
            "attrition_rate_pct",
        ],
    },
    "M07": {
        "name": "Gross Pay",
        "formula": "SUM(gross_pay)",
        "source_table": "raw.fact_payroll",
        "source_view": "metrics.m07_gross_pay",
        "grain": "Department x month",
        "unit": "INR",
        "minimum_group_size": 5,
        "value_column": "gross_pay",
        "dimensions": ["month_start_date", "department_id"],
        "lineage": [
            "raw.fact_payroll",
            "metrics.v_payroll_clean",
            "Join dim_date and aggregate SUM(gross_pay) by month and department",
            "Apply minimum employee count of 5",
            "metrics.m07_gross_pay",
            "gross_pay",
        ],
        "catalog_note": (
            "The metric catalog lists Employee x month grain. "
            "The published SQL view is aggregated at Department x month."
        ),
    },
    "M22": {
        "name": "Task Completion Rate",
        "formula": "Completed tasks / eligible tasks x 100",
        "source_table": "raw.fact_task",
        "source_view": "metrics.m22_task_completion_rate",
        "grain": "Team x sprint",
        "unit": "percent",
        "minimum_group_size": 5,
        "value_column": "task_completion_rate_pct",
        "dimensions": ["team_id", "sprint_id"],
        "lineage": [
            "raw.fact_task",
            "Exclude Cancelled tasks from eligible tasks",
            "Count Done tasks and calculate completion percentage",
            "Apply minimum eligible task count of 5",
            "metrics.m22_task_completion_rate",
            "task_completion_rate_pct",
        ],
    },
    "M27": {
        "name": "High-Risk Share",
        "formula": "Distinct high-risk employees / distinct employees scored x 100",
        "source_table": "raw.fact_attrition_risk",
        "source_view": "metrics.m27_high_risk_share",
        "grain": "Department",
        "unit": "percent",
        "minimum_group_size": 10,
        "value_column": "high_risk_share_pct",
        "dimensions": ["department_id"],
        "lineage": [
            "raw.fact_attrition_risk",
            "Count distinct high-risk employees and employees scored",
            "Apply minimum group size of 10",
            "metrics.m27_high_risk_share",
            "high_risk_share_pct",
        ],
    },
}


SOURCE_FRESHNESS = {
    "M01": ("raw.fact_headcount_monthly", "month_start_date"),
    "M04": ("raw.fact_headcount_monthly", "month_start_date"),
    "M07": ("metrics.m07_gross_pay", "month_start_date"),
    "M22": ("raw.fact_task", "completed_date"),
    "M27": ("raw.fact_attrition_risk", "as_of_date"),
}


def get_connection():
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="DuckDB database not found")
    return duckdb.connect(str(DB_PATH), read_only=True)


@app.get("/")
def root():
    return {
        "message": "Welcome to PulseIQ Metrics API",
        "docs": "/docs",
        "available_metrics": list(METRICS.keys()),
    }


@app.get("/health")
def health():
    try:
        con = get_connection()
        con.execute("SELECT 1").fetchone()
        con.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/metrics")
def list_metrics():
    return {
        "count": len(METRICS),
        "metrics": [
            {"metric_id": metric_id, **details}
            for metric_id, details in METRICS.items()
        ],
    }


@app.get("/metrics/{metric_id}")
def get_metric(
    metric_id: str,
    limit: int = Query(default=100, ge=1, le=500),
):
    metric_id = metric_id.upper()

    if metric_id not in METRICS:
        raise HTTPException(status_code=404, detail="Unknown metric ID")

    metric = METRICS[metric_id]
    con = get_connection()

    try:
        view = metric["source_view"]
        rows = con.execute(
            f"SELECT * FROM {view} LIMIT ?",
            [limit],
        ).fetchdf().to_dict(orient="records")
    finally:
        con.close()

    # Apply a second privacy check before returning records.
    rows = [
        row for row in rows
        if row.get("group_size", 0) >= metric["minimum_group_size"]
    ]

    return jsonable_encoder({
        "metric_id": metric_id,
        "name": metric["name"],
        "formula": metric["formula"],
        "source_table": metric["source_table"],
        "source_view": metric["source_view"],
        "grain": metric["grain"],
        "unit": metric["unit"],
        "minimum_group_size": metric["minimum_group_size"],
        "record_count": len(rows),
        "data": rows,
        "catalog_note": metric.get("catalog_note"),
    })


@app.get("/lineage/{metric_id}")
def get_lineage(metric_id: str):
    metric_id = metric_id.upper()

    if metric_id not in METRICS:
        raise HTTPException(status_code=404, detail="Unknown metric ID")

    metric = METRICS[metric_id]

    return {
        "metric_id": metric_id,
        "metric_name": metric["name"],
        "source_table": metric["source_table"],
        "published_view": metric["source_view"],
        "lineage_steps": metric["lineage"],
    }


@app.get("/freshness")
def get_freshness():
    con = get_connection()
    metric_freshness = {}

    try:
        for metric_id, (source, date_column) in SOURCE_FRESHNESS.items():
            result = con.execute(
                f"SELECT MAX({date_column}) FROM {source}"
            ).fetchone()[0]

            metric_freshness[metric_id] = {
                "source": source,
                "date_column": date_column,
                "latest_source_date": str(result) if result else None,
            }
    finally:
        con.close()

    last_successful_etl = None
    if ETL_LOG.exists():
        with ETL_LOG.open(newline="") as file:
            entries = list(csv.DictReader(file))
        successful = [
            entry for entry in entries
            if entry.get("status", "").upper() == "SUCCESS"
        ]
        if successful:
            last_successful_etl = successful[-1]

    return {
        "metric_source_freshness": metric_freshness,
        "last_successful_etl_validation": last_successful_etl,
        "hosted_refresh_log_modified": (
            HOSTED_LOG.stat().st_mtime if HOSTED_LOG.exists() else None
        ),
        "database_file_modified": (
            DB_PATH.stat().st_mtime if DB_PATH.exists() else None
        ),
        "note": (
            "ETL validation, hosted export refresh, database file modification, "
            "and source data dates are separate freshness indicators."
        ),
    }
