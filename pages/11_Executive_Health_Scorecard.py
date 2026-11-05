
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st


# =========================================================
# GROWMAR PHASE 3 - TASK 15
# EXECUTIVE COMPANY-HEALTH SCORECARD
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "05_Starter" / "pulseiq.duckdb"

st.set_page_config(
    page_title="Executive Health Scorecard | PulseIQ",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------
# PAGE STYLING
# ---------------------------------------------------------

st.markdown("""
<style>
    .scorecard-subtitle {
        color: #8b949e;
        font-size: 13px;
        margin-bottom: 18px;
    }

    .kpi-card {
        border: 1px solid rgba(128,128,128,0.3);
        border-radius: 10px;
        padding: 15px;
        min-height: 155px;
        margin-bottom: 10px;
    }

    .kpi-name {
        font-size: 14px;
        font-weight: 600;
        margin-bottom: 8px;
    }

    .kpi-value {
        font-size: 27px;
        font-weight: 700;
        margin-bottom: 8px;
    }

    .kpi-meta {
        font-size: 12px;
        color: #8b949e;
        margin-bottom: 5px;
    }

    .kpi-status {
        font-size: 12px;
        font-weight: 700;
        margin-top: 9px;
    }

    .status-good {
        color: #16a34a;
    }

    .status-bad {
        color: #dc2626;
    }

    .status-neutral {
        color: #d97706;
    }

    @media print {
        header, footer, [data-testid="stSidebar"],
        [data-testid="stToolbar"],
        [data-testid="stHeader"] {
            display: none !important;
        }

        .block-container {
            max-width: 100% !important;
            padding: 0.2in !important;
        }

        .kpi-card {
            break-inside: avoid;
        }
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# DATABASE FUNCTIONS
# ---------------------------------------------------------

@st.cache_data(ttl=120)
def get_available_months():
    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        result = con.execute("""
            SELECT month_start_date
            FROM metrics.m16_revenue
            ORDER BY month_start_date DESC
        """).fetchdf()

        return pd.to_datetime(
            result["month_start_date"]
        ).dt.to_period("M").dt.to_timestamp().tolist()

    finally:
        con.close()


@st.cache_data(ttl=120)
def get_month_data(month):
    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        month = pd.Timestamp(month).date()

        views = {
            "headcount": """
                SELECT *
                FROM metrics.m01_headcount
                WHERE month_start_date = ?
            """,

            "attrition": """
                SELECT *
                FROM metrics.m04_attrition_monthly
                WHERE month_start_date = ?
            """,

            "attendance": """
                SELECT *
                FROM metrics.m13_attendance_rate
                WHERE month_start_date = ?
            """,

            "overtime": """
                SELECT *
                FROM metrics.m11_overtime_share
                WHERE month_start_date = ?
            """,

            "revenue": """
                SELECT *
                FROM metrics.m16_revenue
                WHERE month_start_date = ?
            """,

            "profit": """
                SELECT *
                FROM metrics.m17_net_profit
                WHERE month_start_date = ?
            """,

            "margin": """
                SELECT *
                FROM metrics.m18_operating_margin
                WHERE month_start_date = ?
            """,

            "payroll_ratio": """
                SELECT *
                FROM metrics.m19_payroll_pct_revenue
                WHERE month_start_date = ?
            """,
        }

        data = {
            name: con.execute(query, [month]).fetchdf()
            for name, query in views.items()
        }

        targets = con.execute("""
            SELECT *
            FROM raw.kpi_targets
            WHERE month = ?
        """, [month]).fetchdf()

        return data, targets

    finally:
        con.close()


@st.cache_data(ttl=120)
def get_previous_month_data(month):
    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        month = pd.Timestamp(month).date()

        queries = {
            "headcount": """
                SELECT *
                FROM metrics.m01_headcount
                WHERE month_start_date < ?
                QUALIFY month_start_date =
                    MAX(month_start_date) OVER ()
            """,

            "attrition": """
                SELECT *
                FROM metrics.m04_attrition_monthly
                WHERE month_start_date < ?
                QUALIFY month_start_date =
                    MAX(month_start_date) OVER ()
            """,

            "attendance": """
                SELECT *
                FROM metrics.m13_attendance_rate
                WHERE month_start_date < ?
                QUALIFY month_start_date =
                    MAX(month_start_date) OVER ()
            """,

            "overtime": """
                SELECT *
                FROM metrics.m11_overtime_share
                WHERE month_start_date < ?
                QUALIFY month_start_date =
                    MAX(month_start_date) OVER ()
            """,

            "revenue": """
                SELECT *
                FROM metrics.m16_revenue
                WHERE month_start_date < ?
                QUALIFY month_start_date =
                    MAX(month_start_date) OVER ()
            """,

            "profit": """
                SELECT *
                FROM metrics.m17_net_profit
                WHERE month_start_date < ?
                QUALIFY month_start_date =
                    MAX(month_start_date) OVER ()
            """,

            "margin": """
                SELECT *
                FROM metrics.m18_operating_margin
                WHERE month_start_date < ?
                QUALIFY month_start_date =
                    MAX(month_start_date) OVER ()
            """,

            "payroll_ratio": """
                SELECT *
                FROM metrics.m19_payroll_pct_revenue
                WHERE month_start_date < ?
                QUALIFY month_start_date =
                    MAX(month_start_date) OVER ()
            """,
        }

        return {
            name: con.execute(query, [month]).fetchdf()
            for name, query in queries.items()
        }

    finally:
        con.close()


# ---------------------------------------------------------
# KPI CALCULATION FUNCTIONS
# ---------------------------------------------------------

def weighted_average(df, value_col, weight_col):
    if df.empty:
        return None

    valid = df[
        df[value_col].notna()
        & df[weight_col].notna()
        & (df[weight_col] > 0)
    ]

    if valid.empty:
        return None

    return float(
        (
            valid[value_col] * valid[weight_col]
        ).sum() / valid[weight_col].sum()
    )


def calculate_kpis(data):
    result = {}

    # Headcount
    df = data["headcount"]

    result["headcount"] = (
        float(df["headcount"].sum())
        if not df.empty else None
    )

    # Monthly attrition
    df = data["attrition"]

    if not df.empty:
        total_exits = df["exits"].sum()
        starting_headcount = df["headcount_start"].sum()

        result["attrition"] = (
            float(total_exits * 100 / starting_headcount)
            if starting_headcount > 0 else None
        )
    else:
        result["attrition"] = None

    # Attendance: employee-count weighted
    result["attendance"] = weighted_average(
        data["attendance"],
        "attendance_rate_pct",
        "employee_count",
    )

    # Overtime: employee-count weighted
    result["overtime"] = weighted_average(
        data["overtime"],
        "overtime_share_pct",
        "employee_count",
    )

    # Company-level financial metrics
    for key, column in [
        ("revenue", "revenue"),
        ("profit", "net_profit"),
        ("margin", "operating_margin_pct"),
        ("payroll_ratio", "payroll_pct_revenue"),
    ]:
        df = data[key]

        result[key] = (
            float(df[column].iloc[0])
            if not df.empty and pd.notna(df[column].iloc[0])
            else None
        )

    return result


def get_targets(targets):
    if targets.empty:
        return {
            "attendance": None,
            "overtime": None,
            "attrition": None,
        }

    return {
        "attendance": (
            float(targets["attendance_rate_target"].mean() * 100)
            if targets["attendance_rate_target"].notna().any()
            else None
        ),

        "overtime": (
            float(targets["overtime_share_target_pct"].mean())
            if targets["overtime_share_target_pct"].notna().any()
            else None
        ),

        "attrition": (
            float(targets["attrition_monthly_target_pct"].mean())
            if targets["attrition_monthly_target_pct"].notna().any()
            else None
        ),
    }


# ---------------------------------------------------------
# KPI STATUS
# ---------------------------------------------------------

def get_status(value, target, direction):
    if value is None or target is None:
        return "NO TARGET", "status-neutral"

    if direction == "higher":
        good = value >= target
    else:
        good = value <= target

    if good:
        return "ON TARGET", "status-good"

    return "BELOW TARGET", "status-bad"


def format_value(value, unit):
    if value is None:
        return "Unavailable"

    if unit == "count":
        return f"{value:,.0f}"

    if unit == "percent":
        return f"{value:.2f}%"

    if unit == "currency":
        return f"₹{value / 10000000:.2f} Cr"

    return f"{value:,.2f}"


# ---------------------------------------------------------
# PAGE HEADER
# ---------------------------------------------------------

st.title("Executive Company-Health Scorecard")

st.markdown(
    '<div class="scorecard-subtitle">'
    'GROWMAR • Phase 3 • Task 15 | Monthly executive performance overview'
    '</div>',
    unsafe_allow_html=True,
)

st.caption(
    "A concise company-health view covering workforce, operations and finance."
)

# ---------------------------------------------------------
# MONTH SELECTOR
# ---------------------------------------------------------

try:
    available_months = get_available_months()

    if not available_months:
        st.error("No monthly scorecard data is available.")
        st.stop()

    selected_month = st.selectbox(
        "Select reporting month",
        available_months,
        format_func=lambda x: pd.Timestamp(x).strftime("%B %Y"),
    )

    current_data, target_data = get_month_data(selected_month)
    previous_data = get_previous_month_data(selected_month)

except Exception as exc:
    st.error(f"Unable to load scorecard data: {exc}")
    st.stop()


current_kpis = calculate_kpis(current_data)
previous_kpis = calculate_kpis(previous_data)
targets = get_targets(target_data)

st.divider()

st.subheader(
    f"Company Health — {pd.Timestamp(selected_month).strftime('%B %Y')}"
)


# ---------------------------------------------------------
# KPI DEFINITIONS
# ---------------------------------------------------------

kpi_config = [
    {
        "key": "headcount",
        "name": "Headcount",
        "unit": "count",
        "target": None,
        "direction": None,
        "source": "metrics.m01_headcount",
        "reason": "Shows the active workforce at month end.",
        "page": "pages/1_Workforce_Details.py",
        "review": False,
    },
    {
        "key": "attrition",
        "name": "Monthly Attrition",
        "unit": "percent",
        "target": targets["attrition"],
        "direction": "lower",
        "source": "metrics.m04_attrition_monthly",
        "reason": "Tracks employee exits relative to starting headcount.",
        "page": "pages/3_Attrition_Analytics.py",
        "review": False,
    },
    {
        "key": "attendance",
        "name": "Attendance Rate",
        "unit": "percent",
        "target": targets["attendance"],
        "direction": "higher",
        "source": "metrics.m13_attendance_rate",
        "reason": "Shows workforce attendance against scheduled work.",
        "page": "pages/2_Attendance_Leave_Trends.py",
        "review": False,
    },
    {
        "key": "overtime",
        "name": "Overtime Share",
        "unit": "percent",
        "target": targets["overtime"],
        "direction": "lower",
        "source": "metrics.m11_overtime_share",
        "reason": "Highlights the share of payroll cost attributed to overtime.",
        "page": "pages/5_Payroll_Cost_Dashboard.py",
        "review": False,
    },
    {
        "key": "revenue",
        "name": "Revenue",
        "unit": "currency",
        "target": None,
        "direction": None,
        "source": "metrics.m16_revenue",
        "reason": "Shows monthly income booked in the ledger.",
        "page": "pages/7_Profit_Loss_Analytics.py",
        "review": True,
    },
    {
        "key": "profit",
        "name": "Net Profit",
        "unit": "currency",
        "target": None,
        "direction": None,
        "source": "metrics.m17_net_profit",
        "reason": "Shows revenue less recorded expenses.",
        "page": "pages/7_Profit_Loss_Analytics.py",
        "review": True,
    },
    {
        "key": "margin",
        "name": "Operating Margin",
        "unit": "percent",
        "target": None,
        "direction": None,
        "source": "metrics.m18_operating_margin",
        "reason": "Shows net profit as a share of revenue.",
        "page": "pages/7_Profit_Loss_Analytics.py",
        "review": True,
    },
    {
        "key": "payroll_ratio",
        "name": "Payroll % of Revenue",
        "unit": "percent",
        "target": None,
        "direction": None,
        "source": "metrics.m19_payroll_pct_revenue",
        "reason": "Shows the share of revenue consumed by payroll cost.",
        "page": "pages/5_Payroll_Cost_Dashboard.py",
        "review": True,
    },
]


# ---------------------------------------------------------
# KPI CARD RENDERING
# ---------------------------------------------------------

def render_kpi_card(config):
    key = config["key"]

    value = current_kpis.get(key)
    previous = previous_kpis.get(key)

    target = config["target"]
    direction = config["direction"]

    status, status_class = get_status(
        value,
        target,
        direction,
    )

    displayed_value = format_value(
        value,
        config["unit"],
    )

    if previous is not None and value is not None:
        delta = value - previous

        if config["unit"] == "currency":
            delta_text = f"₹{delta / 10000000:+.2f} Cr"
        elif config["unit"] == "percent":
            delta_text = f"{delta:+.2f} percentage points"
        else:
            delta_text = f"{delta:+,.0f}"
    else:
        delta_text = "Previous month unavailable"

    target_text = (
        format_value(target, config["unit"])
        if target is not None
        else "No target defined"
    )

    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-name">{config['name']}</div>
            <div class="kpi-value">{displayed_value}</div>
            <div class="kpi-meta">Target: {target_text}</div>
            <div class="kpi-meta">Previous month: {delta_text}</div>
            <div class="kpi-status {status_class}">{status}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if config["review"]:
        st.caption("Catalog: REVIEW REQUIRED")

    st.caption(config["reason"])

    st.caption(f"Source: `{config['source']}`")

    st.page_link(
        config["page"],
        label=f"View {config['name']} details",
        icon="↗",
    )


# ---------------------------------------------------------
# EXECUTIVE SCORECARD GRID
# ---------------------------------------------------------

for row_start in range(0, len(kpi_config), 4):
    cols = st.columns(4)

    for col, config in zip(
        cols,
        kpi_config[row_start:row_start + 4],
    ):
        with col:
            render_kpi_card(config)


# ---------------------------------------------------------
# KPI REASONS
# ---------------------------------------------------------

st.divider()
st.subheader("Why these eight KPIs?")

st.markdown("""
| KPI | Executive reason |
|---|---|
| Headcount | Understand workforce size and capacity. |
| Monthly Attrition | Monitor employee exits and workforce stability. |
| Attendance Rate | Monitor workforce availability and attendance. |
| Overtime Share | Identify potential payroll pressure from overtime. |
| Revenue | Track the income generated by the business. |
| Net Profit | Understand whether the business is profitable. |
| Operating Margin | Measure profitability relative to revenue. |
| Payroll % of Revenue | Monitor the share of revenue consumed by payroll. |
""")

st.info(
    "Task completion is excluded from the eight headline KPIs because "
    "its governed metric view is at team/sprint level rather than "
    "company/month level. It remains available in the detailed "
    "Team Productivity dashboard."
)


# ---------------------------------------------------------
# DATA QUALITY AND TRACEABILITY
# ---------------------------------------------------------

st.divider()
st.subheader("Metric governance and interpretation")

st.markdown("""
- All eight KPI values are retrieved from governed `metrics` views.
- Target comparisons use `raw.kpi_targets`.
- Attendance and overtime company-level figures use employee-count-weighted
  averages of department-level metric-view values.
- Monthly attrition is calculated from total exits divided by total
  starting headcount.
- Headcount is the sum of department-level month-end headcounts.
- Revenue, net profit, operating margin and payroll percentage of revenue
  are marked **REVIEW REQUIRED** in the metric catalog.
- No target is invented for metrics without a defined target.
""")

st.warning(
    "A missing target is not a failed KPI. Finance metrics marked "
    "REVIEW REQUIRED should be interpreted with the metric catalog caveats "
    "and validated by the Finance team before executive decisions."
)

st.caption(
    f"Reporting month: {pd.Timestamp(selected_month).strftime('%B %Y')} | "
    "Sources: PulseIQ governed DuckDB metric views and KPI targets."
)
