import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

# =========================================================
# GROWMAR PHASE 2 - TASK 9: PAYROLL COST DASHBOARD
# =========================================================

st.set_page_config(
    page_title="Payroll Cost | PulseIQ",
    page_icon="💰",
    layout="wide",
)

DB_PATH = "05_Starter/pulseiq.duckdb"

st.title("Payroll Cost Dashboard")
st.caption(
    "GROWMAR • Phase 2 • Task 9 | Payroll trends, department costs, "
    "cost per employee and reconciliation"
)

st.write(
    "Review aggregated payroll costs across departments and months. "
    "Individual payroll records and employee salary amounts are never displayed."
)


@st.cache_data(ttl=60)
def load_data():
    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        payroll = con.execute("""
            SELECT
                g.month_start_date,
                g.department_id,
                dep.department_name,
                g.gross_pay,
                n.net_pay,
                e.employer_cost,
                h.cost_per_head,
                g.employee_count,
                g.group_size
            FROM metrics.m07_gross_pay g
            JOIN metrics.m08_net_pay n
              USING (month_start_date, department_id)
            JOIN metrics.m09_payroll_employer_cost e
              USING (month_start_date, department_id)
            JOIN metrics.m10_cost_per_head h
              USING (month_start_date, department_id)
            LEFT JOIN raw.dim_department dep
              ON g.department_id = dep.department_id
            ORDER BY g.month_start_date, g.department_id
        """).df()

        reconciliation = con.execute("""
            WITH payroll AS (
                SELECT
                    d.month_start_date,
                    ROUND(SUM(p.employer_cost), 2) AS payroll_cost
                FROM metrics.v_payroll_clean p
                JOIN raw.dim_date d ON d.date_key = p.date_key
                GROUP BY d.month_start_date
            ),
            ledger AS (
                SELECT
                    CAST(
                        substr(posting_period, 1, 4) || '-' ||
                        substr(posting_period, 6, 2) || '-01'
                        AS DATE
                    ) AS month_start_date,
                    ROUND(
                        SUM(signed_amount_debit_positive), 2
                    ) AS ledger_cost
                FROM raw.fact_ledger
                WHERE source_type = 'PAYROLL_RUN'
                  AND account_code BETWEEN 5001 AND 5005
                GROUP BY 1
            )
            SELECT
                p.month_start_date,
                p.payroll_cost,
                l.ledger_cost,
                ROUND(p.payroll_cost - l.ledger_cost, 2)
                    AS difference
            FROM payroll p
            LEFT JOIN ledger l USING (month_start_date)
            ORDER BY p.month_start_date
        """).df()

        exceptions = con.execute("""
            SELECT
                payroll_item_id,
                run_id,
                employee_id,
                employee_key,
                department_id,
                period_end_date
            FROM raw.fact_payroll
            WHERE payroll_item_id IN (
                'PI-X0001', 'PI-X0002', 'PI-X0003', 'PI-X0004'
            )
            ORDER BY payroll_item_id
        """).df()

        return payroll, reconciliation, exceptions
    finally:
        con.close()


try:
    payroll, reconciliation, exceptions = load_data()
except Exception as exc:
    st.error(f"Unable to load payroll metrics: {exc}")
    st.info(
        "Run this page from the project root and confirm that the "
        "DuckDB database and official metric views exist."
    )
    st.stop()

if payroll.empty:
    st.warning("No department-month payroll groups meet the minimum group size.")
    st.stop()

payroll["month_start_date"] = pd.to_datetime(payroll["month_start_date"])
reconciliation["month_start_date"] = pd.to_datetime(
    reconciliation["month_start_date"]
)

payroll["department_label"] = (
    payroll["department_name"]
    .fillna(payroll["department_id"])
    .astype(str)
)

# =========================================================
# FILTERS
# =========================================================

st.sidebar.header("Dashboard filters")

months = sorted(payroll["month_start_date"].dropna().unique())
month_labels = {
    pd.Timestamp(m).strftime("%b %Y"): pd.Timestamp(m) for m in months
}
selected_month_labels = st.sidebar.multiselect(
    "Payroll months",
    options=list(month_labels.keys()),
    default=list(month_labels.keys()),
)

departments = sorted(payroll["department_label"].dropna().unique())
selected_departments = st.sidebar.multiselect(
    "Departments",
    options=departments,
    default=departments,
)

filtered = payroll[
    payroll["month_start_date"].isin(
        [month_labels[x] for x in selected_month_labels]
    )
    & payroll["department_label"].isin(selected_departments)
].copy()

if filtered.empty:
    st.info("No published payroll groups match the selected filters.")
    st.stop()

# =========================================================
# OVERVIEW
# =========================================================

st.subheader("Payroll overview")

# These totals are sums of department-month groups published by
# the governed views, not an unrestricted raw-table total.
gross_total = filtered["gross_pay"].sum()
net_total = filtered["net_pay"].sum()
employer_total = filtered["employer_cost"].sum()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Gross pay", f"₹{gross_total:,.0f}")
k2.metric("Net pay", f"₹{net_total:,.0f}")
k3.metric("Employer cost", f"₹{employer_total:,.0f}")
k4.metric(
    "Average cost per employee",
    f"₹{filtered['cost_per_head'].mean():,.0f}",
)

st.caption(
    "Totals above reflect only department-month groups published by the "
    "official metric views. Cost per employee is the unweighted average "
    "of the selected department-month values."
)

tab1, tab2, tab3, tab4 = st.tabs([
    "Monthly trends",
    "Department comparison",
    "Ledger reconciliation",
    "Data quality",
])

with tab1:
    st.subheader("Monthly payroll trends")

    monthly = (
        filtered.groupby("month_start_date", as_index=False)
        .agg(
            gross_pay=("gross_pay", "sum"),
            net_pay=("net_pay", "sum"),
            employer_cost=("employer_cost", "sum"),
        )
        .sort_values("month_start_date")
    )

    trend = monthly.melt(
        id_vars="month_start_date",
        value_vars=["gross_pay", "net_pay", "employer_cost"],
        var_name="cost_type",
        value_name="amount",
    )

    fig = px.line(
        trend,
        x="month_start_date",
        y="amount",
        color="cost_type",
        markers=True,
        title="Gross, net and employer cost by month",
        labels={
            "month_start_date": "Month",
            "amount": "Amount (₹)",
            "cost_type": "Cost measure",
        },
    )
    st.plotly_chart(fig, use_container_width=True)

    fig_head = px.line(
        monthly,
        x="month_start_date",
        y="employer_cost",
        markers=True,
        title="Employer cost trend",
        labels={
            "month_start_date": "Month",
            "employer_cost": "Employer cost (₹)",
        },
    )
    st.plotly_chart(fig_head, use_container_width=True)

    st.dataframe(
        monthly.rename(columns={
            "month_start_date": "Month",
            "gross_pay": "Gross pay (₹)",
            "net_pay": "Net pay (₹)",
            "employer_cost": "Employer cost (₹)",
        }),
        hide_index=True,
        use_container_width=True,
    )

with tab2:
    st.subheader("Department comparison")

    latest_month = filtered["month_start_date"].max()
    latest = filtered[
        filtered["month_start_date"] == latest_month
    ].sort_values("employer_cost", ascending=False)

    st.caption(f"Latest selected month: {latest_month:%B %Y}")

    fig_dept = px.bar(
        latest,
        x="department_label",
        y="employer_cost",
        title="Employer cost by department",
        labels={
            "department_label": "Department",
            "employer_cost": "Employer cost (₹)",
        },
    )
    st.plotly_chart(fig_dept, use_container_width=True)

    fig_head = px.bar(
        latest.sort_values("cost_per_head", ascending=False),
        x="department_label",
        y="cost_per_head",
        title="Employer cost per employee by department",
        labels={
            "department_label": "Department",
            "cost_per_head": "Cost per employee (₹)",
        },
    )
    st.plotly_chart(fig_head, use_container_width=True)

    st.dataframe(
        latest[[
            "department_label", "employee_count", "gross_pay",
            "net_pay", "employer_cost", "cost_per_head"
        ]].rename(columns={
            "department_label": "Department",
            "employee_count": "Employee count",
            "gross_pay": "Gross pay (₹)",
            "net_pay": "Net pay (₹)",
            "employer_cost": "Employer cost (₹)",
            "cost_per_head": "Cost per employee (₹)",
        }),
        hide_index=True,
        use_container_width=True,
    )

with tab3:
    st.subheader("Payroll-to-ledger reconciliation")

    st.write(
        "Payroll employer cost is compared with ledger debit-positive "
        "amounts in accounts 5001–5005 for payroll-run postings."
    )

    rec = reconciliation[
        reconciliation["month_start_date"].isin(
            filtered["month_start_date"].unique()
        )
    ].copy()

    rec["status"] = rec["difference"].apply(
        lambda x: "Reconciled" if pd.notna(x) and abs(x) <= 0.01
        else "Investigate"
    )

    fig_rec = px.bar(
        rec,
        x="month_start_date",
        y="difference",
        color="status",
        title="Payroll minus ledger cost by month",
        labels={
            "month_start_date": "Month",
            "difference": "Difference (₹)",
            "status": "Reconciliation status",
        },
    )
    st.plotly_chart(fig_rec, use_container_width=True)

    st.dataframe(
        rec.rename(columns={
            "month_start_date": "Month",
            "payroll_cost": "Payroll employer cost (₹)",
            "ledger_cost": "Ledger cost (₹)",
            "difference": "Difference (₹)",
            "status": "Status",
        }),
        hide_index=True,
        use_container_width=True,
    )

    unresolved = rec[rec["status"] == "Investigate"]
    if not unresolved.empty:
        st.warning(
            f"{len(unresolved)} selected month(s) have an unresolved "
            "payroll-to-ledger difference. Do not silently adjust these values."
        )
    else:
        st.success("Selected months reconcile within ₹0.01.")

with tab4:
    st.subheader("Data-quality and privacy notes")

    st.markdown("""
    **Governed payroll exclusions**
    - `PI-X0001` and `PI-X0002` are excluded from official payroll metrics
      because they duplicate original employee/run records.
    - Raw source records are preserved.

    **Unresolved employee mappings**
    - `PI-X0003` and `PI-X0004` use employee key `-1`.
    - They remain included according to the documented project rule.
    - No employee dimension records are invented.

    **Privacy**
    - Payroll metrics are aggregated by department and month.
    - Groups with fewer than five distinct employees are suppressed by
      the official metric views.
    - This page does not display individual payroll or salary records.
    """)

    st.markdown("**Flagged source records — metadata only**")
    st.dataframe(
        exceptions[[
            "payroll_item_id", "run_id", "employee_key",
            "department_id", "period_end_date"
        ]],
        hide_index=True,
        use_container_width=True,
    )

    st.info(
        "The employee key is included here only to explain the documented "
        "unknown-key exceptions. Individual salary amounts are not displayed."
    )

st.divider()
st.caption(
    "PulseIQ • GROWMAR Phase 2 Task 9 • Source: governed DuckDB payroll metrics"
)
