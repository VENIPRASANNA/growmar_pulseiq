"""Privacy-controlled KPI queries for the PulseIQ Explorer."""

import re

from src.explorer_access import can_access_metric
from src.privacy_gate import can_publish


METRICS = {
    "M01": ("m01_headcount", "headcount", "department"),
    "M02": ("m02_hires", "hires", "department"),
    "M03": ("m03_exits", "exits", "department"),
    "M04": ("m04_attrition_monthly", "attrition_rate_pct", "department"),
    "M05": ("m05_attrition_rolling_12m", "attrition_rate_12m_pct", "department"),
    "M06": ("m06_voluntary_attrition_rate", "voluntary_attrition_rate_pct", "department"),
    "M07": ("m07_gross_pay", "gross_pay", "department"),
    "M08": ("m08_net_pay", "net_pay", "department"),
    "M09": ("m09_payroll_employer_cost", "employer_cost", "department"),
    "M10": ("m10_cost_per_head", "cost_per_head", "department"),
    "M11": ("m11_overtime_share", "overtime_share_pct", "department"),
    "M12": ("m12_variable_pay_share", "variable_pay_share_pct", "department"),
    "M13": ("m13_attendance_rate", "attendance_rate_pct", "department"),
    "M14": ("m14_late_arrival_rate", "late_arrivals_per_100_present_days", "department"),
    "M15": ("m15_leave_without_pay_days", "leave_without_pay_days", "department"),
    "M22": ("m22_task_completion_rate", "task_completion_rate_pct", "team"),
    "M23": ("m23_on_time_delivery_rate", "on_time_delivery_rate_pct", "team"),
    "M25": ("m25_average_cycle_time", "average_cycle_time_days", "team"),
    "M27": ("m27_high_risk_share", "high_risk_share_pct", "department"),
}


def get_approved_metrics(con, user):
    """Return only role-authorized metrics with approved thresholds."""
    rows = con.execute("""
        SELECT metric_id, metric_name, minimum_group_size,
               threshold_status, unit, grain, caveat
        FROM metrics.metric_catalog
        ORDER BY metric_id
    """).fetchdf()

    approved = []

    for row in rows.to_dict("records"):
        metric_id = row["metric_id"]
        raw_threshold = str(row["minimum_group_size"])

        match = re.match(r"^(\d+)", raw_threshold)
        if row["threshold_status"] != "DEFINED" or not match:
            continue

        if metric_id not in METRICS:
            continue

        if can_access_metric(user, metric_id):
            row["minimum_group_size"] = int(match.group(1))
            approved.append(row)

    return approved


def _company_query(con, metric_id, minimum):
    """Calculate company-level workforce KPIs from complete monthly totals."""
    if metric_id not in {"M01", "M02", "M03", "M04", "M05", "M06"}:
        raise PermissionError("This metric has no approved company view.")

    sql = """
        WITH monthly AS (
            SELECT
                month_start_date,
                SUM(headcount_end) AS headcount,
                SUM(headcount_start) AS headcount_start,
                SUM(hires) AS hires,
                SUM(exits) AS exits,
                SUM(voluntary_exits) AS voluntary_exits
            FROM raw.fact_headcount_monthly
            WHERE department_id <> 'D00'
            GROUP BY month_start_date
        ),
        rolling AS (
            SELECT *,
                COUNT(*) OVER (
                    ORDER BY month_start_date
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
                ) AS months_in_window,
                SUM(exits) OVER (
                    ORDER BY month_start_date
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
                ) AS exits_12m,
                SUM(voluntary_exits) OVER (
                    ORDER BY month_start_date
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
                ) AS voluntary_exits_12m,
                AVG(headcount) OVER (
                    ORDER BY month_start_date
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
                ) AS avg_headcount_12m
            FROM monthly
        )
        SELECT
            month_start_date,
            CASE ?
                WHEN 'M01' THEN headcount
                WHEN 'M02' THEN hires
                WHEN 'M03' THEN exits
                WHEN 'M04' THEN
                    ROUND(100.0 * exits / NULLIF(headcount_start, 0), 2)
                WHEN 'M05' THEN
                    ROUND(100.0 * exits_12m / NULLIF(avg_headcount_12m, 0), 2)
                WHEN 'M06' THEN
                    ROUND(100.0 * voluntary_exits_12m
                          / NULLIF(avg_headcount_12m, 0), 2)
            END AS metric_value,
            headcount AS group_size,
            'Company' AS dimension_name
        FROM rolling
        WHERE headcount >= ?
          AND (? NOT IN ('M05', 'M06') OR months_in_window = 12)
        ORDER BY month_start_date
    """

    result = con.execute(
        sql, [metric_id, minimum, metric_id]
    ).fetchdf()

    # Apply the privacy gate to every returned group.
    return result[
        result["group_size"].apply(
            lambda n: can_publish(metric_id, int(n), {metric_id: minimum})
        )
    ].reset_index(drop=True)


def query_metric(
    con,
    user,
    metric_id,
    dimension,
    department_id=None,
    team_id=None,
):
    """Query an approved KPI with mandatory role and privacy filters."""

    if not can_access_metric(user, metric_id):
        raise PermissionError("Your role cannot access this metric.")

    if metric_id not in METRICS:
        raise PermissionError("Metric is unavailable or not approved.")

    catalog = con.execute("""
        SELECT minimum_group_size, threshold_status
        FROM metrics.metric_catalog
        WHERE metric_id = ?
    """, [metric_id]).fetchone()

    if not catalog or catalog[1] != "DEFINED":
        raise PermissionError("Privacy threshold is not approved.")

    match = re.match(r"^(\d+)", str(catalog[0]))
    if not match:
        raise PermissionError("Metric has no valid privacy threshold.")

    minimum = int(match.group(1))

    # Company-level access is restricted to approved workforce KPIs.
    if dimension == "company":
        if user.role not in {"ADMIN", "EXECUTIVE"}:
            raise PermissionError("Company-level access is not permitted.")
        if metric_id not in {"M01", "M02", "M03", "M04", "M05", "M06"}:
            raise PermissionError("This KPI has no approved company-level view.")
        return _company_query(con, metric_id, minimum)

    view, value_column, grain = METRICS[metric_id]

    if dimension != grain:
        raise PermissionError("Unsupported dimension for this KPI.")

    if grain == "department":
        if user.role not in {"ADMIN", "HR"}:
            raise PermissionError("Department-level access is not permitted.")

        if user.role == "HR":
            if department_id not in (None, user.department_id):
                raise PermissionError("HR users can only access their own department.")
            department_id = user.department_id

        sql = f"""
            SELECT v.*, d.department_name AS dimension_name
            FROM metrics.{view} v
            JOIN raw.dim_department d
              ON d.department_id = v.department_id
            WHERE v.group_size >= ?
        """
        params = [minimum]

        if department_id is not None:
            sql += " AND v.department_id = ?"
            params.append(department_id)

        sql += " ORDER BY 1, 2"

    else:
        if user.role not in {"ADMIN", "MANAGER"}:
            raise PermissionError("Team-level access is not permitted.")

        if user.role == "MANAGER":
            if team_id not in (None, user.team_id):
                raise PermissionError("Managers can only access their own team.")
            team_id = user.team_id

        sql = f"""
            SELECT v.*, t.team_name AS dimension_name,
                   s.sprint_name
            FROM metrics.{view} v
            JOIN raw.dim_team t ON t.team_id = v.team_id
            JOIN raw.dim_sprint s ON s.sprint_id = v.sprint_id
            WHERE v.group_size >= ?
        """
        params = [minimum]

        if team_id is not None:
            sql += " AND v.team_id = ?"
            params.append(team_id)

        sql += " ORDER BY v.sprint_id"

    result = con.execute(sql, params).fetchdf()

    if not result.empty:
        result = result[
            result["group_size"].apply(
                lambda n: can_publish(
                    metric_id, int(n), {metric_id: minimum}
                )
            )
        ].reset_index(drop=True)

    return result
