
import pandas as pd
import os
from pathlib import Path
import plotly.express as px
import streamlit as st

# =========================================================
# GROWMAR PHASE 3 - TASK 13
# CROSS-DEPARTMENT IMPACT VIEW
# =========================================================

st.set_page_config(
    page_title="Cross-Department Impact | PulseIQ",
    page_icon="🏢",
    layout="wide",
)

CSV_PATH = "task13_department_month_summary.csv"


# =========================================================
# HOSTED PAGE 9 - COMPANY-WIDE CROSS-FUNCTIONAL IMPACT
# =========================================================

HOSTED_DATA = Path(__file__).resolve().parents[1] / "data" / "hosted"

HOSTED_MODE = (
    os.getenv("PULSEIQ_HOSTED_MODE", "").lower() == "true"
    or (
        not Path(CSV_PATH).exists()
        and HOSTED_DATA.exists()
    )
)

if HOSTED_MODE:

    @st.cache_data(ttl=300)
    def load_hosted_page9():
        workforce = pd.read_parquet(
            HOSTED_DATA / "workforce_monthly.parquet"
        )
        movements = pd.read_parquet(
            HOSTED_DATA / "workforce_movements_quarterly.parquet"
        )
        payroll = pd.read_parquet(
            HOSTED_DATA / "payroll_company_monthly.parquet"
        )
        attendance = pd.read_parquet(
            HOSTED_DATA / "attendance_monthly.parquet"
        )
        return workforce, movements, payroll, attendance

    workforce, movements, payroll, attendance = load_hosted_page9()

    st.title("🏢 Cross-Department Impact View")
    st.caption(
        "PulseIQ | Public company-wide workforce, payroll "
        "and operational impact"
    )

    # Use the common 18-month period across all four datasets.
    payroll["month_start_date"] = pd.to_datetime(
        payroll["month_start_date"]
    )

    start_date = payroll["month_start_date"].min()
    end_date = payroll["month_start_date"].max()

    for frame in [workforce, attendance]:
        frame["month_start_date"] = pd.to_datetime(
            frame["month_start_date"]
        )

    movements["quarter"] = pd.to_datetime(movements["quarter"])
    for column in ["hires", "exits", "net_movement"]:
        movements[column] = pd.to_numeric(
            movements[column], errors="raise"
        )

    workforce = workforce[
        workforce["month_start_date"].between(start_date, end_date)
    ]
    movements = movements[
        movements["quarter"].between(
            start_date.to_period("Q").start_time,
            end_date.to_period("Q").start_time
        )
    ].copy()
    attendance = attendance[
        attendance["month_start_date"].between(start_date, end_date)
    ]

    st.info(
        "Data period: "
        f"{start_date.strftime('%d %B %Y')} to "
        f"{(end_date + pd.offsets.MonthEnd(0)).strftime('%d %B %Y')}"
    )

    # -----------------------------------------------------
    # MONTHLY COMPANY-WIDE AGGREGATION
    # -----------------------------------------------------

    workforce_monthly = (
        workforce.groupby("month_start_date", as_index=False)
        .agg(workforce_headcount=("headcount", "sum"))
    )

    movement_quarterly = movements.sort_values("quarter").copy()
    movement_quarterly["quarter_label"] = (
        movement_quarterly["quarter"]
        .dt.to_period("Q")
        .map(lambda period: f"Q{period.quarter} {period.year}")
    )

    attendance_monthly = (
        attendance.groupby("month_start_date", as_index=False)
        .agg(
            average_department_attendance=(
                "attendance_rate_pct", "mean"
            ),
            average_late_arrivals_per_100_days=(
                "late_arrivals_per_100_present_days", "mean"
            ),
            departments_represented=("department_id", "nunique")
        )
    )

    payroll_monthly = payroll[
        [
            "month_start_date",
            "gross_pay",
            "net_pay",
            "employer_cost",
            "employee_count"
        ]
    ].copy()

    monthly = (
        payroll_monthly
        .merge(workforce_monthly, on="month_start_date", how="left")
        .merge(attendance_monthly, on="month_start_date", how="left")
        .sort_values("month_start_date")
    )

    monthly["month_label"] = monthly["month_start_date"].dt.strftime("%b %Y")

    if monthly.isnull().any().any():
        st.warning(
            "Some monthly metrics are unavailable in the selected "
            "period. Missing values are not treated as zero."
        )

    # -----------------------------------------------------
    # 1. COMPANY-WIDE KPI OVERVIEW
    # -----------------------------------------------------

    latest = monthly.iloc[-1]

    st.subheader("Company-Wide Performance")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Payroll Employer Cost",
        f"₹{latest['employer_cost']:,.0f}"
    )
    c2.metric(
        "Payroll Employee Count",
        f"{latest['employee_count']:,.0f}"
    )
    c3.metric(
        "Published-Group Headcount",
        f"{latest['workforce_headcount']:,.0f}"
    )
    c4.metric(
        "Average Department Attendance",
        f"{latest['average_department_attendance']:.2f}%"
    )

    # -----------------------------------------------------
    # 2. WORKFORCE STRENGTH
    # -----------------------------------------------------

    st.divider()
    st.subheader("Published-Group Workforce Trend")

    workforce_chart = monthly[
        ["month_label", "workforce_headcount"]
    ].rename(columns={
        "workforce_headcount": "Published-Group Headcount"
    })

    workforce_fig = px.line(
        workforce_chart,
        x="month_label",
        y="Published-Group Headcount",
        markers=True,
        title="Published-Group Headcount by Month",
        labels={
            "month_label": "Month",
            "Published-Group Headcount": "Employees"
        }
    )
    workforce_fig.update_xaxes(type="category")
    workforce_fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(workforce_fig, use_container_width=True)

    # -----------------------------------------------------
    # 3. EMPLOYEE MOVEMENT
    # -----------------------------------------------------

    st.divider()
    st.subheader("Quarterly Employee Movement Trend")

    movement_chart = movement_quarterly[
        ["quarter_label", "hires", "exits"]
    ].rename(columns={
        "hires": "Hires",
        "exits": "Exits"
    })

    st.line_chart(
        movement_chart,
        x="quarter_label",
        y=["Hires", "Exits"],
        x_label="Quarter",
        y_label="Company-Wide Movements"
    )

    net_chart = movement_quarterly[
        ["quarter_label", "net_movement"]
    ].rename(columns={
        "net_movement": "Net Workforce Movement"
    })

    st.bar_chart(
        net_chart,
        x="quarter_label",
        y="Net Workforce Movement",
        x_label="Quarter",
        y_label="Hires minus Exits"
    )

    quarterly_display = movement_quarterly[
        ["quarter", "hires", "exits", "net_movement"]
    ].copy()

    quarterly_display["quarter"] = quarterly_display[
        "quarter"
    ].dt.to_period("Q").map(
        lambda period: f"Q{period.quarter} {period.year}"
    )

    quarterly_display = quarterly_display.rename(columns={
        "quarter": "Quarter",
        "hires": "Hires",
        "exits": "Exits",
        "net_movement": "Net Movement"
    })

    st.subheader("Quarterly Workforce Movement Summary")
    st.dataframe(
        quarterly_display,
        use_container_width=True,
        hide_index=True
    )

    # -----------------------------------------------------
    # 4. PAYROLL IMPACT
    # -----------------------------------------------------

    st.divider()
    st.subheader("Payroll Impact Trend")

    payroll_chart = monthly[
        ["month_label", "employer_cost", "gross_pay", "net_pay"]
    ].rename(columns={
        "employer_cost": "Employer Cost",
        "gross_pay": "Gross Pay",
        "net_pay": "Net Pay"
    })

    st.line_chart(
        payroll_chart,
        x="month_label",
        y=["Employer Cost", "Gross Pay", "Net Pay"],
        x_label="Month",
        y_label="Amount (₹)"
    )

    # -----------------------------------------------------
    # 5. ATTENDANCE IMPACT
    # -----------------------------------------------------

    st.divider()
    st.subheader("Attendance & Punctuality Trend")

    attendance_chart = monthly[
        [
            "month_label",
            "average_department_attendance",
            "average_late_arrivals_per_100_days"
        ]
    ].rename(columns={
        "average_department_attendance": "Average Department Attendance (%)",
        "average_late_arrivals_per_100_days": (
            "Average Late Arrivals per 100 Present Days"
        )
    })

    attendance_fig = px.line(
        attendance_chart,
        x="month_label",
        y="Average Department Attendance (%)",
        markers=True,
        title="Average Department Attendance Trend",
        labels={
            "month_label": "Month",
            "Average Department Attendance (%)": "Attendance (%)"
        }
    )
    attendance_fig.update_xaxes(type="category")
    st.plotly_chart(attendance_fig, use_container_width=True)

    st.subheader("Late Arrivals Trend")

    late_fig = px.line(
        attendance_chart,
        x="month_label",
        y="Average Late Arrivals per 100 Present Days",
        markers=True,
        title="Average Late Arrivals per 100 Present Days",
        labels={
            "month_label": "Month",
            "Average Late Arrivals per 100 Present Days":
                "Late Arrivals per 100 Present Days"
        }
    )
    late_fig.update_xaxes(type="category")
    st.plotly_chart(late_fig, use_container_width=True)

    # -----------------------------------------------------
    # 6. MONTHLY IMPACT SUMMARY
    # -----------------------------------------------------

    st.divider()
    st.subheader("Monthly Cross-Functional Summary")

    display = monthly.copy()
    display["month_start_date"] = (
        display["month_start_date"].dt.strftime("%b %Y")
    )

    for column in [
        "gross_pay", "net_pay", "employer_cost"
    ]:
        display[column] = display[column].map(
            lambda value: (
                f"₹{value:,.2f}" if pd.notna(value) else "N/A"
            )
        )

    display = display.rename(columns={
        "month_start_date": "Month",
        "employee_count": "Payroll Employees",
        "workforce_headcount": "Published-Group Headcount",
        "average_department_attendance": (
            "Average Department Attendance (%)"
        ),
        "average_late_arrivals_per_100_days": (
            "Average Late Arrivals per 100 Present Days"
        ),
        "employer_cost": "Employer Cost",
        "gross_pay": "Gross Pay",
        "net_pay": "Net Pay"
    })

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True
    )

    # -----------------------------------------------------
    # 7. METHODOLOGY AND PRIVACY
    # -----------------------------------------------------

    st.divider()
    st.subheader("Methodology & Privacy")

    st.write(
        "- Workforce headcount is the sum of published department groups; "
        "department groups below the minimum threshold are excluded."
    )
    st.write(
        "- Hiring and exit movements are company-wide quarterly totals. "
        "Only complete quarters with at least 10 hires and 10 exits are published."
    )
    st.write(
        "- Payroll employee count comes from the company-wide payroll "
        "dataset; workforce headcount is calculated separately."
    )
    st.write(
        "- Attendance is the unweighted average of published "
        "department attendance rates, not a weighted company-wide rate."
    )
    st.write(
        "- The dashboard covers the common April 2025 to September 2026 "
        "period across all four datasets."
    )
    st.write(
        "- Department rankings, client information and individual "
        "employee records are not displayed."
    )

    st.caption(
        "Public dashboard uses curated aggregated Parquet datasets."
    )

    st.stop()


st.title("Cross-Department Impact View")
st.caption(
    "GROWMAR • Phase 3 • Task 13 | "
    "Department-wise payroll, workforce, attendance and leave impact"
)

st.write(
    "Compare department-level workforce and operational indicators "
    "to understand how payroll, attendance, leave and employee movement "
    "vary across departments."
)


# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------

@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv(CSV_PATH)

    df["month"] = pd.to_datetime(
        df["month"].astype(str) + "-01",
        errors="coerce"
    )

    numeric_columns = [
        "employer_cost",
        "gross_pay",
        "net_pay",
        "employees_paid",
        "scheduled_days",
        "present_days",
        "half_days_unpaid",
        "late_arrivals",
        "headcount_start",
        "headcount_end",
        "hires",
        "exits",
        "voluntary_exits",
        "approved_leave_requests",
        "approved_leave_days",
        "attendance_rate_pct",
        "attrition_rate_monthly_pct",
        "cost_per_head",
        "overtime_hours",
    ]

    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # No leave records in a department-month means zero
    df["approved_leave_days"] = (
        df["approved_leave_days"].fillna(0)
    )
    df["approved_leave_requests"] = (
        df["approved_leave_requests"].fillna(0)
    )

    return df


try:
    df = load_data()
except Exception as exc:
    st.error(f"Unable to load Task 13 summary: {exc}")
    st.info(
        "Check that task13_department_month_summary.csv "
        "exists in the project root."
    )
    st.stop()


# ---------------------------------------------------------
# FILTERS
# ---------------------------------------------------------

st.subheader("Analysis Filters")

all_months = sorted(df["month"].dropna().unique())

if not all_months:
    st.error("No valid month values found in the summary.")
    st.stop()

month_labels = [
    pd.Timestamp(month).strftime("%b %Y")
    for month in all_months
]

selected_months = st.select_slider(
    "Select analysis period",
    options=month_labels,
    value=(month_labels[0], month_labels[-1]),
)

start_index = month_labels.index(selected_months[0])
end_index = month_labels.index(selected_months[1])

start_month = all_months[start_index]
end_month = all_months[end_index]

filtered = df[
    (df["month"] >= start_month) &
    (df["month"] <= end_month)
].copy()

include_executive = st.checkbox(
    "Include Executive Office in analysis",
    value=False,
)

if not include_executive:
    filtered = filtered[
        filtered["department_id"] != "D00"
    ]

departments = sorted(
    filtered["department_name"].dropna().unique()
)

selected_departments = st.multiselect(
    "Select departments",
    options=departments,
    default=departments,
)

filtered = filtered[
    filtered["department_name"].isin(selected_departments)
].copy()

if filtered.empty:
    st.warning("No data available for the selected filters.")
    st.stop()


# ---------------------------------------------------------
# DEPARTMENT-LEVEL AGGREGATION
# ---------------------------------------------------------

def summarize_departments(data):

    summary = data.groupby(
        ["department_id", "department_name"],
        as_index=False
    ).agg(
        employer_cost=("employer_cost", "sum"),
        gross_pay=("gross_pay", "sum"),
        net_pay=("net_pay", "sum"),
        scheduled_days=("scheduled_days", "sum"),
        present_days=("present_days", "sum"),
        half_days_unpaid=("half_days_unpaid", "sum"),
        late_arrivals=("late_arrivals", "sum"),
        headcount_start=("headcount_start", "sum"),
        hires=("hires", "sum"),
        exits=("exits", "sum"),
        voluntary_exits=("voluntary_exits", "sum"),
        approved_leave_requests=("approved_leave_requests", "sum"),
        approved_leave_days=("approved_leave_days", "sum"),
        employees_paid=("employees_paid", "sum"),
    )

    # Weighted attendance calculation
    summary["attendance_rate_pct"] = (
        (
            summary["present_days"]
            + 0.5 * summary["half_days_unpaid"]
        )
        / summary["scheduled_days"].replace(0, pd.NA)
    ) * 100

    # Aggregate period attrition
    summary["attrition_rate_pct"] = (
        summary["exits"]
        / summary["headcount_start"].replace(0, pd.NA)
    ) * 100

    summary["late_arrivals_per_100_present_days"] = (
        summary["late_arrivals"]
        / summary["present_days"].replace(0, pd.NA)
    ) * 100

    summary["average_monthly_headcount_end"] = (
        data.groupby("department_id")["headcount_end"].mean()
        .reindex(summary["department_id"])
        .values
    )

    return summary


dept_summary = summarize_departments(filtered)


# ---------------------------------------------------------
# KPI CARDS
# ---------------------------------------------------------

st.divider()
st.subheader("Overall Department Performance")

total_cost = dept_summary["employer_cost"].sum()
total_exits = dept_summary["exits"].sum()
total_hires = dept_summary["hires"].sum()
total_leave = dept_summary["approved_leave_days"].sum()

total_scheduled = dept_summary["scheduled_days"].sum()
total_present = dept_summary["present_days"].sum()
total_half_days = dept_summary["half_days_unpaid"].sum()

overall_attendance = (
    (total_present + 0.5 * total_half_days)
    / total_scheduled * 100
    if total_scheduled else 0
)

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Total Employer Cost",
    f"₹{total_cost / 10000000:.2f} Cr"
)

c2.metric(
    "Overall Attendance",
    f"{overall_attendance:.2f}%"
)

c3.metric(
    "Total Employee Exits",
    f"{total_exits:,.0f}"
)

c4.metric(
    "Approved Leave Days",
    f"{total_leave:,.0f}"
)

c5, c6, c7 = st.columns(3)

c5.metric("Total Hires", f"{total_hires:,.0f}")
c6.metric("Departments Analysed", len(dept_summary))
c7.metric("Total Net Pay", f"₹{dept_summary['net_pay'].sum() / 10000000:.2f} Cr")


# ---------------------------------------------------------
# COMBINED DEPARTMENT COMPARISON CHART
# ---------------------------------------------------------

st.divider()
st.subheader("Combined Department Comparison")

st.write(
    "The heatmap converts each department's metric into a relative "
    "0–100 scale. A higher value means a higher value for that metric; "
    "it does not necessarily indicate better performance."
)

chart_columns = {
    "Payroll Cost": "employer_cost",
    "Attendance": "attendance_rate_pct",
    "Approved Leave Days": "approved_leave_days",
    "Employee Exits": "exits",
}

chart_data = dept_summary[
    ["department_name"] + list(chart_columns.values())
].copy()

normalized = chart_data.copy()

for label, column in chart_columns.items():
    values = chart_data[column]

    min_value = values.min()
    max_value = values.max()

    if pd.isna(min_value) or pd.isna(max_value):
        normalized[label] = 0
    elif max_value == min_value:
        normalized[label] = 50
    else:
        normalized[label] = (
            (values - min_value) / (max_value - min_value)
        ) * 100

heatmap_data = normalized[
    ["department_name"] + list(chart_columns.keys())
].set_index("department_name")

fig = px.imshow(
    heatmap_data,
    text_auto=".1f",
    aspect="auto",
    color_continuous_scale="Blues",
    labels={
        "x": "Business Indicators",
        "y": "Department",
        "color": "Relative Index"
    },
)

fig.update_layout(
    height=520,
    margin=dict(l=10, r=10, t=30, b=10),
)

st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------
# DEPARTMENT IMPACT INSIGHTS
# ---------------------------------------------------------

st.divider()
st.subheader("Department Impact Insights")

highest_cost = dept_summary.loc[
    dept_summary["employer_cost"].idxmax()
]

lowest_attendance = dept_summary.loc[
    dept_summary["attendance_rate_pct"].idxmin()
]

highest_exits = dept_summary.loc[
    dept_summary["exits"].idxmax()
]

highest_leave = dept_summary.loc[
    dept_summary["approved_leave_days"].idxmax()
]

i1, i2 = st.columns(2)

with i1:
    st.info(
        f"**Highest payroll cost:** {highest_cost['department_name']} "
        f"with ₹{highest_cost['employer_cost'] / 10000000:.2f} Cr."
    )

    st.warning(
        f"**Lowest attendance:** {lowest_attendance['department_name']} "
        f"with {lowest_attendance['attendance_rate_pct']:.2f}%."
    )

with i2:
    st.info(
        f"**Highest employee exits:** {highest_exits['department_name']} "
        f"with {highest_exits['exits']:.0f} exits."
    )

    st.warning(
        f"**Highest approved leave:** {highest_leave['department_name']} "
        f"with {highest_leave['approved_leave_days']:.0f} days."
    )


# ---------------------------------------------------------
# DEPARTMENT DETAIL TABLE
# ---------------------------------------------------------

st.divider()
st.subheader("Department-Wise Impact Summary")

display_data = dept_summary[
    [
        "department_name",
        "employer_cost",
        "attendance_rate_pct",
        "approved_leave_days",
        "hires",
        "exits",
        "attrition_rate_pct",
        "average_monthly_headcount_end",
    ]
].copy()

display_data = display_data.rename(
    columns={
        "department_name": "Department",
        "employer_cost": "Employer Cost (₹)",
        "attendance_rate_pct": "Attendance (%)",
        "approved_leave_days": "Approved Leave Days",
        "hires": "Hires",
        "exits": "Exits",
        "attrition_rate_pct": "Weighted Monthly Exit Rate (%)",
        "average_monthly_headcount_end": "Average Monthly Headcount",
    }
)

st.dataframe(
    display_data.round(2),
    use_container_width=True,
    hide_index=True,
)

# ---------------------------------------------------------
# METHODOLOGY
# ---------------------------------------------------------

with st.expander("View calculation methodology"):
    st.markdown("""
    - **Employer Cost:** Sum of monthly employer payroll cost.
    - **Attendance:** Weighted attendance using present days,
      half of unpaid half-days and scheduled days.
    - **Approved Leave:** Sum of approved leave days assigned
      to the request start month in the source summary.
    - **Hires and Exits:** Sum of monthly workforce movements.
    - **Weighted Monthly Exit Rate:** Total exits divided by
        summed monthly starting headcount.
    - **Combined Chart:** Min-max normalized comparison of
      payroll cost, attendance, approved leave and exits.
    """)

st.caption(
    "Source: PulseIQ Task 13 department-month summary. "
    "Department-level aggregates are used; individual employee "
    "payroll details are not displayed."
)
