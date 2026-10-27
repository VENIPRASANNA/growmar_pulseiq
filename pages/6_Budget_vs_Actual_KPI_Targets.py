
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="Budget vs Actual | PulseIQ",
    page_icon="📊",
    layout="wide",
)

st.title("Budget vs Actual & KPI Targets")
st.caption(
    "PulseIQ | Financial performance, departmental budgets "
    "and operational KPI monitoring"
)

DB_PATH = (
    Path(__file__).resolve().parents[1]
    / "05_Starter"
    / "pulseiq.duckdb"
)


# =========================================================
# 2. DATABASE HELPERS
# =========================================================
@st.cache_data(ttl=300, show_spinner="Loading PulseIQ analytics...")
def load_query(sql: str) -> pd.DataFrame:
    """Run a read-only query against the PulseIQ database."""
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return con.execute(sql).df()
    finally:
        con.close()


def money(value):
    if pd.isna(value):
        return "—"
    return f"₹{value:,.2f}"


def show_query_error(section, error):
    st.error(f"Unable to load {section}.")
    with st.expander("Technical details"):
        st.code(str(error))


def style_money_columns(df, columns):
    """Format selected numeric columns as Indian rupee amounts."""
    format_dict = {
        col: "₹{:,.2f}"
        for col in columns
        if col in df.columns
    }
    return df.style.format(format_dict, na_rep="—")


# =========================================================
# 3. CHECK DATABASE
# =========================================================
if not DB_PATH.exists():
    st.error(f"PulseIQ database not found: {DB_PATH}")
    st.stop()


# =========================================================
# 4. LOAD OFFICIAL DATA
# =========================================================
try:
    # Budget versus actual payroll
    budget_actual = load_query("""
        WITH actual AS (
            SELECT
                d.month_start_date AS month,
                p.department_id,
                ROUND(SUM(p.employer_cost), 2) AS actual_cost,
                COUNT(DISTINCT p.employee_id) AS employee_count
            FROM metrics.v_payroll_clean p
            JOIN raw.dim_date d
                ON d.date_key = p.date_key
            GROUP BY 1, 2
            HAVING COUNT(DISTINCT p.employee_id) >= 5
        )
        SELECT
            a.month,
            a.department_id,
            dep.department_name,
            a.employee_count,
            b.budget_payroll_cost AS budget,
            a.actual_cost,
            ROUND(
                a.actual_cost - b.budget_payroll_cost,
                2
            ) AS variance,
            ROUND(
                100.0 * (
                    a.actual_cost - b.budget_payroll_cost
                ) / NULLIF(b.budget_payroll_cost, 0),
                2
            ) AS variance_pct
        FROM actual a
        JOIN raw.budget_payroll_dept_month b
            ON a.month = b.month
            AND a.department_id = b.department_id
        LEFT JOIN raw.dim_department dep
            ON a.department_id = dep.department_id
        ORDER BY a.month, a.department_id
    """)

    # Attendance
    attendance = load_query("""
        SELECT
            month_start_date AS month,
            department_id,
            attendance_rate_pct,
            employee_count,
            group_size
        FROM metrics.m13_attendance_rate
    """)

    # Overtime
    overtime = load_query("""
        SELECT
            month_start_date AS month,
            department_id,
            overtime_share_pct,
            employee_count,
            group_size
        FROM metrics.m11_overtime_share
    """)

    # Attrition
    attrition = load_query("""
        SELECT
            month_start_date AS month,
            department_id,
            exits,
            headcount_start,
            attrition_rate_pct,
            group_size
        FROM metrics.m04_attrition_monthly
    """)

    # Team/sprint task completion
    task_completion = load_query("""
        SELECT
            team_id,
            sprint_id,
            completed_tasks,
            eligible_tasks,
            task_completion_rate_pct,
            group_size
        FROM metrics.m22_task_completion_rate
        WHERE group_size >= 5
    """)

    # KPI targets
    targets = load_query("""
        SELECT
            month,
            department_id,
            attendance_rate_target,
            overtime_share_target_pct,
            attrition_monthly_target_pct,
            task_completion_target_pct
        FROM raw.kpi_targets
    """)

    departments = load_query("""
        SELECT department_id, department_name
        FROM raw.dim_department
        ORDER BY department_name
    """)

except Exception as exc:
    show_query_error("dashboard data", exc)
    st.stop()


# =========================================================
# 5. PREPARE DATA
# =========================================================
if budget_actual.empty:
    st.warning(
        "No matching department-month budget and actual payroll "
        "records were found."
    )
    st.stop()

for df in [budget_actual, attendance, overtime, attrition, targets]:
    if "month" in df.columns:
        df["month"] = pd.to_datetime(df["month"])

# Create a department-name lookup.
department_names = dict(
    zip(
        departments["department_id"],
        departments["department_name"],
    )
)


# =========================================================
# 6. SIDEBAR FILTERS
# =========================================================
st.sidebar.header("Dashboard Filters")

min_month = budget_actual["month"].min().date()
max_month = budget_actual["month"].max().date()

date_range = st.sidebar.date_input(
    "Month range",
    value=(min_month, max_month),
    min_value=min_month,
    max_value=max_month,
)

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = end_date = date_range

start_date = pd.Timestamp(start_date)
end_date = pd.Timestamp(end_date)

department_options = departments["department_id"].tolist()

selected_departments = st.sidebar.multiselect(
    "Departments",
    options=department_options,
    default=department_options,
    format_func=lambda x: department_names.get(x, x),
)

filtered = budget_actual[
    budget_actual["month"].between(start_date, end_date)
    & budget_actual["department_id"].isin(selected_departments)
].copy()

if filtered.empty:
    st.warning("No payroll records match your selected filters.")
    st.stop()

# Use the same period and department filters for KPI targets.
target_filtered = targets[
    targets["month"].between(start_date, end_date)
    & targets["department_id"].isin(selected_departments)
].copy()


# =========================================================
# 7. FINANCIAL OVERVIEW
# =========================================================
st.subheader("Financial Overview")

total_budget = filtered["budget"].sum()
total_actual = filtered["actual_cost"].sum()
net_variance = total_actual - total_budget

# Sum positive variances only. Do not offset them by underspends.
gross_overspend = filtered.loc[
    filtered["variance"] > 0, "variance"
].sum()

net_variance_pct = (
    100 * net_variance / total_budget
    if total_budget != 0
    else None
)

overspend_departments = filtered.loc[
    filtered["variance"] > 0, "department_id"
].nunique()

c1, c2, c3, c4 = st.columns(4)

c1.metric("Total Budget", money(total_budget))
c2.metric("Actual Payroll Cost", money(total_actual))

c3.metric(
    "Net Budget Variance",
    money(net_variance),
    delta=(
        f"{net_variance_pct:+.2f}%"
        if net_variance_pct is not None
        else None
    ),
    delta_color="inverse",
)

c4.metric("Gross Monthly Overspend", money(gross_overspend))

st.caption(
    f"Showing {len(filtered)} department-month records across "
    f"{filtered['department_id'].nunique()} departments. "
    f"{overspend_departments} departments have at least one "
    "monthly overspend. Gross overspend sums positive monthly "
    "variances without offsetting underspends."
)


# =========================================================
# 8. MONTHLY BUDGET VS ACTUAL
# =========================================================
st.divider()
st.subheader("1. Monthly Budget vs Actual")

monthly = (
    filtered.groupby("month", as_index=False)
    .agg(
        budget=("budget", "sum"),
        actual=("actual_cost", "sum"),
    )
    .sort_values("month")
)

monthly["variance"] = monthly["actual"] - monthly["budget"]

monthly["variance_pct"] = (
    100 * monthly["variance"] / monthly["budget"]
).where(monthly["budget"] != 0)

# Separate measures for the chart.
monthly_chart = monthly.melt(
    id_vars="month",
    value_vars=["budget", "actual"],
    var_name="measure",
    value_name="cost",
)

monthly_chart["measure"] = monthly_chart["measure"].map({
    "budget": "Budget",
    "actual": "Actual",
})

st.line_chart(
    monthly_chart,
    x="month",
    y="cost",
    color="measure",
)

st.caption(
    "Budget and actual cost are summed across selected departments "
    "for each month."
)

st.markdown("**Monthly variance details**")

monthly_display = monthly.copy()
monthly_display["month"] = monthly_display["month"].dt.strftime("%Y-%m")
monthly_display = monthly_display.rename(
    columns={
        "month": "Month",
        "budget": "Budget (₹)",
        "actual": "Actual (₹)",
        "variance": "Variance (₹)",
        "variance_pct": "Variance (%)",
    }
)

st.dataframe(
    monthly_display.style.format(
        {
            "Budget (₹)": "₹{:,.2f}",
            "Actual (₹)": "₹{:,.2f}",
            "Variance (₹)": "₹{:,.2f}",
            "Variance (%)": "{:+.2f}%",
        },
        na_rep="—",
    ),
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# 9. DEPARTMENT OVESPEND RANKING
# =========================================================
st.divider()
st.subheader("2. Department Overspend Ranking")

ranking = (
    filtered.assign(
        positive_variance=filtered["variance"].clip(lower=0)
    )
    .groupby(
        ["department_id", "department_name"],
        dropna=False,
        as_index=False,
    )
    .agg(
        months=("month", "nunique"),
        total_budget=("budget", "sum"),
        total_actual=("actual_cost", "sum"),
        net_variance=("variance", "sum"),
        gross_overspend=("positive_variance", "sum"),
        overspend_months=(
            "variance",
            lambda x: int((x > 0).sum()),
        ),
    )
    .sort_values("gross_overspend", ascending=False)
)

st.caption(
    "Gross overspend = sum of positive monthly variances. "
    "Net variance = sum of all monthly variances, including "
    "underspends. These measures answer different questions."
)

rank_chart = ranking.head(10).sort_values("gross_overspend")

st.bar_chart(
    rank_chart,
    x="department_name",
    y="gross_overspend",
)

ranking_display = ranking.rename(
    columns={
        "department_id": "Department ID",
        "department_name": "Department",
        "months": "Months",
        "total_budget": "Total Budget (₹)",
        "total_actual": "Actual Cost (₹)",
        "net_variance": "Net Variance (₹)",
        "gross_overspend": "Gross Overspend (₹)",
        "overspend_months": "Overspend Months",
    }
)

st.dataframe(
    ranking_display.style.format(
        {
            "Total Budget (₹)": "₹{:,.2f}",
            "Actual Cost (₹)": "₹{:,.2f}",
            "Net Variance (₹)": "₹{:,.2f}",
            "Gross Overspend (₹)": "₹{:,.2f}",
        },
        na_rep="—",
    ),
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# 10. KPI TARGET TRACKING
# =========================================================
st.divider()
st.subheader("3. KPI Target Tracking")

st.caption(
    "Attendance targets are stored as ratios, so a target of 0.94 "
    "is compared as 94%. Overtime and attrition are compared in "
    "percentage units. Missing targets remain unavailable."
)


def evaluate_kpi(
    metric_df,
    actual_col,
    target_col,
    label,
    higher_is_better,
    min_group_size,
    target_multiplier=1.0,
):
    """Compare a department-month metric with its matching target."""
    data = metric_df.copy()
    data["month"] = pd.to_datetime(data["month"])

    data = data[
        data["month"].between(start_date, end_date)
        & data["department_id"].isin(selected_departments)
        & (data["group_size"] >= min_group_size)
    ].copy()

    result = data.merge(
        target_filtered[["month", "department_id", target_col]],
        on=["month", "department_id"],
        how="left",
    )

    result["actual"] = pd.to_numeric(
        result[actual_col],
        errors="coerce",
    )

    result["target"] = (
        pd.to_numeric(result[target_col], errors="coerce")
        * target_multiplier
    )

    def get_status(row):
        if pd.isna(row["target"]):
            return "Target unavailable"

        if pd.isna(row["actual"]):
            return "Actual unavailable"

        if higher_is_better:
            met = row["actual"] >= row["target"]
        else:
            met = row["actual"] <= row["target"]

        return "Meets target" if met else "Misses target"

    result["status"] = result.apply(get_status, axis=1)
    result["KPI"] = label

    return result[
        [
            "month",
            "department_id",
            "actual",
            "target",
            "status",
            "group_size",
            "KPI",
        ]
    ]


try:
    attendance_status = evaluate_kpi(
        attendance,
        actual_col="attendance_rate_pct",
        target_col="attendance_rate_target",
        label="Attendance",
        higher_is_better=True,
        min_group_size=5,
        target_multiplier=100.0,
    )

    overtime_status = evaluate_kpi(
        overtime,
        actual_col="overtime_share_pct",
        target_col="overtime_share_target_pct",
        label="Overtime share",
        higher_is_better=False,
        min_group_size=5,
    )

    attrition_status = evaluate_kpi(
        attrition,
        actual_col="attrition_rate_pct",
        target_col="attrition_monthly_target_pct",
        label="Monthly attrition",
        higher_is_better=False,
        min_group_size=10,
    )

    kpi_status = pd.concat(
        [
            attendance_status,
            overtime_status,
            attrition_status,
        ],
        ignore_index=True,
    )

    if kpi_status.empty:
        st.info(
            "No KPI observations meet the required group-size rules "
            "for the selected filters."
        )
    else:
        available_kpis = sorted(kpi_status["KPI"].unique())

        selected_kpis = st.multiselect(
            "KPI types",
            options=available_kpis,
            default=available_kpis,
        )

        kpi_view = kpi_status[
            kpi_status["KPI"].isin(selected_kpis)
        ].copy()

        status_summary = (
            kpi_view.groupby(
                ["KPI", "status"],
                as_index=False,
            )
            .size()
            .rename(columns={"size": "Observations"})
        )

        st.markdown("**KPI status summary**")
        st.dataframe(
            status_summary,
            use_container_width=True,
            hide_index=True,
        )

        kpi_display = kpi_view.rename(
            columns={
                "month": "Month",
                "department_id": "Department",
                "actual": "Actual (%)",
                "target": "Target (%)",
                "status": "Status",
                "group_size": "Group Size",
            }
        )

        kpi_display["Month"] = (
            kpi_display["Month"].dt.strftime("%Y-%m")
        )

        st.markdown("**Monthly department-level KPI results**")

        st.dataframe(
            kpi_display.style.format(
                {
                    "Actual (%)": "{:.2f}%",
                    "Target (%)": "{:.2f}%",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )

except Exception as exc:
    show_query_error("KPI target comparisons", exc)


# =========================================================
# 11. TASK COMPLETION BY TEAM
# =========================================================
st.divider()
st.subheader("4. Team Task Completion")

st.caption(
    "Task completion is measured at team-sprint grain. The chart "
    "below aggregates task counts by team before calculating the "
    "completion rate; it does not sum percentages."
)

if task_completion.empty:
    st.info(
        "No task-completion groups meet the minimum group-size rule."
    )
else:
    task_data = task_completion.copy()

    for col in ["completed_tasks", "eligible_tasks"]:
        task_data[col] = pd.to_numeric(
            task_data[col],
            errors="coerce",
        )

    task_data = task_data.dropna(
        subset=["completed_tasks", "eligible_tasks"]
    )

    # Keep valid eligible task counts.
    task_data = task_data[task_data["eligible_tasks"] > 0].copy()

    if task_data.empty:
        st.info("No valid task-completion counts are available.")
    else:
        # Correct aggregation: sum counts, then calculate percentage.
        team_summary = (
            task_data.groupby("team_id", as_index=False)
            .agg(
                completed_tasks=("completed_tasks", "sum"),
                eligible_tasks=("eligible_tasks", "sum"),
            )
        )

        team_summary["completion_rate_pct"] = (
            100.0
            * team_summary["completed_tasks"]
            / team_summary["eligible_tasks"]
        )

        team_summary = team_summary.sort_values(
            "completion_rate_pct",
            ascending=False,
        )

        st.bar_chart(
            team_summary,
            x="team_id",
            y="completion_rate_pct",
        )

        team_display = team_summary.rename(
            columns={
                "team_id": "Team",
                "completed_tasks": "Completed Tasks",
                "eligible_tasks": "Eligible Tasks",
                "completion_rate_pct": "Completion Rate (%)",
            }
        )

        st.dataframe(
            team_display.style.format(
                {"Completion Rate (%)": "{:.2f}%"},
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )

        # Preserve the detailed sprint-level view.
        st.markdown("**Team and sprint details**")

        sprint_display = task_data[
            [
                "team_id",
                "sprint_id",
                "completed_tasks",
                "eligible_tasks",
                "group_size",
            ]
        ].rename(
            columns={
                "team_id": "Team",
                "sprint_id": "Sprint",
                "completed_tasks": "Completed Tasks",
                "eligible_tasks": "Eligible Tasks",
                "group_size": "Group Size",
            }
        )

        st.dataframe(
            sprint_display,
            use_container_width=True,
            hide_index=True,
        )

st.info(
    "Department-month task-completion targets are not compared with "
    "team-sprint actuals because their reporting grains differ. "
    "A documented mapping is needed before making that comparison."
)


# =========================================================
# 12. TARGET COVERAGE
# =========================================================
st.divider()
st.subheader("5. Target Coverage & Data Quality")

if target_filtered.empty:
    st.warning(
        "No KPI target records exist for the selected departments "
        "and period."
    )
else:
    coverage = pd.DataFrame(
        {
            "Target": [
                "Attendance",
                "Overtime share",
                "Monthly attrition",
                "Task completion",
            ],
            "Missing department-month targets": [
                int(
                    target_filtered[
                        "attendance_rate_target"
                    ].isna().sum()
                ),
                int(
                    target_filtered[
                        "overtime_share_target_pct"
                    ].isna().sum()
                ),
                int(
                    target_filtered[
                        "attrition_monthly_target_pct"
                    ].isna().sum()
                ),
                int(
                    target_filtered[
                        "task_completion_target_pct"
                    ].isna().sum()
                ),
            ],
        }
    )

    st.dataframe(
        coverage,
        use_container_width=True,
        hide_index=True,
    )

st.warning(
    "D00 has no published KPI targets in the supplied target table. "
    "D10 has missing task-completion targets. Missing targets are "
    "not treated as zero, and no substitute targets are invented."
)

st.caption(
    "Payroll is displayed at department-month level only when at least "
    "five distinct employees are present. Attrition comparisons require "
    "a group size of at least ten. Task-completion source groups require "
    "at least five eligible tasks, following the metric view's group-size "
    "filter."
)


# =========================================================
# 13. FINDINGS AND RECOMMENDATIONS
# =========================================================
st.divider()
st.subheader("6. Findings & Recommendations")

if not ranking.empty:
    highest_gross = ranking.iloc[0]

    st.markdown(
        f"""
        **Finding 1 — Department to investigate**

        **{highest_gross['department_name']}** has the highest gross
        monthly overspend in the selected period at
        **{money(highest_gross['gross_overspend'])}**.

        **Recommendation:** Review the affected months, staffing changes,
        overtime and payroll assumptions. Confirm the underlying causes
        before changing the department budget.
        """
    )

positive_months = filtered[filtered["variance"] > 0]

if not positive_months.empty:
    repeated = (
        positive_months.groupby(
            ["department_id", "department_name"],
            dropna=False,
        )
        .size()
        .sort_values(ascending=False)
    )

    department_id, department_name = repeated.index[0]
    overspend_count = int(repeated.iloc[0])

    st.markdown(
        f"""
        **Finding 2 — Recurring budget overruns**

        **{department_name}** exceeded its budget in
        **{overspend_count} month(s)** within the selected period.

        **Recommendation:** Compare those months with staffing,
        overtime and payroll planning. Adjust future budgets only
        after validating the reasons for the recurring variances.
        """
    )
else:
    st.markdown(
        """
        **Finding 2 — No overspend in the selected period**

        None of the selected department-month records has a positive
        budget variance. Continue monitoring actual costs against budget.
        """
    )

st.caption(
    "These findings identify areas for investigation; they do not prove "
    "the cause of a variance. Investigate outstanding payroll-to-ledger "
    "reconciliation exceptions separately before making financial "
    "adjustments."
)


# =========================================================
# 14. FOOTER
# =========================================================
st.divider()

st.caption(
    "PulseIQ | Budget vs Actual & KPI Targets | "
    "Sources: DuckDB metric views, payroll budget and KPI target tables"
)
