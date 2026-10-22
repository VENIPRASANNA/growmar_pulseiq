from pathlib import Path
import duckdb
import plotly.express as px
import streamlit as st

DB = Path(__file__).resolve().parents[1] / "05_Starter" / "pulseiq.duckdb"

st.title("Workforce Details")
st.caption("Current workforce snapshot · Governed metric views")

@st.cache_data
def load_details():
    con = duckdb.connect(str(DB), read_only=True)
    try:
        location = con.execute("""
            SELECT city_tier, tier_number, headcount
            FROM metrics.m30_location_tier_headcount
            ORDER BY tier_number
        """).fetchdf()
        work_mode = con.execute("""
            SELECT work_mode, headcount
            FROM metrics.m31_work_mode_headcount
            ORDER BY headcount DESC
        """).fetchdf()
        return location, work_mode
    finally:
        con.close()

try:
    location, work_mode = load_details()
except Exception as exc:
    st.error(f"Could not load governed metric views: {exc}")
    st.stop()

left, right = st.columns(2)

with left:
    st.subheader("Employees by City Tier")
    fig = px.bar(
        location, x="city_tier", y="headcount",
        labels={"city_tier": "City tier", "headcount": "Employees"},
        color_discrete_sequence=["#247BA0"]
    )
    fig.update_layout(template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

    if not location.empty:
        top = location.loc[location["headcount"].idxmax()]
        total = int(location["headcount"].sum())
        share = int(top["headcount"]) / total * 100 if total else 0
        st.caption(
            f"Insight: {top['city_tier']} has the most employees "
            f"({int(top['headcount']):,}), representing {share:.1f}% "
            "of employees across displayed tiers."
        )

with right:
    st.subheader("Employees by Work Mode")
    fig = px.bar(
        work_mode, x="work_mode", y="headcount",
        labels={"work_mode": "Work mode", "headcount": "Employees"},
        color_discrete_sequence=["#2A9D8F"]
    )
    fig.update_layout(template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

    if not work_mode.empty:
        top = work_mode.loc[work_mode["headcount"].idxmax()]
        total = int(work_mode["headcount"].sum())
        share = int(top["headcount"]) / total * 100 if total else 0
        st.caption(
            f"Insight: {top['work_mode']} is the largest work mode "
            f"({int(top['headcount']):,} employees; {share:.1f}% "
            "of employees across displayed modes)."
        )

st.info(
    "These charts show current workforce snapshots, not historical monthly "
    "trends. Small groups may be suppressed by the governed metric layer."
)
