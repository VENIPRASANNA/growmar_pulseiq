
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

DB = Path(__file__).parent / "05_Starter" / "pulseiq.duckdb"
HOSTED_DIR = Path(__file__).parent / "data" / "hosted"
HOSTED_MODE = not DB.exists()

st.set_page_config(
    page_title="PulseIQ Workforce",
    page_icon="📊",
    layout="wide"
)

st.title("PulseIQ | Workforce Overview")
st.caption(
    "Governed workforce metrics · Monthly headcount "
    "and quarterly workforce movements"
)


@st.cache_data
def load_data():
    if HOSTED_MODE:
        headcount = pd.read_parquet(
            HOSTED_DIR / "workforce_monthly.parquet"
        )

        movements = pd.read_parquet(
            HOSTED_DIR / "workforce_movements_quarterly.parquet"
        )

        movements["quarter"] = pd.to_datetime(
            movements["quarter"]
        )

        hires = movements[["quarter", "hires"]].copy()
        exits = movements[["quarter", "exits"]].copy()

        return headcount, hires, exits

    con = duckdb.connect(str(DB), read_only=True)

    try:
        headcount = con.execute("""
            SELECT month_start_date, department_id,
                   department_name, headcount
            FROM metrics.m29_department_headcount
            ORDER BY month_start_date
        """).fetchdf()

        hires = con.execute("""
            SELECT month_start_date, department_id, hires
            FROM metrics.m02_hires
        """).fetchdf()

        exits = con.execute("""
            SELECT month_start_date, department_id, exits
            FROM metrics.m03_exits
        """).fetchdf()

        return headcount, hires, exits

    finally:
        con.close()


# Load dashboard data
try:
    headcount, hires, exits = load_data()

except Exception as exc:
    st.error(f"Could not load dashboard metric views: {exc}")
    st.stop()


# Convert date columns
headcount["month_start_date"] = pd.to_datetime(
    headcount["month_start_date"]
)

if HOSTED_MODE:
    hires["quarter"] = pd.to_datetime(hires["quarter"])
    exits["quarter"] = pd.to_datetime(exits["quarter"])

else:
    hires["month_start_date"] = pd.to_datetime(
        hires["month_start_date"]
    )

    exits["month_start_date"] = pd.to_datetime(
        exits["month_start_date"]
    )


# Sidebar filters
with st.sidebar:
    st.header("Filters")

    departments = sorted(
        headcount["department_name"].dropna().unique()
    )

    selected = st.multiselect(
        "Department",
        departments,
        default=departments
    )

    min_date = headcount["month_start_date"].min().date()
    max_date = headcount["month_start_date"].max().date()

    dates = st.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )


# Apply department filter to headcount
df = headcount[
    headcount["department_name"].isin(selected)
].copy()


# Apply date filter to headcount
if isinstance(dates, (tuple, list)) and len(dates) == 2:
    start = pd.Timestamp(dates[0])
    end = pd.Timestamp(dates[1])

    df = df[
        df["month_start_date"].between(start, end)
    ]


if df.empty:
    st.warning(
        "No results for these filters. "
        "Please select another date range or department."
    )
    st.stop()


# Monthly headcount calculations
monthly = (
    df.groupby("month_start_date", as_index=False)["headcount"]
    .sum()
    .sort_values("month_start_date")
)

latest_month = monthly.iloc[-1]["month_start_date"]

latest = int(monthly.iloc[-1]["headcount"])
first = int(monthly.iloc[0]["headcount"])

change = latest - first
change_pct = change / first * 100 if first else 0


# Hires and exits calculations
if HOSTED_MODE:

    # Hosted data contains company-wide quarterly totals.
    h = hires.copy()
    e = exits.copy()

    if isinstance(dates, (tuple, list)) and len(dates) == 2:

        # Include quarters that overlap the selected date range.
        quarter_end = (
            h["quarter"]
            + pd.DateOffset(months=3)
            - pd.Timedelta(days=1)
        )

        movement_mask = (
            (h["quarter"] <= end)
            & (quarter_end >= start)
        )

        h = h.loc[movement_mask].copy()
        e = e.loc[movement_mask].copy()

else:

    # Local data retains department-level monthly movements.
    dept_ids = df["department_id"].unique()

    h = hires[
        hires["department_id"].isin(dept_ids)
    ]

    e = exits[
        exits["department_id"].isin(dept_ids)
    ]

    if isinstance(dates, (tuple, list)) and len(dates) == 2:
        h = h[
            h["month_start_date"].between(start, end)
        ]

        e = e[
            e["month_start_date"].between(start, end)
        ]


# KPI cards
a, b, c, d = st.columns(4)

a.metric(
    "Latest headcount",
    f"{latest:,}",
    latest_month.strftime("%b %Y")
)

b.metric(
    "Net change",
    f"{change:+,}",
    f"{change_pct:+.1f}%"
)

c.metric(
    "Company-wide hires (quarterly)"
    if HOSTED_MODE else "Hires in period",
    f"{int(h['hires'].sum()):,}"
)

d.metric(
    "Company-wide exits (quarterly)"
    if HOSTED_MODE else "Exits in period",
    f"{int(e['exits'].sum()):,}"
)


# Hosted data disclosure
if HOSTED_MODE:
    st.caption(
        "Hosted data privacy note: hires and exits are "
        "company-wide quarterly totals. The selected date "
        "range includes quarters that overlap the selected "
        "period. Department-level movement breakdowns are "
        "not published. Department filters apply to headcount, "
        "not company-wide movement totals."
    )


# Headcount trend
st.subheader("Headcount trend")

fig = px.line(
    monthly,
    x="month_start_date",
    y="headcount",
    markers=True,
    labels={
        "month_start_date": "Month",
        "headcount": "Employees"
    }
)

fig.update_traces(line_color="#247BA0")
fig.update_layout(template="plotly_white")

st.plotly_chart(
    fig,
    use_container_width=True
)

st.caption(
    f"Insight: headcount changed by {change:+,} "
    f"({change_pct:+.1f}%) from "
    f"{monthly.iloc[0]['month_start_date']:%b %Y} "
    f"to {latest_month:%b %Y}."
)


# Department workforce
st.subheader("Department workforce")

dept = (
    df[df["month_start_date"].eq(latest_month)]
    .groupby("department_name", as_index=False)["headcount"]
    .sum()
    .sort_values("headcount")
)

fig2 = px.bar(
    dept,
    x="headcount",
    y="department_name",
    orientation="h",
    labels={
        "headcount": "Employees",
        "department_name": "Department"
    }
)

fig2.update_traces(marker_color="#2A9D8F")
fig2.update_layout(template="plotly_white")

st.plotly_chart(
    fig2,
    use_container_width=True
)

if not dept.empty:
    top = dept.sort_values(
        "headcount",
        ascending=False
    ).iloc[0]

    st.caption(
        f"Insight: {top['department_name']} is the largest "
        f"displayed department with "
        f"{int(top['headcount']):,} employees."
    )


# Department headcount share
st.subheader("Department Headcount Share (%)")

if HOSTED_MODE:

    share_df = pd.read_parquet(
        HOSTED_DIR / "department_distribution.parquet"
    )

else:

    share = duckdb.connect(
        str(DB),
        read_only=True
    )

    try:
        share_df = share.execute("""
            SELECT department_name,
                   department_headcount,
                   total_headcount,
                   headcount_share_pct
            FROM metrics.m32_department_headcount_share
            ORDER BY department_headcount DESC
        """).fetchdf()

    finally:
        share.close()


if not share_df.empty:

    share_fig = px.bar(
        share_df,
        x="headcount_share_pct",
        y="department_name",
        orientation="h",
        labels={
            "headcount_share_pct": "Headcount share (%)",
            "department_name": "Department"
        },
        color_discrete_sequence=["#247BA0"]
    )

    share_fig.update_layout(
        template="plotly_white"
    )

    st.plotly_chart(
        share_fig,
        use_container_width=True
    )

    top_share = share_df.iloc[0]

    st.caption(
        f"Insight: {top_share['department_name']} accounts "
        f"for {top_share['headcount_share_pct']:.2f}% "
        f"of the governed department headcount total "
        f"({int(top_share['department_headcount'])} "
        f"of {int(top_share['total_headcount'])} employees)."
    )


# Final dashboard note
st.info(
    "Department share uses the latest month in the governed "
    "department view. Location-tier and work-mode breakdowns "
    "are current workforce snapshots."
)
