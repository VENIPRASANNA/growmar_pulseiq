
"""Hosted Self-Service KPI Explorer with role-based privacy controls."""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
HOSTED_DIR = ROOT / "data" / "hosted"

sys.path.insert(0, str(ROOT))

from src.explorer_access import (
    load_demo_users,
    get_user_access,
    get_allowed_dimensions,
    can_access_metric,
)


# --------------------------------------------------
# Configuration
# --------------------------------------------------

st.set_page_config(
    page_title="Self-Service KPI Explorer | PulseIQ",
    page_icon="🔎",
    layout="wide",
)

MIN_GROUP_SIZE = 10


# --------------------------------------------------
# Hosted Dataset Loading
# --------------------------------------------------

ALLOWED_DATASETS = {
    "ai_actuals_monthly",
    "workforce_monthly",
    "workforce_movements_quarterly",
    "attrition_rolling_12m",
    "payroll_monthly",
    "payroll_company_monthly",
    "attendance_monthly",
    "productivity_sprint",
    "finance_monthly",
    "receivables_summary",
}


@st.cache_data
def load_dataset(dataset_name):
    """Load an approved privacy-reviewed Parquet dataset."""

    if dataset_name not in ALLOWED_DATASETS:
        raise ValueError("Dataset is not approved.")

    dataset_path = HOSTED_DIR / f"{dataset_name}.parquet"

    if not dataset_path.is_file():
        raise FileNotFoundError(
            f"Hosted dataset is missing: {dataset_name}.parquet"
        )

    return pd.read_parquet(dataset_path)


# --------------------------------------------------
# Hosted KPI Catalog
# --------------------------------------------------

METRIC_CATALOG = {
    "M01": {
        "name": "Headcount",
        "unit": "Employees",
        "dimensions": ["company", "department"],
    },
    "M02": {
        "name": "Hires",
        "unit": "Employees",
        "dimensions": ["company"],
    },
    "M03": {
        "name": "Exits",
        "unit": "Employees",
        "dimensions": ["company"],
    },
    "M05": {
        "name": "Rolling 12-Month Attrition",
        "unit": "%",
        "dimensions": ["company"],
    },
    "M07": {
        "name": "Gross Pay",
        "unit": "Currency",
        "dimensions": ["company", "department"],
    },
    "M08": {
        "name": "Net Pay",
        "unit": "Currency",
        "dimensions": ["company", "department"],
    },
    "M09": {
        "name": "Employer Cost",
        "unit": "Currency",
        "dimensions": ["company", "department"],
    },
    "M10": {
        "name": "Cost Per Head",
        "unit": "Currency",
        "dimensions": ["department"],
    },
    "M11": {
        "name": "Overtime Share",
        "unit": "%",
        "dimensions": ["department"],
    },
    "M12": {
        "name": "Variable Pay Share",
        "unit": "%",
        "dimensions": ["department"],
    },
    "M13": {
        "name": "Attendance Rate",
        "unit": "%",
        "dimensions": ["department"],
    },
    "M14": {
        "name": "Late Arrivals per 100 Present Days",
        "unit": "Rate",
        "dimensions": ["department"],
    },
    "M16": {
        "name": "Revenue",
        "unit": "Currency",
        "dimensions": ["company"],
    },
    "M17": {
        "name": "Net Profit",
        "unit": "Currency",
        "dimensions": ["company"],
    },
    "M18": {
        "name": "Operating Margin",
        "unit": "%",
        "dimensions": ["company"],
    },
    "M19": {
        "name": "Payroll as Percentage of Revenue",
        "unit": "%",
        "dimensions": ["company"],
    },
    "M20": {
        "name": "Days Sales Outstanding",
        "unit": "Days",
        "dimensions": ["company"],
    },
    "M22": {
        "name": "Task Completion Rate",
        "unit": "%",
        "dimensions": ["team"],
    },
    "M23": {
        "name": "On-Time Delivery Rate",
        "unit": "%",
        "dimensions": ["team"],
    },
    "M24": {
        "name": "Completed Story Points",
        "unit": "Story Points",
        "dimensions": ["team"],
    },
    "M25": {
        "name": "Average Cycle Time",
        "unit": "Days",
        "dimensions": ["team"],
    },
}


# --------------------------------------------------
# KPI Query Function
# --------------------------------------------------

def query_hosted_metric(
    metric_id,
    dimension,
    department_id=None,
    team_id=None,
):
    """Retrieve an approved aggregate KPI from hosted Parquet data."""

    result = None
    value_column = None
    sort_column = None

    # ----------------------------------------------
    # M01: Headcount
    # ----------------------------------------------

    if metric_id == "M01":

        if dimension == "company":
            result = load_dataset("ai_actuals_monthly")

            value_column = "actual_headcount"
            sort_column = "month_start_date"

        else:
            result = load_dataset("workforce_monthly")

            result = result[
                (result["department_id"] == department_id)
                & (result["department_id"] != "D00")
                & (result["group_size"] >= MIN_GROUP_SIZE)
            ].copy()

            value_column = "headcount"
            sort_column = "month_start_date"

    # ----------------------------------------------
    # M02 and M03: Quarterly Workforce Movements
    # ----------------------------------------------

    elif metric_id in {"M02", "M03"}:

        result = load_dataset("workforce_movements_quarterly")

        value_column = (
            "hires" if metric_id == "M02" else "exits"
        )

        sort_column = "quarter"

    # ----------------------------------------------
    # M05: Rolling Attrition
    # ----------------------------------------------

    elif metric_id == "M05":

        result = load_dataset("attrition_rolling_12m")

        value_column = "attrition_rate_12m_pct"
        sort_column = "month_start_date"

    # ----------------------------------------------
    # M07-M12: Payroll
    # ----------------------------------------------

    elif metric_id in {
        "M07", "M08", "M09", "M10", "M11", "M12"
    }:

        if dimension == "department":

            result = load_dataset("payroll_monthly")

            result = result[
                (result["department_id"] == department_id)
                & (result["department_id"] != "D00")
                & (result["employee_count"] >= MIN_GROUP_SIZE)
            ].copy()

        else:

            result = load_dataset("payroll_company_monthly")

        value_columns = {
            "M07": "gross_pay",
            "M08": "net_pay",
            "M09": "employer_cost",
            "M10": "cost_per_head",
            "M11": "overtime_share_pct",
            "M12": "variable_pay_share_pct",
        }

        value_column = value_columns[metric_id]
        sort_column = "month_start_date"

    # ----------------------------------------------
    # M13 and M14: Attendance
    # ----------------------------------------------

    elif metric_id in {"M13", "M14"}:

        result = load_dataset("attendance_monthly")

        result = result[
            (result["department_id"] == department_id)
            & (result["department_id"] != "D00")
            & (result["employee_count"] >= MIN_GROUP_SIZE)
        ].copy()

        value_column = (
            "attendance_rate_pct"
            if metric_id == "M13"
            else "late_arrivals_per_100_present_days"
        )

        sort_column = "month_start_date"

    # ----------------------------------------------
    # M16-M19: Financial Performance
    # ----------------------------------------------

    elif metric_id in {"M16", "M17", "M18", "M19"}:

        result = load_dataset("finance_monthly")

        value_columns = {
            "M16": "revenue",
            "M17": "net_profit",
            "M18": "operating_margin_pct",
            "M19": "payroll_pct_revenue",
        }

        value_column = value_columns[metric_id]
        sort_column = "month_start_date"

    # ----------------------------------------------
    # M20: Days Sales Outstanding
    # ----------------------------------------------

    elif metric_id == "M20":

        result = load_dataset("receivables_summary")

        value_column = "dso_days"
        sort_column = "report_date"

    # ----------------------------------------------
    # M22-M25: Team Productivity
    # ----------------------------------------------

    elif metric_id in {"M22", "M23", "M24", "M25"}:

        result = load_dataset("productivity_sprint")

        result = result[
            (result["team_id"] == team_id)
            & (result["group_size"] >= MIN_GROUP_SIZE)
        ].copy()

        value_columns = {
            "M22": "task_completion_rate_pct",
            "M23": "on_time_delivery_rate_pct",
            "M24": "completed_story_points",
            "M25": "average_cycle_time_days",
        }

        value_column = value_columns[metric_id]
        sort_column = "start_date"

    else:
        raise ValueError(
            "The selected KPI is not supported by hosted datasets."
        )

    if result is None or result.empty:
        return pd.DataFrame()

    if value_column not in result.columns:
        raise ValueError(
            f"Required KPI column '{value_column}' is unavailable."
        )

    # Convert the selected KPI to numeric.
    result = result.copy()

    result["metric_value"] = pd.to_numeric(
        result[value_column],
        errors="coerce",
    )

    result = result.dropna(
        subset=["metric_value"]
    )

    if result.empty:
        return pd.DataFrame()

    # Sort using actual date values before creating chart labels.
    if sort_column and sort_column in result.columns:
        result = result.sort_values(sort_column)

        result["period_label"] = (
            result[sort_column].astype(str)
        )
    else:
        result["period_label"] = "Current"

    # Display organizational scope.
    if (
        dimension == "department"
        and "department_name" in result.columns
    ):
        result["dimension_name"] = result["department_name"]

    elif (
        dimension == "team"
        and "team_name" in result.columns
    ):
        result["dimension_name"] = result["team_name"]

    else:
        result["dimension_name"] = "Company"

    return result.reset_index(drop=True)


# --------------------------------------------------
# Page Header
# --------------------------------------------------

st.title("🔎 Self-Service KPI Explorer")

st.caption(
    "Explore approved workforce, payroll and productivity KPIs "
    "using privacy-reviewed hosted aggregate datasets."
)


# --------------------------------------------------
# Demo User Selection
# --------------------------------------------------

try:
    users = load_demo_users()

    if not users:
        st.error("No demo users are configured.")
        st.stop()

except Exception as exc:
    st.error(f"Unable to load demo users: {exc}")
    st.stop()


with st.sidebar:

    st.header("Demo Access")

    st.caption(
        "Demonstration role selector — not production authentication."
    )

    username = st.selectbox(
        "Select demo user",
        list(users.keys()),
    )


user = get_user_access(username)

st.sidebar.success(f"Role: {user.role}")

if user.role == "HR":
    st.sidebar.caption("Restricted to Human Resources (D07).")

elif user.role == "MANAGER":
    st.sidebar.caption("Restricted to assigned team (T08).")

elif user.role == "EXECUTIVE":
    st.sidebar.caption("Company-level KPIs only.")

else:
    st.sidebar.caption(
        "Administrator access to approved metrics."
    )


# --------------------------------------------------
# Dimension Selection
# --------------------------------------------------

allowed_dimensions = get_allowed_dimensions(user)

if not allowed_dimensions:
    st.warning("No dimensions are available for this role.")
    st.stop()


st.subheader("Explore a KPI")

dimension = st.selectbox(
    "Select dimension",
    allowed_dimensions,
)


# --------------------------------------------------
# Department and Team Scope
# --------------------------------------------------

department_id = None
team_id = None

try:

    # ----------------------------------------------
    # Department selection
    # ----------------------------------------------

    if dimension == "department":

        if user.role == "HR":

            department_id = user.department_id

            st.text_input(
                "Department",
                value="Human Resources (D07)",
                disabled=True,
            )

        else:

            departments = load_dataset("workforce_monthly")

            departments = departments[
                (departments["department_id"] != "D00")
                & (departments["group_size"] >= MIN_GROUP_SIZE)
            ]

            departments = (
                departments[
                    ["department_id", "department_name"]
                ]
                .drop_duplicates()
                .sort_values("department_name")
            )

            department_options = {
                f"{row.department_name} ({row.department_id})":
                row.department_id
                for row in departments.itertuples()
            }

            if not department_options:
                st.warning(
                    "No privacy-approved departments are available."
                )
                st.stop()

            selected_department = st.selectbox(
                "Choose department",
                list(department_options.keys()),
            )

            department_id = department_options[
                selected_department
            ]

    # ----------------------------------------------
    # Team selection
    # ----------------------------------------------

    elif dimension == "team":

        teams = load_dataset("productivity_sprint")

        teams = teams[
            teams["group_size"] >= MIN_GROUP_SIZE
        ]

        teams = (
            teams[["team_id", "team_name"]]
            .drop_duplicates()
            .sort_values("team_name")
        )

        if user.role == "MANAGER":

            team_id = user.team_id

            matching_team = teams[
                teams["team_id"] == team_id
            ]

            if matching_team.empty:
                st.warning(
                    "No privacy-approved data is available "
                    "for the assigned team."
                )
                st.stop()

            team_name = matching_team.iloc[0]["team_name"]

            st.text_input(
                "Team",
                value=f"{team_name} ({team_id})",
                disabled=True,
            )

        else:

            team_options = {
                f"{row.team_name} ({row.team_id})":
                row.team_id
                for row in teams.itertuples()
            }

            if not team_options:
                st.warning(
                    "No privacy-approved teams are available."
                )
                st.stop()

            selected_team = st.selectbox(
                "Choose team",
                list(team_options.keys()),
            )

            team_id = team_options[selected_team]

except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()

except Exception as exc:
    st.error(f"Unable to load organizational scope: {exc}")
    st.stop()


# --------------------------------------------------
# KPI Selection Based on Role and Dimension
# --------------------------------------------------

available_metrics = {}

for metric_id, details in METRIC_CATALOG.items():

    role_allowed = can_access_metric(user, metric_id)

    dimension_allowed = (
        dimension in details["dimensions"]
    )

    if role_allowed and dimension_allowed:
        available_metrics[metric_id] = details


if not available_metrics:

    st.warning(
        "No hosted KPIs are available for this role "
        "and selected dimension."
    )
    st.stop()


metric_options = {
    f"{metric_id} — {details['name']}": metric_id
    for metric_id, details in available_metrics.items()
}

selected_label = st.selectbox(
    "Select KPI",
    list(metric_options.keys()),
)

metric_id = metric_options[selected_label]

selected_metric = METRIC_CATALOG[metric_id]


st.caption(
    f"Metric: {selected_metric['name']} · "
    f"Unit: {selected_metric['unit']} · "
    f"Dimension: {dimension.title()}"
)


# --------------------------------------------------
# Privacy Information
# --------------------------------------------------

st.info(
    "Privacy rule: Department and team datasets are "
    "pre-filtered using a minimum approved group size of 10. "
    "The Explorer also applies the available group-size "
    "checks before displaying results."
)


# --------------------------------------------------
# Explore KPI
# --------------------------------------------------

if st.button(
    "Explore KPI",
    type="primary",
):

    try:

        result = query_hosted_metric(
            metric_id=metric_id,
            dimension=dimension,
            department_id=department_id,
            team_id=team_id,
        )

        if result.empty:

            st.warning(
                "No approved data is available for this selection. "
                "The records may be unavailable or suppressed "
                "by the privacy threshold."
            )

        else:

            latest_value = result["metric_value"].iloc[-1]

            # --------------------------------------
            # KPI Summary
            # --------------------------------------

            if selected_metric["unit"] == "Currency":
                display_value = f"₹{latest_value:,.2f}"

            elif selected_metric["unit"] == "%":
                display_value = f"{latest_value:,.2f}%"

            elif selected_metric["unit"] == "Employees":
                display_value = f"{latest_value:,.0f}"

            else:
                display_value = (
                    f"{latest_value:,.2f} "
                    f"{selected_metric['unit']}"
                )

            st.success(
                f"{len(result)} approved aggregate records returned."
            )

            col1, col2 = st.columns(2)

            col1.metric(
                "Latest KPI Value",
                display_value,
            )

            col2.metric(
                "Records Displayed",
                f"{len(result):,}",
            )

            # --------------------------------------
            # KPI Visualization
            # --------------------------------------

            st.subheader("KPI Visualization")

            if len(result) > 1:

                chart = px.line(
                    result,
                    x="period_label",
                    y="metric_value",
                    markers=True,
                    title=selected_metric["name"],
                )

            else:

                chart = px.bar(
                    result,
                    x="period_label",
                    y="metric_value",
                    title=selected_metric["name"],
                )

            chart.update_layout(
                xaxis_title="Reporting Period",
                yaxis_title=selected_metric["unit"],
            )

            st.plotly_chart(
                chart,
                use_container_width=True,
            )

            # --------------------------------------
            # Aggregated Results
            # --------------------------------------

            st.subheader(
                "Approved Aggregated Results"
            )

            display_columns = [
                column
                for column in [
                    "period_label",
                    "dimension_name",
                    "metric_value",
                ]
                if column in result.columns
            ]

            display_result = result[
                display_columns
            ].rename(
                columns={
                    "period_label": "Reporting Period",
                    "dimension_name": "Organizational Scope",
                    "metric_value": "KPI Value",
                }
            )

            st.dataframe(
                display_result,
                use_container_width=True,
                hide_index=True,
            )

            # --------------------------------------
            # Privacy Notice
            # --------------------------------------

            st.caption(
                "Only approved aggregate datasets are displayed. "
                "Individual employee records and sensitive identifiers "
                "are not available in this Explorer."
            )

    except PermissionError as exc:

        st.error(f"Access denied: {exc}")

    except FileNotFoundError as exc:

        st.error(str(exc))

    except Exception as exc:

        st.error(f"Unable to retrieve KPI: {exc}")
