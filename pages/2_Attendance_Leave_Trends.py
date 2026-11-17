
import os
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


# --------------------------------------------------
# Configuration
# --------------------------------------------------

DB = Path(__file__).resolve().parents[1] / "05_Starter" / "pulseiq.duckdb"

st.set_page_config(
    page_title="Attendance & Leave Trends",
    page_icon="📅",
    layout="wide",
)

st.title("Attendance & Leave Trends")
st.caption(
    "Monthly workforce attendance and punctuality trends"
)



# --------------------------------------------------
# HOSTED ATTENDANCE MODE — AGGREGATE DATA ONLY
# --------------------------------------------------

HOSTED_DIR = Path(__file__).resolve().parents[1] / "data" / "hosted"
HOSTED_MODE = (
    os.getenv("PULSEIQ_HOSTED_MODE", "").lower() == "true"
    or not DB.exists()
)

if HOSTED_MODE:
    st.info(
        "Public hosted mode: privacy-reviewed department-month "
        "attendance aggregates."
    )

    hosted_file = HOSTED_DIR / "attendance_monthly.parquet"

    if not hosted_file.exists():
        st.error("Hosted attendance dataset is missing.")
        st.stop()

    try:
        hosted = pd.read_parquet(hosted_file)
    except Exception as exc:
        st.error(f"Unable to load hosted attendance data: {exc}")
        st.stop()

    required = {
        "month_start_date",
        "department_name",
        "attendance_rate_pct",
        "late_arrivals_per_100_present_days",
        "employee_count",
    }

    missing = required - set(hosted.columns)

    if missing:
        st.error(
            "Unexpected hosted attendance schema: "
            + ", ".join(sorted(missing))
        )
        st.stop()

    hosted["month_start_date"] = pd.to_datetime(
        hosted["month_start_date"], errors="coerce"
    )

    for column in [
        "attendance_rate_pct",
        "late_arrivals_per_100_present_days",
        "employee_count",
    ]:
        hosted[column] = pd.to_numeric(
            hosted[column], errors="coerce"
        )

    hosted = hosted.dropna(
        subset=[
            "month_start_date",
            "department_name",
            "attendance_rate_pct",
            "late_arrivals_per_100_present_days",
        ]
    ).copy()

    # Recheck publication threshold before displaying public data.
    hosted = hosted[hosted["employee_count"] >= 10].copy()

    if hosted.empty:
        st.warning("No eligible hosted attendance aggregates are available.")
        st.stop()

    if hosted.duplicated(
        ["month_start_date", "department_name"]
    ).any():
        st.error("Duplicate department-month records detected.")
        st.stop()

    with st.sidebar:
        st.header("Filters")

        departments = sorted(hosted["department_name"].unique())

        selected_departments = st.multiselect(
            "Department",
            departments,
            default=departments,
        )

        min_date = hosted["month_start_date"].min().date()
        max_date = hosted["month_start_date"].max().date()

        selected_dates = st.date_input(
            "Date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

    filtered = hosted[
        hosted["department_name"].isin(selected_departments)
    ].copy()

    if isinstance(selected_dates, (tuple, list)) and len(selected_dates) == 2:
        start = pd.Timestamp(selected_dates[0]).to_period("M").to_timestamp()
        end = pd.Timestamp(selected_dates[1]).to_period("M").to_timestamp()

        filtered = filtered[
            filtered["month_start_date"].between(start, end)
        ]

    if filtered.empty:
        st.warning("No published attendance aggregates match these filters.")
        st.stop()

    st.caption(
        "Privacy and coverage note: department-month groups with fewer "
        "than 10 employees are excluded. Some months contain fewer "
        "published departments than others. Results describe published "
        "groups only, not necessarily the complete organisation."
    )

    # Equal-weighted average of published department rates.
    monthly = (
        filtered.groupby("month_start_date", as_index=False)
        .agg(
            average_department_attendance_pct=(
                "attendance_rate_pct", "mean"
            ),
            average_late_arrivals_per_100_present_days=(
                "late_arrivals_per_100_present_days", "mean"
            ),
            published_departments=("department_name", "nunique"),
            published_department_months=("department_name", "size"),
        )
        .sort_values("month_start_date")
    )

    department_summary = (
        filtered.groupby("department_name", as_index=False)
        .agg(
            average_attendance_pct=("attendance_rate_pct", "mean"),
            average_late_arrivals_per_100_present_days=(
                "late_arrivals_per_100_present_days", "mean"
            ),
            published_months=("month_start_date", "nunique"),
        )
        .sort_values("average_attendance_pct")
    )

    latest = monthly.iloc[-1]

    st.header("Attendance overview")

    k1, k2, k3, k4 = st.columns(4)

    k1.metric(
        "Latest average department attendance",
        f"{latest['average_department_attendance_pct']:.2f}%",
    )

    k2.metric(
        "Latest published departments",
        f"{int(latest['published_departments'])}",
    )

    k3.metric(
        "Average late arrivals per 100 present days",
        f"{latest['average_late_arrivals_per_100_present_days']:.2f}",
    )

    k4.metric(
        "Published department-month records",
        f"{len(filtered):,}",
    )

    st.caption(
        "Attendance KPIs are unweighted averages of published "
        "department-level rates. They are not exact workforce-wide rates."
    )

    # 1. Monthly attendance trend
    st.subheader("1. Monthly attendance trend")

    fig = px.line(
        monthly,
        x="month_start_date",
        y="average_department_attendance_pct",
        markers=True,
        labels={
            "month_start_date": "Month",
            "average_department_attendance_pct":
                "Average published department attendance (%)",
        },
    )

    fig.update_layout(
        template="plotly_white",
        yaxis_ticksuffix="%",
    )

    st.plotly_chart(fig, use_container_width=True)

    # 2. Attendance by department
    st.subheader("2. Attendance by department")

    fig_department = px.bar(
        department_summary,
        x="average_attendance_pct",
        y="department_name",
        orientation="h",
        text="average_attendance_pct",
        labels={
            "average_attendance_pct": "Average attendance (%)",
            "department_name": "Department",
        },
        hover_data={"published_months": True},
    )

    fig_department.update_traces(
        texttemplate="%{text:.2f}%",
        textposition="outside",
        cliponaxis=False,
    )

    fig_department.update_layout(
        template="plotly_white",
        xaxis_ticksuffix="%",
    )

    st.plotly_chart(fig_department, use_container_width=True)

    # 3. Late-arrival trend
    st.subheader("3. Late arrivals by month")

    fig_late = px.bar(
        monthly,
        x="month_start_date",
        y="average_late_arrivals_per_100_present_days",
        labels={
            "month_start_date": "Month",
            "average_late_arrivals_per_100_present_days":
                "Average late arrivals per 100 present days",
        },
    )

    fig_late.update_layout(template="plotly_white")

    st.plotly_chart(fig_late, use_container_width=True)

    # 4. Published aggregate detail
    st.subheader("4. Published department attendance detail")

    detail = filtered[
        [
            "month_start_date",
            "department_name",
            "attendance_rate_pct",
            "late_arrivals_per_100_present_days",
        ]
    ].sort_values(
        ["month_start_date", "department_name"]
    ).rename(columns={
        "month_start_date": "Month",
        "department_name": "Department",
        "attendance_rate_pct": "Attendance rate (%)",
        "late_arrivals_per_100_present_days":
            "Late arrivals per 100 present days",
    })

    st.dataframe(detail, use_container_width=True, hide_index=True)

    st.download_button(
        "Download published attendance aggregates (CSV)",
        data=detail.to_csv(index=False).encode("utf-8"),
        file_name="published_attendance_aggregates.csv",
        mime="text/csv",
    )

    # 5. Numerical findings
    st.subheader("5. Attendance findings")

    lowest = monthly.loc[
        monthly["average_department_attendance_pct"].idxmin()
    ]
    highest = monthly.loc[
        monthly["average_department_attendance_pct"].idxmax()
    ]

    st.write(
        f"**Lowest average published department attendance:** "
        f"{lowest['month_start_date']:%B %Y} — "
        f"{lowest['average_department_attendance_pct']:.2f}%."
    )

    st.write(
        f"**Highest average published department attendance:** "
        f"{highest['month_start_date']:%B %Y} — "
        f"{highest['average_department_attendance_pct']:.2f}%."
    )

    if len(monthly) >= 2:
        monthly["change_pp"] = (
            monthly["average_department_attendance_pct"].diff()
        )

        declines = monthly.dropna(subset=["change_pp"])
        declines = declines[declines["change_pp"] < 0]

        if not declines.empty:
            largest = declines.loc[declines["change_pp"].idxmin()]

            st.write(
                f"**Largest month-to-month decline:** "
                f"{largest['month_start_date']:%B %Y} — "
                f"{largest['change_pp']:.2f} percentage points."
            )
        else:
            st.info(
                "No month-to-month decline was found in the selected range."
            )

    st.info(
        "These findings describe published department aggregates. "
        "They do not establish the cause of attendance changes."
    )

    st.success("Hosted Attendance Dashboard loaded successfully.")
    st.stop()


# --------------------------------------------------
# Load data from DuckDB
# --------------------------------------------------

@st.cache_data
def load_data():
    con = duckdb.connect(str(DB), read_only=True)

    try:
        attendance = con.execute("""
            SELECT
                d.month_start_date,
                a.department_id,
                dep.department_name,
                COUNT(DISTINCT a.employee_id) AS employee_count,
                SUM(a.present_days) AS present_days,
                SUM(a.half_days_unpaid) AS half_days_unpaid,
                SUM(a.scheduled_days) AS scheduled_days,
                SUM(a.late_arrivals) AS late_arrivals,
                SUM(a.overtime_hours) AS overtime_hours,
                SUM(a.paid_leave_days) AS paid_leave_days,
                SUM(a.unpaid_absence_days) AS unpaid_absence_days,
                ROUND(
                    100.0 * (
                        SUM(a.present_days)
                        + 0.5 * SUM(a.half_days_unpaid)
                    ) / NULLIF(SUM(a.scheduled_days), 0),
                    2
                ) AS attendance_rate_pct
            FROM raw.fact_attendance_monthly a
            JOIN raw.dim_date d
                ON d.date_key = a.date_key
            LEFT JOIN raw.dim_department dep
                ON dep.department_id = a.department_id
            GROUP BY
                d.month_start_date,
                a.department_id,
                dep.department_name
            HAVING COUNT(DISTINCT a.employee_id) >= 5
            ORDER BY d.month_start_date
        """).fetchdf()

        leave = con.execute("""
            SELECT
                DATE_TRUNC('month', l.start_date)::DATE
                    AS month_start_date,
                l.leave_type_code,
                t.leave_type_name,
                SUM(l.days) AS leave_days,
                COUNT(*) AS leave_requests
            FROM raw.fact_leave l
            LEFT JOIN raw.dim_leave_type t
                ON t.leave_type_code = l.leave_type_code
            WHERE l.status = 'Approved'
            GROUP BY 1, 2, 3
            ORDER BY 1
        """).fetchdf()

        calendar = con.execute("""
            SELECT
                date,
                month_start_date,
                is_weekend,
                is_holiday,
                is_working_day
            FROM raw.dim_date
            ORDER BY date
        """).fetchdf()

        return attendance, leave, calendar

    finally:
        con.close()


try:
    attendance, leave, calendar = load_data()
except Exception as exc:
    st.error(f"Unable to load attendance data: {exc}")
    st.stop()


if attendance.empty:
    st.warning("No attendance data is available.")
    st.stop()


# --------------------------------------------------
# Prepare dates
# --------------------------------------------------

for frame in (attendance, leave, calendar):
    if "month_start_date" in frame.columns:
        frame["month_start_date"] = pd.to_datetime(
            frame["month_start_date"]
        )

if "date" in calendar.columns:
    calendar["date"] = pd.to_datetime(calendar["date"])


# --------------------------------------------------
# Sidebar filters
# --------------------------------------------------

with st.sidebar:
    st.header("Filters")

    departments = sorted(
        attendance["department_name"].dropna().unique().tolist()
    )

    selected_departments = st.multiselect(
        "Department",
        departments,
        default=departments,
    )

    months = sorted(attendance["month_start_date"].unique())

    selected_months = st.date_input(
        "Date range",
        value=(
            pd.Timestamp(months[0]).date(),
            pd.Timestamp(months[-1]).date(),
        ),
        min_value=pd.Timestamp(months[0]).date(),
        max_value=pd.Timestamp(months[-1]).date(),
    )


# --------------------------------------------------
# Apply filters
# --------------------------------------------------

df = attendance[
    attendance["department_name"].isin(selected_departments)
].copy()

valid_date_range = (
    isinstance(selected_months, (tuple, list))
    and len(selected_months) == 2
)

if valid_date_range:
    start = pd.Timestamp(selected_months[0]).to_period("M").to_timestamp()
    end = pd.Timestamp(selected_months[1]).to_period("M").to_timestamp()

    df = df[df["month_start_date"].between(start, end)]

    filtered_leave = leave[
        leave["month_start_date"].between(start, end)
    ].copy()

    filtered_calendar = calendar[
        calendar["month_start_date"].between(start, end)
    ].copy()
else:
    filtered_leave = leave.copy()
    filtered_calendar = calendar.copy()

if df.empty:
    st.warning("No records match the selected filters.")
    st.stop()


# --------------------------------------------------
# Monthly attendance calculations
# --------------------------------------------------

monthly = (
    df.groupby("month_start_date", as_index=False)
    .agg(
        present_days=("present_days", "sum"),
        half_days_unpaid=("half_days_unpaid", "sum"),
        scheduled_days=("scheduled_days", "sum"),
        late_arrivals=("late_arrivals", "sum"),
        overtime_hours=("overtime_hours", "sum"),
        unpaid_absence_days=("unpaid_absence_days", "sum"),
        paid_leave_days=("paid_leave_days", "sum"),
    )
    .sort_values("month_start_date")
)

monthly["attendance_rate_pct"] = (
    100
    * (
        monthly["present_days"]
        + 0.5 * monthly["half_days_unpaid"]
    )
    / monthly["scheduled_days"].replace(0, float("nan"))
)

monthly["late_per_100_present_days"] = (
    100
    * monthly["late_arrivals"]
    / monthly["present_days"].replace(0, float("nan"))
)

monthly["attendance_change_pp"] = (
    monthly["attendance_rate_pct"].diff()
)


# --------------------------------------------------
# KPI cards
# --------------------------------------------------

latest = monthly.iloc[-1]

a, b, c, d = st.columns(4)

a.metric(
    "Latest attendance",
    f"{latest['attendance_rate_pct']:.2f}%",
)

b.metric(
    "Late arrivals",
    f"{int(monthly['late_arrivals'].sum()):,}",
)

c.metric(
    "Overtime hours",
    f"{monthly['overtime_hours'].sum():,.1f}",
)

d.metric(
    "Scheduled days",
    f"{int(monthly['scheduled_days'].sum()):,}",
)


# --------------------------------------------------
# 1. Monthly attendance trend
# --------------------------------------------------

st.subheader("1. Monthly attendance trend")

fig = px.line(
    monthly,
    x="month_start_date",
    y="attendance_rate_pct",
    markers=True,
    labels={
        "month_start_date": "Month",
        "attendance_rate_pct": "Attendance rate (%)",
    },
    hover_data={
        "scheduled_days": ":,.0f",
        "unpaid_absence_days": ":,.0f",
        "paid_leave_days": ":,.0f",
    },
)

fig.update_layout(
    template="plotly_white",
    yaxis_ticksuffix="%",
)

st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------
# 2. Attendance by department
# --------------------------------------------------

st.subheader("2. Attendance by department")

dept = (
    df.groupby("department_name", as_index=False)
    .agg(
        present_days=("present_days", "sum"),
        half_days_unpaid=("half_days_unpaid", "sum"),
        scheduled_days=("scheduled_days", "sum"),
    )
)

dept["attendance_rate_pct"] = (
    100
    * (
        dept["present_days"]
        + 0.5 * dept["half_days_unpaid"]
    )
    / dept["scheduled_days"].replace(0, float("nan"))
)

dept = dept.sort_values("attendance_rate_pct")

fig_dept = px.bar(
    dept,
    x="attendance_rate_pct",
    y="department_name",
    orientation="h",
    text="attendance_rate_pct",
    labels={
        "attendance_rate_pct": "Attendance rate (%)",
        "department_name": "Department",
    },
    hover_data={
        "scheduled_days": ":,.0f",
    },
)

fig_dept.update_traces(
    texttemplate="%{text:.2f}%",
    textposition="outside",
    cliponaxis=False,
)

# Zoom the axis to make differences easier to compare.
# The axis is explicitly labelled because it does not start at zero.
fig_dept.update_layout(
    template="plotly_white",
    xaxis_range=[80, 100],
)

st.plotly_chart(fig_dept, use_container_width=True)

st.caption(
    "Note: The department chart uses an 80–100% axis range to highlight "
    "differences. Compare the labelled values, not just the bar lengths."
)


# --------------------------------------------------
# 3. Late arrivals by month
# --------------------------------------------------

left, right = st.columns(2)

with left:
    st.subheader("3. Late arrivals by month")

    fig_late = px.bar(
        monthly,
        x="month_start_date",
        y="late_arrivals",
        labels={
            "month_start_date": "Month",
            "late_arrivals": "Late-arrival events",
        },
    )

    fig_late.update_layout(template="plotly_white")

    st.plotly_chart(fig_late, use_container_width=True)


# --------------------------------------------------
# 4. Overtime by month
# --------------------------------------------------

with right:
    st.subheader("4. Overtime by month")

    fig_overtime = px.line(
        monthly,
        x="month_start_date",
        y="overtime_hours",
        markers=True,
        labels={
            "month_start_date": "Month",
            "overtime_hours": "Overtime hours",
        },
    )

    fig_overtime.update_layout(template="plotly_white")

    st.plotly_chart(fig_overtime, use_container_width=True)


# --------------------------------------------------
# 5. Approved leave by type
# --------------------------------------------------

st.subheader("5. Approved leave by type")

if not filtered_leave.empty:
    leave_type = (
        filtered_leave.groupby("leave_type_name", as_index=False)
        .agg(
            leave_days=("leave_days", "sum"),
            requests=("leave_requests", "sum"),
        )
        .sort_values("leave_days", ascending=False)
    )

    fig_leave = px.bar(
        leave_type,
        x="leave_type_name",
        y="leave_days",
        color="leave_type_name",
        labels={
            "leave_type_name": "Leave type",
            "leave_days": "Approved leave days",
        },
        hover_data={
            "requests": True,
        },
    )

    fig_leave.update_layout(
        template="plotly_white",
        showlegend=False,
    )

    st.plotly_chart(fig_leave, use_container_width=True)

    st.dataframe(
        leave_type,
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No approved leave requests match this date range.")


st.caption(
    "Leave is grouped by the month the request starts. Requests spanning "
    "multiple months are not distributed across those months."
)


# --------------------------------------------------
# 6. Calendar context and long weekends
# --------------------------------------------------

st.subheader("6. Calendar context")

st.caption(
    "Calendar working days, holidays and weekends provide context. "
    "They do not replace employee-level scheduled days in the "
    "attendance-rate denominator."
)

if not filtered_calendar.empty:
    calendar_monthly = (
        filtered_calendar.groupby("month_start_date", as_index=False)
        .agg(
            calendar_working_days=(
                "is_working_day",
                lambda s: (s == "Y").sum(),
            ),
            holidays=(
                "is_holiday",
                lambda s: (s == "Y").sum(),
            ),
            weekend_days=(
                "is_weekend",
                lambda s: (s == "Y").sum(),
            ),
        )
        .sort_values("month_start_date")
    )

    fig_calendar = px.bar(
        calendar_monthly,
        x="month_start_date",
        y=[
            "calendar_working_days",
            "holidays",
            "weekend_days",
        ],
        barmode="group",
        labels={
            "month_start_date": "Month",
            "value": "Calendar days",
            "variable": "Day category",
        },
    )

    fig_calendar.update_layout(template="plotly_white")

    st.plotly_chart(fig_calendar, use_container_width=True)

    # Find holiday/weekend runs of at least three consecutive days.
    cal_days = filtered_calendar.sort_values("date").copy()

    cal_days["is_nonworking"] = (
        (cal_days["is_weekend"] == "Y")
        | (cal_days["is_holiday"] == "Y")
    )

    cal_days["date_gap"] = cal_days["date"].diff().dt.days

    cal_days["new_run"] = (
        (~cal_days["is_nonworking"])
        | (cal_days["date_gap"] != 1)
    )

    cal_days["run_id"] = cal_days["new_run"].cumsum()

    nonworking = cal_days[cal_days["is_nonworking"]].copy()

    if not nonworking.empty:
        runs = (
            nonworking.groupby("run_id")
            .agg(
                start_date=("date", "min"),
                end_date=("date", "max"),
                consecutive_days=("date", "count"),
            )
            .reset_index(drop=True)
        )

        long_weekends = runs[runs["consecutive_days"] >= 3]

        if not long_weekends.empty:
            st.markdown("**Long weekends / non-working runs (3+ days)**")

            st.dataframe(
                long_weekends,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(
                "No runs of three or more consecutive weekend/holiday "
                "dates were found in the selected range."
            )


# --------------------------------------------------
# 7. Unusual months and numerical findings
# --------------------------------------------------

st.subheader("7. Unusual months and numerical findings")

if len(monthly) >= 2:
    lowest = monthly.loc[monthly["attendance_rate_pct"].idxmin()]
    highest = monthly.loc[monthly["attendance_rate_pct"].idxmax()]

    declines = monthly.dropna(subset=["attendance_change_pp"])
    negative_changes = declines[
        declines["attendance_change_pp"] < 0
    ]

    st.markdown("**Finding 1 — Lowest attendance month**")

    st.write(
        f"{lowest['month_start_date']:%B %Y} had the lowest attendance "
        f"rate at {lowest['attendance_rate_pct']:.2f}%. "
        f"Scheduled days totalled {lowest['scheduled_days']:,.0f}."
    )

    st.markdown("**Finding 2 — Highest attendance month**")

    st.write(
        f"{highest['month_start_date']:%B %Y} had the highest attendance "
        f"rate at {highest['attendance_rate_pct']:.2f}%."
    )

    if not negative_changes.empty:
        largest_decline = negative_changes.loc[
            negative_changes["attendance_change_pp"].idxmin()
        ]

        previous_month = monthly[
            monthly["month_start_date"]
            < largest_decline["month_start_date"]
        ].iloc[-1]

        st.markdown("**Finding 3 — Largest monthly decline**")

        st.write(
            f"Attendance fell from {previous_month['attendance_rate_pct']:.2f}% "
            f"in {previous_month['month_start_date']:%B %Y} to "
            f"{largest_decline['attendance_rate_pct']:.2f}% in "
            f"{largest_decline['month_start_date']:%B %Y}, a change of "
            f"{largest_decline['attendance_change_pp']:.2f} percentage points."
        )

        target_month = largest_decline["month_start_date"]

        department_month = df[
            df["month_start_date"] == target_month
        ].copy()

        if not department_month.empty:
            department_month["rate"] = (
                100
                * (
                    department_month["present_days"]
                    + 0.5 * department_month["half_days_unpaid"]
                )
                / department_month["scheduled_days"].replace(
                    0, float("nan")
                )
            )

            department_month = department_month.dropna(subset=["rate"])

            if not department_month.empty:
                lowest_department = department_month.loc[
                    department_month["rate"].idxmin()
                ]

                st.write(
                    f"In that month, the lowest department rate among "
                    f"the selected departments was "
                    f"{lowest_department['department_name']} at "
                    f"{lowest_department['rate']:.2f}%, based on "
                    f"{int(lowest_department['employee_count'])} employees."
                )

    else:
        st.info(
            "No month-to-month attendance decline was found in the "
            "selected date range."
        )

else:
    st.info(
        "Select at least two months to compare attendance and identify "
        "month-to-month changes."
    )


st.info(
    "These findings identify unusual patterns, not confirmed causes. "
    "Review department-level results, approved leave and calendar context "
    "before attributing a change to a specific event."
)
