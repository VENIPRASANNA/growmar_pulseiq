
"""PulseIQ Phase 1 ETL: contract validation and quarantine."""

from pathlib import Path
import json
import csv
import traceback
from datetime import datetime, timezone
import re

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "05_Starter" / "pulseiq.duckdb"
CLEAN_DIR = ROOT / "data" / "clean"
REJECTED_DIR = ROOT / "data" / "rejected"
LOG_DIR = ROOT / "logs"

# These are the columns defined by the supplied contracts.
CONTRACT_COLUMNS = {
    "fact_anomaly": [
        "result_id", "source_dataset", "record_id", "employee_id",
        "period", "anomaly_score", "flagged", "reason_code",
        "reason_text", "money_at_risk", "model_version", "scored_at",
    ],
    "fact_attrition_risk": [
        "prediction_id", "employee_id", "department_id", "as_of_date",
        "risk_score_12m", "risk_band", "top_reason_1", "top_reason_2",
        "top_reason_3", "model_version",
    ],
    "fact_forecast": [
        "forecast_id", "metric", "department_id", "forecast_month",
        "forecast_value", "lower_80", "upper_80", "method",
        "trained_through",
    ],
    "fact_task": [
        "task_id", "team_id", "sprint_id", "assignee_employee_id",
        "task_type", "priority", "story_points", "created_date",
        "started_date", "due_date", "completed_date", "status",
        "reopened_count",
    ],
}

ID_COLUMNS = {
    "fact_anomaly": "result_id",
    "fact_attrition_risk": "prediction_id",
    "fact_forecast": "forecast_id",
    "fact_task": "task_id",
}


def values(con, sql):
    """Return the first column of a query as a set of strings."""
    return set(con.execute(sql).df().iloc[:, 0].dropna().astype(str))


def validate_table(con, table):
    """Return input data with a validation-reason column."""
    df = con.execute(f"SELECT * FROM raw.{table}").df()
    original_count = len(df)
    reasons = [[] for _ in range(original_count)]

    contract = CONTRACT_COLUMNS[table]
    unexpected = sorted(set(df.columns) - set(contract))
    missing = sorted(set(contract) - set(df.columns))

    if missing:
        raise ValueError(
            f"{table} is missing contract columns: {missing}"
        )

    def reject(mask, message):
        """Attach a reason to each row where mask is true."""
        for idx in df.index[mask.fillna(False)]:
            reasons[idx].append(message)

    # Every contract column marked non-null must contain a value.
    nullable = {
        "fact_anomaly": {"money_at_risk"},
        "fact_attrition_risk": {
            "top_reason_1", "top_reason_2", "top_reason_3"
        },
        "fact_forecast": set(),
        "fact_task": {"started_date", "completed_date"},
    }

    for col in contract:
        if col not in nullable[table]:
            reject(df[col].isna(), f"{col} is required")

    # IDs must be unique and follow the contract's format.
    id_col = ID_COLUMNS[table]
    if table == "fact_anomaly":
        pattern = r"AN-\d{4}"
    elif table == "fact_attrition_risk":
        pattern = r"AR-\d{4}"
    elif table == "fact_forecast":
        pattern = r"FC-\d{4}"
    else:
        pattern = r"TASK-\d{5}"

    reject(
        ~df[id_col].astype("string").str.fullmatch(pattern, na=False),
        f"{id_col} has an invalid format",
    )
    reject(
        df[id_col].duplicated(keep=False),
        f"{id_col} is duplicated",
    )

    # Reference data: use distinct IDs because dimensions can contain history.
    employee_ids = values(
        con, "SELECT DISTINCT employee_id FROM raw.dim_employee"
    )
    department_ids = values(
        con, "SELECT DISTINCT department_id FROM raw.dim_department"
    )
    team_ids = values(
        con, "SELECT DISTINCT team_id FROM raw.dim_team"
    )
    sprint_ids = values(
        con, "SELECT DISTINCT sprint_id FROM raw.dim_sprint"
    )

    if table == "fact_anomaly":
        reject(
            ~df["source_dataset"].isin([
                "attendance_monthly_features",
                "payroll_monthly_features",
            ]),
            "source_dataset is not an allowed value",
        )
        reject(
            ~df["employee_id"].astype("string").isin(employee_ids),
            "employee_id not found in dim_employee",
        )
        period_dates = pd.to_datetime(
            df["period"], errors="coerce"
        )

        month_start = period_dates.dt.is_month_start
        month_end = period_dates.dt.is_month_end

        reject(
            ~(month_start | month_end),
            "period must be a month-start or month-end date",
        )
        reject(
            ~df["flagged"].isin(["Y", "N"]),
            "flagged must be Y or N",
        )
        reject(
            ~df["anomaly_score"].between(0, 1, inclusive="both"),
            "anomaly_score must be between 0 and 1",
        )
        reject(
            ~df["reason_code"].isin({
                "FREQUENT_LATE", "GROSS_ABOVE_NORM",
                "GROSS_BELOW_EXPECTED", "LONG_UNPAID_ABSENCE",
                "NEGATIVE_NET_PAY", "NO_ATTENDANCE",
                "OVERTIME_ABOVE_CAP", "PATTERN_SHIFT",
                "PF_NOT_DEDUCTED", "STATISTICAL_OUTLIER", "ZERO_PAY",
            }),
            "reason_code is not a published code",
        )
        reject(
            df["money_at_risk"].notna()
            & df["source_dataset"].eq("attendance_monthly_features"),
            "money_at_risk must be blank for attendance rows",
        )
       


        # The feature datasets required by the contract are not loaded.
        # Do not guess that AF IDs match FA IDs or PI IDs.
        source_check_note = (
            "Not verified: feature source datasets are not present in raw schema"
        )
    else:
        source_check_note = ""

    if table == "fact_attrition_risk":
        reject(
            ~df["employee_id"].astype("string").isin(employee_ids),
            "employee_id not found in dim_employee",
        )
        reject(
            ~df["department_id"].astype("string").isin(department_ids),
            "department_id not found in dim_department",
        )
        reject(
            ~df["risk_score_12m"].between(0, 1, inclusive="both"),
            "risk_score_12m must be between 0 and 1",
        )
        reject(
            ~df["risk_band"].isin(["Low", "Medium", "High"]),
            "risk_band must be Low, Medium, or High",
        )
        batch_date = df["as_of_date"].max()

        reject(
            df["as_of_date"].ne(batch_date),
            f"as_of_date must match batch date {batch_date}",
)

        # The active-status rule is checked against current employee records.
        current = con.execute("""
            SELECT DISTINCT employee_id
            FROM raw.dim_employee
            WHERE is_current = 'Y'
              AND lower(employment_status) = 'active'
        """).df()["employee_id"].astype(str)
        reject(
            ~df["employee_id"].astype("string").isin(set(current)),
            "employee is not active in current employee records",
        )

    if table == "fact_forecast":
        reject(
            ~df["metric"].isin([
                "headcount_end", "attrition_rate_monthly_pct"
            ]),
            "metric is not allowed",
        )
        reject(
            ~(
                df["department_id"].eq("ALL")
                | df["department_id"].astype("string").isin(department_ids)
            ),
            "department_id must exist in dim_department or be ALL",
        )
        reject(
            df["forecast_month"].dt.day.ne(1),
            "forecast_month must be the first day of a month",
        )
        reject(
            df["forecast_value"] < 0,
            "forecast_value must be >= 0",
        )
        reject(
            df["lower_80"] > df["forecast_value"],
            "lower_80 must be <= forecast_value",
        )
        reject(
            df["upper_80"] < df["forecast_value"],
            "upper_80 must be >= forecast_value",
        )
        reject(
            ~df["trained_through"].astype("string").str.fullmatch(
                r"\d{4}-\d{2}", na=False
            ),
            "trained_through must use YYYY-MM",
        )

    if table == "fact_task":
        reject(
            ~df["team_id"].astype("string").isin(team_ids),
            "team_id not found in dim_team",
        )
        reject(
            ~df["sprint_id"].astype("string").isin(sprint_ids),
            "sprint_id not found in dim_sprint",
        )

        # The task due date must match the sprint's end date.
        sprint_dates = con.execute("""
            SELECT sprint_id, end_date
            FROM raw.dim_sprint
        """).df()

        sprint_end_dates = dict(
            zip(sprint_dates["sprint_id"], sprint_dates["end_date"])
        )

        expected_end_date = df["sprint_id"].map(sprint_end_dates)

        reject(
            df["due_date"].ne(expected_end_date),
            "due_date must match sprint end date",
        )

        reject(
            ~df["assignee_employee_id"].astype("string").isin(employee_ids),
            "assignee_employee_id not found in dim_employee",
        )
        reject(
            ~df["task_type"].isin(["Feature", "Bug", "Chore", "Spike"]),
            "task_type is not allowed",
        )
        reject(
            ~df["priority"].isin(["P1", "P2", "P3", "P4"]),
            "priority must be P1, P2, P3, or P4",
        )
        reject(
            ~df["story_points"].isin([1, 2, 3, 5, 8, 13]),
            "story_points is not allowed",
        )
        reject(
            ~df["status"].isin([
                "Done", "In Progress", "Blocked", "To Do", "Cancelled"
            ]),
            "status is not allowed",
        )
        reject(
            df["reopened_count"] < 0,
            "reopened_count must be >= 0",
        )
        reject(
            df["started_date"].isna() & df["status"].ne("To Do"),
            "started_date may be blank only when status is To Do",
        )
        reject(
            df["completed_date"].isna() & df["status"].eq("Done"),
            "completed_date is required when status is Done",
        )
        reject(
            df["completed_date"].notna()
            & df["started_date"].notna()
            & (df["completed_date"] < df["started_date"]),
            "completed_date must be >= started_date",
        )
        reject(
            df["started_date"].notna()
            & (df["created_date"] > df["started_date"]),
            "created_date must be <= started_date",
        )

    # Save a separate reason per row, even when multiple rules fail.
    df["validation_reason"] = [
        "; ".join(row_reasons) for row_reasons in reasons
    ]

    passed = df[df["validation_reason"].eq("")].copy()
    rejected = df[~df["validation_reason"].eq("")].copy()

    # Extra source columns are preserved in outputs, but reported.
    summary = {
        "table": table,
        "input_rows": original_count,
        "passed_rows": len(passed),
        "quarantined_rows": len(rejected),
        "unexpected_columns": ", ".join(unexpected),
        "missing_contract_columns": ", ".join(missing),
        "source_reference_note": source_check_note,
    }

    return passed, rejected, summary


def write_etl_run_log(started_at, finished_at, status, error_message=""):
    """Append an ETL execution record to logs/etl_run_log.csv."""
    log_path = LOG_DIR / "etl_run_log.csv"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not log_path.exists()

    with log_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["started_at", "finished_at", "status", "error_message"],
        )
        if write_header:
            writer.writeheader()
        writer.writerow({
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "status": status,
            "error_message": error_message,
        })


def main():
    started_at = datetime.now(timezone.utc)
    status = "SUCCESS"
    error_message = ""

    try:
        _main_pipeline()
    except Exception as exc:
        status = "FAILED"
        error_message = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        write_etl_run_log(
            started_at,
            datetime.now(timezone.utc),
            status,
            error_message,
        )


def _main_pipeline():
    for folder in [CLEAN_DIR, REJECTED_DIR, LOG_DIR]:
        folder.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(DB_PATH), read_only=True)
    summaries = []

    try:
        for table in CONTRACT_COLUMNS:
            print(f"\nValidating {table}...")
            passed, rejected, summary = validate_table(con, table)

            passed.drop(columns=["validation_reason"]).to_csv(
                CLEAN_DIR / f"{table}.csv", index=False
            )
            rejected.to_csv(
                REJECTED_DIR / f"{table}_quarantine.csv", index=False
            )
            summaries.append(summary)

            print(
                f"Input: {summary['input_rows']} | "
                f"Passed: {summary['passed_rows']} | "
                f"Quarantined: {summary['quarantined_rows']}"
            )
            if summary["unexpected_columns"]:
                print(
                    "Unexpected columns reported: "
                    + summary["unexpected_columns"]
                )
            if summary["source_reference_note"]:
                print("NOTE:", summary["source_reference_note"])

            assert (
                summary["input_rows"]
                == summary["passed_rows"] + summary["quarantined_rows"]
            ), f"Row reconciliation failed for {table}"

    finally:
        con.close()

    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(LOG_DIR / "etl_summary.csv", index=False)
    summary_df.to_json(
        LOG_DIR / "etl_summary.json", orient="records", indent=2
    )

    print("\n--- ETL SUMMARY ---")
    print(summary_df.to_string(index=False))
    print("\nETL completed. No input rows were silently discarded.")


if __name__ == "__main__":
    main()
