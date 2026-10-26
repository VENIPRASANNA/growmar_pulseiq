from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


# =========================================================
# CONFIGURATION
# =========================================================

DB = (
    Path(__file__).resolve().parents[1]
    / "05_Starter"
    / "pulseiq.duckdb"
)

MIN_GROUP_SIZE = 10

st.set_page_config(
    page_title="Attrition Analytics",
    page_icon="📊",
    layout="wide",
)

st.title("Attrition Analytics")
st.caption(
    "Actual employee exits, tenure at exit, and separately labelled "
    "predicted attrition risk."
)


# =========================================================
# LOAD DATA FROM DUCKDB METRIC VIEWS
# =========================================================

@st.cache_data
def load_data():
    con = duckdb.connect(str(DB), read_only=True)

    try:
        exits = con.execute("""
            SELECT
                v.month_start_date,
                v.department_id,
                d.department_name,
                v.exits,
                v.group_size
            FROM metrics.m03_exits v
            LEFT JOIN raw.dim_department d
                ON d.department_id = v.department_id
            ORDER BY v.month_start_date
        """).fetchdf()

        monthly = con.execute("""
            SELECT
                v.month_start_date,
                v.department_id,
                d.department_name,
                v.exits,
                v.headcount_start,
                v.attrition_rate_pct,
                v.group_size
            FROM metrics.m04_attrition_monthly v
            LEFT JOIN raw.dim_department d
                ON d.department_id = v.department_id
            ORDER BY v.month_start_date
        """).fetchdf()

        rolling = con.execute("""
            SELECT
                v.month_start_date,
                v.department_id,
                d.department_name,
                v.exits_12m,
                v.avg_headcount_12m,
                v.attrition_rate_12m_pct,
                v.group_size
            FROM metrics.m05_attrition_rolling_12m v
            LEFT JOIN raw.dim_department d
                ON d.department_id = v.department_id
            ORDER BY v.month_start_date
        """).fetchdf()

        voluntary = con.execute("""
            SELECT
                v.month_start_date,
                v.department_id,
                d.department_name,
                v.voluntary_exits_12m,
                v.avg_headcount_12m,
                v.voluntary_attrition_rate_pct,
                v.group_size
            FROM metrics.m06_voluntary_attrition_rate v
            LEFT JOIN raw.dim_department d
                ON d.department_id = v.department_id
            ORDER BY v.month_start_date
        """).fetchdf()

        risk = con.execute("""
            SELECT
                r.as_of_date,
                r.department_id,
                d.department_name,
                COUNT(DISTINCT r.employee_id) AS employees_scored,
                COUNT(DISTINCT CASE
                    WHEN LOWER(r.risk_band) = 'high'
                    THEN r.employee_id
                END) AS high_risk_employees,
                ROUND(
                    100.0 * COUNT(DISTINCT CASE
                        WHEN LOWER(r.risk_band) = 'high'
                        THEN r.employee_id
                    END)
                    / NULLIF(COUNT(DISTINCT r.employee_id), 0),
                    2
                ) AS high_risk_share_pct
            FROM raw.fact_attrition_risk r
            LEFT JOIN raw.dim_department d
                ON d.department_id = r.department_id
            GROUP BY
                r.as_of_date,
                r.department_id,
                d.department_name
            HAVING COUNT(DISTINCT r.employee_id) >= 10
            ORDER BY r.as_of_date
        """).fetchdf()

        tenure = con.execute("""
            SELECT
                department_id,
                hire_date,
                exit_date,
                DATE_DIFF(
                    'day',
                    CAST(hire_date AS DATE),
                    CAST(exit_date AS DATE)
                ) / 365.25 AS tenure_years
            FROM raw.dim_employee
            WHERE exit_date IS NOT NULL
              AND hire_date IS NOT NULL
              AND CAST(exit_date AS DATE) >= CAST(hire_date AS DATE)
        """).fetchdf()

        departments = con.execute("""
            SELECT department_id, department_name
            FROM raw.dim_department
        """).fetchdf()

        return (
            exits,
            monthly,
            rolling,
            voluntary,
            risk,
            tenure,
            departments,
        )

    finally:
        con.close()


try:
    (
        exits,
        monthly,
        rolling,
        voluntary,
        risk,
        tenure,
        departments,
    ) = load_data()

except Exception as exc:
    st.error(f"Unable to load attrition data: {exc}")
    st.stop()


# =========================================================
# NORMALISE DATES
# =========================================================

for frame in (exits, monthly, rolling, voluntary):
    if "month_start_date" in frame.columns:
        frame["month_start_date"] = pd.to_datetime(
            frame["month_start_date"]
        )

if not risk.empty:
    risk["as_of_date"] = pd.to_datetime(risk["as_of_date"])

if not tenure.empty:
    tenure["hire_date"] = pd.to_datetime(tenure["hire_date"])
    tenure["exit_date"] = pd.to_datetime(tenure["exit_date"])


# =========================================================
# SIDEBAR FILTERS
# =========================================================

if monthly.empty:
    st.warning("No monthly attrition data is available.")
    st.stop()

with st.sidebar:
    st.header("Filters")

    available_departments = sorted(
        monthly["department_name"].dropna().unique().tolist()
    )

    selected_departments = st.multiselect(
        "Department",
        available_departments,
        default=available_departments,
    )

    available_months = sorted(
        monthly["month_start_date"].dropna().unique()
    )

    first_month = pd.Timestamp(available_months[0]).date()
    last_month = pd.Timestamp(available_months[-1]).date()

    selected_range = st.date_input(
        "Actual attrition date range",
        value=(first_month, last_month),
        min_value=first_month,
        max_value=last_month,
    )


if not selected_departments:
    st.warning("Select at least one department.")
    st.stop()

if not isinstance(selected_range, (tuple, list)) or len(selected_range) != 2:
    st.info("Select both a start date and an end date.")
    st.stop()

start_month = pd.Timestamp(selected_range[0]).to_period("M").to_timestamp()
end_month = pd.Timestamp(selected_range[1]).to_period("M").to_timestamp()


def filter_actual(frame):
    return frame[
        frame["department_name"].isin(selected_departments)
        & frame["month_start_date"].between(start_month, end_month)
    ].copy()


exits_f = filter_actual(exits)
monthly_f = filter_actual(monthly)
rolling_f = filter_actual(rolling)
voluntary_f = filter_actual(voluntary)

if monthly_f.empty:
    st.warning("No attrition records match the selected filters.")
    st.stop()


# =========================================================
# SECTION 1: ACTUAL ATTRITION
# =========================================================

st.header("1. Actual attrition")

st.caption(
    "Historical outcomes, not predictions. Monthly attrition is exits "
    "divided by beginning headcount, using the governed metric."
)

monthly_summary = (
    monthly_f.groupby("month_start_date", as_index=False)
    .agg(
        exits=("exits", "sum"),
        headcount_start=("headcount_start", "sum"),
    )
    .sort_values("month_start_date")
)

monthly_summary["attrition_rate_pct"] = (
    100
    * monthly_summary["exits"]
    / monthly_summary["headcount_start"].replace(0, float("nan"))
)

latest_month = monthly_f["month_start_date"].max()

latest_data = monthly_f[
    monthly_f["month_start_date"] == latest_month
]

latest_exits = int(latest_data["exits"].sum())
latest_headcount = latest_data["headcount_start"].sum()

latest_rate = (
    100 * latest_exits / latest_headcount
    if latest_headcount > 0
    else 0
)

total_exits = int(monthly_f["exits"].sum())

c1, c2, c3 = st.columns(3)

c1.metric("Exits in selected period", f"{total_exits:,}")
c2.metric(f"Exits in {latest_month:%b %Y}", f"{latest_exits:,}")
c3.metric(f"Attrition in {latest_month:%b %Y}", f"{latest_rate:.2f}%")


left, right = st.columns(2)

with left:
    st.subheader("Monthly exits")

    fig = px.bar(
        monthly_summary,
        x="month_start_date",
        y="exits",
        labels={
            "month_start_date": "Month",
            "exits": "Employee exits",
        },
    )

    fig.update_layout(template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Monthly attrition rate")

    fig = px.line(
        monthly_summary,
        x="month_start_date",
        y="attrition_rate_pct",
        markers=True,
        labels={
            "month_start_date": "Month",
            "attrition_rate_pct": "Attrition rate (%)",
        },
    )

    fig.update_layout(template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)


# =========================================================
# SECTION 2: ATTRITION BY DEPARTMENT
# =========================================================

st.header("2. Attrition by department")

st.caption(
    f"Department comparison for the latest month in the selected range: "
    f"{latest_month:%B %Y}. Rates are not averaged across different months."
)

latest_department_data = monthly_f[
    monthly_f["month_start_date"] == latest_month
].copy()

department_summary = (
    latest_department_data.groupby("department_name", as_index=False)
    .agg(
        exits=("exits", "sum"),
        headcount_start=("headcount_start", "sum"),
        group_size=("group_size", "max"),
    )
)

department_summary["attrition_rate_pct"] = (
    100
    * department_summary["exits"]
    / department_summary["headcount_start"].replace(0, float("nan"))
)

department_summary = department_summary[
    (department_summary["group_size"] >= MIN_GROUP_SIZE)
    & (department_summary["headcount_start"] > 0)
].sort_values("attrition_rate_pct", ascending=True)

if not department_summary.empty:
    fig = px.bar(
        department_summary,
        x="attrition_rate_pct",
        y="department_name",
        orientation="h",
        text="attrition_rate_pct",
        hover_data=["exits", "headcount_start"],
        labels={
            "attrition_rate_pct": "Attrition rate (%)",
            "department_name": "Department",
            "exits": "Exits",
            "headcount_start": "Beginning headcount",
        },
    )

    fig.update_traces(
        texttemplate="%{text:.2f}%",
        textposition="outside",
        cliponaxis=False,
    )

    fig.update_layout(template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        department_summary[
            [
                "department_name",
                "exits",
                "headcount_start",
                "attrition_rate_pct",
                "group_size",
            ]
        ].round(2),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info(
        "No departments meet the minimum group-size rule for the latest month."
    )

st.caption(
    f"Departments with group sizes below {MIN_GROUP_SIZE} are excluded "
    "from this comparison."
)


# =========================================================
# SECTION 3: VOLUNTARY VERSUS OTHER EXITS
# =========================================================

st.header("3. Voluntary versus other exits")

st.caption(
    "Voluntary attrition uses a rolling 12-month metric. Do not compare "
    "this directly with a single month's attrition rate."
)

if not voluntary_f.empty:
    voluntary_summary = (
        voluntary_f.groupby("department_name", as_index=False)
        .agg(
            voluntary_exits_12m=("voluntary_exits_12m", "max"),
            voluntary_attrition_rate_pct=(
                "voluntary_attrition_rate_pct",
                "mean",
            ),
            group_size=("group_size", "max"),
        )
    )

    voluntary_summary = voluntary_summary[
        voluntary_summary["group_size"] >= MIN_GROUP_SIZE
    ]

    st.dataframe(
        voluntary_summary[
            [
                "department_name",
                "voluntary_exits_12m",
                "voluntary_attrition_rate_pct",
            ]
        ].round(2),
        use_container_width=True,
        hide_index=True,
    )

    with duckdb.connect(str(DB), read_only=True) as con:
        exit_type_data = con.execute("""
            SELECT
                h.month_start_date,
                d.department_name,
                SUM(h.exits) AS exits,
                SUM(h.voluntary_exits) AS voluntary_exits,
                SUM(h.exits - h.voluntary_exits) AS other_exits
            FROM raw.fact_headcount_monthly h
            LEFT JOIN raw.dim_department d
                ON d.department_id = h.department_id
            WHERE h.department_id != 'D00'
            GROUP BY h.month_start_date, d.department_name
            ORDER BY h.month_start_date
        """).fetchdf()

    exit_type_data["month_start_date"] = pd.to_datetime(
        exit_type_data["month_start_date"]
    )

    exit_type_data = exit_type_data[
        exit_type_data["department_name"].isin(selected_departments)
        & exit_type_data["month_start_date"].between(
            start_month, end_month
        )
    ]

    exit_type_summary = (
        exit_type_data.groupby("month_start_date", as_index=False)
        .agg(
            voluntary_exits=("voluntary_exits", "sum"),
            other_exits=("other_exits", "sum"),
        )
        .sort_values("month_start_date")
    )

    if not exit_type_summary.empty:
        exit_type_long = exit_type_summary.melt(
            id_vars="month_start_date",
            value_vars=["voluntary_exits", "other_exits"],
            var_name="exit_type",
            value_name="exits",
        )

        fig = px.bar(
            exit_type_long,
            x="month_start_date",
            y="exits",
            color="exit_type",
            barmode="stack",
            labels={
                "month_start_date": "Month",
                "exits": "Exits",
                "exit_type": "Exit category",
            },
        )

        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No rolling 12-month voluntary attrition records match the filters.")


# =========================================================
# SECTION 4: TENURE AT EXIT
# =========================================================

st.header("4. Tenure at exit")

st.caption(
    "Tenure is calculated from hire date to recorded exit date. "
    "It describes employees who exited; it does not predict future exits."
)

tenure_f = tenure.merge(
    departments,
    on="department_id",
    how="left",
)

tenure_f = tenure_f[
    tenure_f["department_name"].isin(selected_departments)
    & tenure_f["exit_date"].between(
        pd.Timestamp(start_month),
        pd.Timestamp(end_month) + pd.offsets.MonthEnd(0),
    )
].copy()

if not tenure_f.empty:
    tenure_f["tenure_years"] = pd.to_numeric(
        tenure_f["tenure_years"],
        errors="coerce",
    )

    tenure_f = tenure_f[
        tenure_f["tenure_years"].notna()
        & (tenure_f["tenure_years"] >= 0)
    ]

    tenure_summary = (
        tenure_f.groupby("department_name", as_index=False)
        .agg(
            exited_employees=("tenure_years", "size"),
            median_tenure_years=("tenure_years", "median"),
        )
    )

    tenure_summary = tenure_summary[
        tenure_summary["exited_employees"] >= MIN_GROUP_SIZE
    ].sort_values("median_tenure_years")

    if not tenure_summary.empty:
        fig = px.bar(
            tenure_summary,
            x="median_tenure_years",
            y="department_name",
            orientation="h",
            hover_data=["exited_employees"],
            labels={
                "median_tenure_years": "Median tenure at exit (years)",
                "department_name": "Department",
                "exited_employees": "Exited employees",
            },
        )

        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            tenure_summary.round(2),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "No department has enough exited employees for a privacy-safe "
            "tenure summary."
        )
else:
    st.info("No exit-tenure records match the selected filters.")


# =========================================================
# SECTION 5: PREDICTED ATTRITION RISK
# =========================================================

st.header("5. Predicted attrition risk")

st.warning(
    "**Prediction, not certainty:** risk bands are model estimates. "
    "They do not mean an employee will definitely leave. Use these "
    "group summaries for supportive workforce planning, not individual "
    "employment decisions."
)

if not risk.empty:
    latest_risk_date = risk["as_of_date"].max()

    risk_latest = risk[
        (risk["as_of_date"] == latest_risk_date)
        & (risk["department_name"].isin(selected_departments))
        & (risk["employees_scored"] >= MIN_GROUP_SIZE)
    ].copy()

    if not risk_latest.empty:
        st.caption(
            f"Latest prediction snapshot: {latest_risk_date:%d %B %Y}"
        )

        risk_latest = risk_latest.sort_values("high_risk_share_pct")

        fig = px.bar(
            risk_latest,
            x="high_risk_share_pct",
            y="department_name",
            orientation="h",
            text="high_risk_share_pct",
            hover_data=["employees_scored", "high_risk_employees"],
            labels={
                "high_risk_share_pct": "High-risk share (%)",
                "department_name": "Department",
                "employees_scored": "Employees scored",
                "high_risk_employees": "Employees in high-risk band",
            },
        )

        fig.update_traces(
            texttemplate="%{text:.2f}%",
            textposition="outside",
            cliponaxis=False,
        )

        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            risk_latest[
                [
                    "department_name",
                    "employees_scored",
                    "high_risk_employees",
                    "high_risk_share_pct",
                ]
            ].round(2),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "No departments meet the minimum group-size rule in the "
            "latest prediction snapshot."
        )
else:
    st.info("No predicted attrition-risk data is available.")


# =========================================================
# SECTION 6: THREE NUMERICAL FINDINGS
# =========================================================

st.header("6. Key findings")

if not monthly_summary.empty:
    peak = monthly_summary.loc[
        monthly_summary["attrition_rate_pct"].idxmax()
    ]

    st.markdown("**Finding 1 — Highest monthly attrition**")
    st.write(
        f"{peak['month_start_date']:%B %Y} had the highest monthly "
        f"attrition rate in the selected period: "
        f"{peak['attrition_rate_pct']:.2f}%, with "
        f"{int(peak['exits'])} exits."
    )

    lowest = monthly_summary.loc[
        monthly_summary["attrition_rate_pct"].idxmin()
    ]

    st.markdown("**Finding 2 — Lowest monthly attrition**")
    st.write(
        f"{lowest['month_start_date']:%B %Y} had the lowest monthly "
        f"attrition rate: {lowest['attrition_rate_pct']:.2f}%, with "
        f"{int(lowest['exits'])} exits."
    )

    if not department_summary.empty:
        top_department = department_summary.loc[
            department_summary["attrition_rate_pct"].idxmax()
        ]

        st.markdown("**Finding 3 — Department requiring review**")
        st.write(
            f"In {latest_month:%B %Y}, "
            f"{top_department['department_name']} had the highest "
            f"displayed department attrition rate: "
            f"{top_department['attrition_rate_pct']:.2f}%, with "
            f"{int(top_department['exits'])} exits from a beginning "
            f"headcount of {int(top_department['headcount_start'])}."
        )
    else:
        st.info(
            "No department-level finding is available under the current "
            "minimum group-size rule."
        )


# =========================================================
# METHODOLOGY AND PRIVACY
# =========================================================

st.divider()

st.subheader("Methodology and privacy")

st.markdown(
    f"""
- **Monthly attrition:** exits divided by beginning headcount, using
  the existing governed monthly metric.
- **Department comparison:** latest available month, rather than an
  average of monthly rates.
- **Rolling 12-month metrics:** reported separately from single-month
  attrition rates.
- **Predicted risk:** a model estimate, not a confirmed future exit.
- **Privacy:** group summaries only; groups smaller than
  {MIN_GROUP_SIZE} are excluded from relevant summaries.
- **Interpretation:** a high rate identifies an area to investigate;
  it does not establish why employees left.
"""
)