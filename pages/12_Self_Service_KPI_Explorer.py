
"""Self-Service KPI Explorer with role-based privacy controls."""

from pathlib import Path
import sys

import duckdb
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.explorer_access import (
    load_demo_users,
    get_user_access,
    get_allowed_dimensions,
)

from src.explorer_queries import (
    METRICS,
    get_approved_metrics,
    query_metric,
)


# --------------------------------------------------
# Configuration
# --------------------------------------------------

DB = ROOT / "05_Starter" / "pulseiq.duckdb"

st.set_page_config(
    page_title="Self-Service KPI Explorer | PulseIQ",
    page_icon="🔎",
    layout="wide",
)


# --------------------------------------------------
# Page Header
# --------------------------------------------------

st.title("🔎 Self-Service KPI Explorer")

st.caption(
    "Explore approved workforce KPIs with role-based access "
    "and minimum-group-size privacy protection."
)


# --------------------------------------------------
# Database Validation
# --------------------------------------------------

if not DB.exists():
    st.error("Local KPI database is unavailable.")
    st.stop()


# --------------------------------------------------
# Demo User Selection
# --------------------------------------------------

users = load_demo_users()

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
    st.sidebar.caption("Restricted to Human Resources.")

elif user.role == "MANAGER":
    st.sidebar.caption("Restricted to the assigned team.")

elif user.role == "EXECUTIVE":
    st.sidebar.caption("Company-level KPIs only.")

else:
    st.sidebar.caption("Administrator access to approved metrics.")


# --------------------------------------------------
# Database Connection
# --------------------------------------------------

con = duckdb.connect(
    str(DB),
    read_only=True,
)

try:

    # ----------------------------------------------
    # Load Approved Metrics
    # ----------------------------------------------

    approved = get_approved_metrics(con, user)

    if not approved:
        st.warning(
            "No approved KPIs are available for this role."
        )
        st.stop()

    metric_options = {
        f"{row['metric_id']} — {row['metric_name']}": row
        for row in approved
    }

    # ----------------------------------------------
    # KPI Selection
    # ----------------------------------------------

    st.subheader("Explore a KPI")

    selected_label = st.selectbox(
        "Select KPI",
        list(metric_options.keys()),
    )

    selected_metric = metric_options[selected_label]

    metric_id = selected_metric["metric_id"]

    st.caption(
        f"Definition: {selected_metric['metric_name']} · "
        f"Grain: {selected_metric['grain']} · "
        f"Unit: {selected_metric['unit']}"
    )

    # ----------------------------------------------
    # Privacy Threshold
    # ----------------------------------------------

    minimum = selected_metric["minimum_group_size"]

    threshold_unit = (
        "tasks"
        if metric_id in {"M22", "M23", "M25"}
        else "employees"
    )

    st.info(
        f"Privacy rule: groups must contain at least "
        f"{minimum} {threshold_unit}."
    )

    # ----------------------------------------------
    # Dimension Selection
    # ----------------------------------------------

    allowed_dimensions = get_allowed_dimensions(user)

    dimension = st.selectbox(
        "Select dimension",
        allowed_dimensions,
    )

    department_id = None
    team_id = None

    # ----------------------------------------------
    # Department Selection
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

            departments = con.execute("""
                SELECT department_id, department_name
                FROM raw.dim_department
                WHERE department_id <> 'D00'
                ORDER BY department_name
            """).fetchall()

            department_options = {
                f"{name} ({dept_id})": dept_id
                for dept_id, name in departments
            }

            selected_department = st.selectbox(
                "Choose department",
                list(department_options.keys()),
            )

            department_id = department_options[
                selected_department
            ]

    # ----------------------------------------------
    # Team Selection
    # ----------------------------------------------

    elif dimension == "team":

        if user.role == "MANAGER":

            team_id = user.team_id

            team_row = con.execute(
                """
                SELECT team_name
                FROM raw.dim_team
                WHERE team_id = ?
                """,
                [team_id],
            ).fetchone()

            team_name = team_row[0]

            st.text_input(
                "Team",
                value=f"{team_name} ({team_id})",
                disabled=True,
            )

        else:

            teams = con.execute("""
                SELECT team_id, team_name, department_id
                FROM raw.dim_team
                ORDER BY team_name
            """).fetchall()

            team_options = {
                f"{name} ({team_id})": team_id
                for team_id, name, dept_id in teams
            }

            selected_team = st.selectbox(
                "Choose team",
                list(team_options.keys()),
            )

            team_id = team_options[selected_team]

    # ----------------------------------------------
    # Explore KPI
    # ----------------------------------------------

    if st.button(
        "Explore KPI",
        type="primary",
    ):

        try:

            result = query_metric(
                con=con,
                user=user,
                metric_id=metric_id,
                dimension=dimension,
                department_id=department_id,
                team_id=team_id,
            )

            # --------------------------------------
            # Handle Empty Results
            # --------------------------------------

            if result.empty:

                st.warning(
                    "No data is available for this selection, "
                    "or the group does not meet the privacy threshold."
                )

            else:

                # ----------------------------------
                # Determine Value Column
                # ----------------------------------

                value_column = (
                    "metric_value"
                    if dimension == "company"
                    else METRICS[metric_id][1]
                )

                st.success(
                    f"{len(result)} approved records returned."
                )

                # ----------------------------------
                # KPI Summary
                # ----------------------------------

                selected_value = result[
                    value_column
                ].iloc[-1]

                col1, col2 = st.columns(2)

                col1.metric(
                    "Selected KPI value",
                    (
                        f"{selected_value:,.2f}"
                        if selected_value is not None
                        else "N/A"
                    ),
                )

                col2.metric(
                    "Records displayed",
                    f"{len(result):,}",
                )

                # ----------------------------------
                # KPI Visualization
                # ----------------------------------

                st.subheader("KPI Visualization")

                if dimension == "team":

                    chart = px.line(
                        result,
                        x="sprint_name",
                        y=value_column,
                        markers=True,
                        title=selected_metric["metric_name"],
                    )

                elif "month_start_date" in result.columns:

                    chart = px.line(
                        result,
                        x="month_start_date",
                        y=value_column,
                        markers=True,
                        title=selected_metric["metric_name"],
                    )

                else:

                    chart = px.bar(
                        result,
                        x="dimension_name",
                        y=value_column,
                        title=selected_metric["metric_name"],
                    )

                st.plotly_chart(
                    chart,
                    use_container_width=True,
                )

                # ----------------------------------
                # Aggregated Results
                # ----------------------------------

                st.subheader(
                    "Approved Aggregated Results"
                )

                st.dataframe(
                    result,
                    use_container_width=True,
                    hide_index=True,
                )

                # ----------------------------------
                # Privacy Information
                # ----------------------------------

                st.caption(
                    "Only aggregated records meeting the configured "
                    "privacy threshold are displayed. Individual-level "
                    "employee records are not available in this explorer."
                )

        except PermissionError as exc:

            st.error(
                f"Access denied: {exc}"
            )

        except Exception as exc:

            st.error(
                f"Unable to retrieve KPI: {exc}"
            )

finally:

    con.close()
