from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

DB = Path(__file__).parent / "05_Starter" / "pulseiq.duckdb"
st.set_page_config(page_title="PulseIQ Workforce", page_icon="📊", layout="wide")

st.title("PulseIQ | Workforce Overview")
st.caption("Governed workforce metrics · Monthly headcount and current workforce")

@st.cache_data
def load_data():
    con = duckdb.connect(str(DB), read_only=True)
    try:
        headcount = con.execute("""
            SELECT month_start_date, department_id, department_name, headcount
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

try:
    headcount, hires, exits = load_data()
except Exception as exc:
    st.error(f"Could not load dashboard metric views: {exc}")
    st.stop()

headcount["month_start_date"] = pd.to_datetime(headcount["month_start_date"])
hires["month_start_date"] = pd.to_datetime(hires["month_start_date"])
exits["month_start_date"] = pd.to_datetime(exits["month_start_date"])

with st.sidebar:
    st.header("Filters")
    departments = sorted(headcount["department_name"].dropna().unique())
    selected = st.multiselect("Department", departments, default=departments)
    min_date = headcount["month_start_date"].min().date()
    max_date = headcount["month_start_date"].max().date()
    dates = st.date_input(
        "Date range", value=(min_date, max_date),
        min_value=min_date, max_value=max_date
    )

df = headcount[headcount["department_name"].isin(selected)].copy()
if isinstance(dates, (tuple, list)) and len(dates) == 2:
    start, end = pd.Timestamp(dates[0]), pd.Timestamp(dates[1])
    df = df[df["month_start_date"].between(start, end)]

if df.empty:
    st.warning("No results for these filters. Please select another range or department.")
    st.stop()

monthly = (
    df.groupby("month_start_date", as_index=False)["headcount"]
      .sum().sort_values("month_start_date")
)
latest_month = monthly.iloc[-1]["month_start_date"]
latest = int(monthly.iloc[-1]["headcount"])
first = int(monthly.iloc[0]["headcount"])
change = latest - first
change_pct = change / first * 100 if first else 0

dept_ids = df["department_id"].unique()
h = hires[hires["department_id"].isin(dept_ids)]
e = exits[exits["department_id"].isin(dept_ids)]
if isinstance(dates, (tuple, list)) and len(dates) == 2:
    h = h[h["month_start_date"].between(start, end)]
    e = e[e["month_start_date"].between(start, end)]

a, b, c, d = st.columns(4)
a.metric("Latest headcount", f"{latest:,}", latest_month.strftime("%b %Y"))
b.metric("Net change", f"{change:+,}", f"{change_pct:+.1f}%")
c.metric("Hires in period", f"{int(h['hires'].sum()):,}")
d.metric("Exits in period", f"{int(e['exits'].sum()):,}")

st.subheader("Headcount trend")
fig = px.line(monthly, x="month_start_date", y="headcount", markers=True,
              labels={"month_start_date": "Month", "headcount": "Employees"})
fig.update_traces(line_color="#247BA0")
fig.update_layout(template="plotly_white")
st.plotly_chart(fig, use_container_width=True)
st.caption(
    f"Insight: headcount changed by {change:+,} ({change_pct:+.1f}%) "
    f"from {monthly.iloc[0]['month_start_date']:%b %Y} to {latest_month:%b %Y}."
)

st.subheader("Department workforce")
dept = (
    df[df["month_start_date"].eq(latest_month)]
    .groupby("department_name", as_index=False)["headcount"].sum()
    .sort_values("headcount")
)
fig2 = px.bar(dept, x="headcount", y="department_name", orientation="h",
              labels={"headcount": "Employees", "department_name": "Department"})
fig2.update_traces(marker_color="#2A9D8F")
fig2.update_layout(template="plotly_white")
st.plotly_chart(fig2, use_container_width=True)
if not dept.empty:
    top = dept.sort_values("headcount", ascending=False).iloc[0]
    st.caption(
        f"Insight: {top['department_name']} is the largest displayed department "
        f"with {int(top['headcount']):,} employees."
    )

st.info(
    "Headcount comes from governed metric views. Location-tier and work-mode "
    "breakdowns are current snapshots and will be shown on the Workforce Details page."
)
