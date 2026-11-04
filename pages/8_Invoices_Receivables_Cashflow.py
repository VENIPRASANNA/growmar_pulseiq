
import streamlit as st
import duckdb
import pandas as pd
from pathlib import Path

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Invoices, Receivables & Cash Flow | PulseIQ",
    page_icon="💳",
    layout="wide"
)

st.title("💳 Invoices, Receivables & Cash Flow")
st.caption(
    "PulseIQ | Task 12 | Invoice ageing, client payment "
    "performance and cash flow analytics"
)

# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_PATH = (
    Path(__file__).resolve().parents[1]
    / "05_Starter"
    / "pulseiq.duckdb"
)


@st.cache_data(ttl=300)
def run_query(query):
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return con.execute(query).fetchdf()
    finally:
        con.close()


# ============================================================
# DATA LOADING
# ============================================================

@st.cache_data(ttl=300)
def load_data():

    # --------------------------------------------------------
    # 1. RECEIVABLES AGEING
    # --------------------------------------------------------

    ageing_query = """
    WITH open_invoices AS (
        SELECT
            invoice_id,
            balance_due,
            days_past_due_at_cutoff,
            CASE
                WHEN days_past_due_at_cutoff <= 0
                    THEN 'Not yet due'
                WHEN days_past_due_at_cutoff <= 30
                    THEN '0-30 days'
                WHEN days_past_due_at_cutoff <= 60
                    THEN '31-60 days'
                WHEN days_past_due_at_cutoff <= 90
                    THEN '61-90 days'
                ELSE '90+ days'
            END AS ageing_bucket
        FROM raw.fact_invoice
        WHERE status IN ('SENT', 'OVERDUE', 'PARTIALLY_PAID')
          AND balance_due > 0
    )

    SELECT
        ageing_bucket,
        COUNT(*) AS invoice_count,
        SUM(balance_due) AS outstanding_amount
    FROM open_invoices
    GROUP BY ageing_bucket
    ORDER BY
        CASE ageing_bucket
            WHEN 'Not yet due' THEN 1
            WHEN '0-30 days' THEN 2
            WHEN '31-60 days' THEN 3
            WHEN '61-90 days' THEN 4
            WHEN '90+ days' THEN 5
        END
    """

    ageing = run_query(ageing_query)

    # --------------------------------------------------------
    # 2. RECEIVABLES KPI
    # --------------------------------------------------------

    receivables_query = """
    SELECT
        COUNT(*) AS total_open_invoices,
        SUM(balance_due) AS total_receivables,

        SUM(
            CASE
                WHEN days_past_due_at_cutoff > 0
                THEN balance_due
                ELSE 0
            END
        ) AS overdue_receivables,

        COUNT(
            CASE
                WHEN days_past_due_at_cutoff > 0
                THEN 1
            END
        ) AS overdue_invoice_count

    FROM raw.fact_invoice
    WHERE status IN ('SENT', 'OVERDUE', 'PARTIALLY_PAID')
      AND balance_due > 0
    """

    receivables = run_query(receivables_query)

    # --------------------------------------------------------
    # 3. CLIENT PAYMENT PERFORMANCE
    # --------------------------------------------------------

    client_query = """
    SELECT
        c.client_id,
        c.client_name,
        c.payment_terms_days,
        c.payment_behaviour,
        COUNT(i.invoice_id) AS paid_invoice_count,

        ROUND(AVG(i.days_to_pay), 2)
            AS avg_days_to_pay,

        ROUND(
            AVG(i.days_to_pay) - c.payment_terms_days,
            2
        ) AS avg_days_beyond_terms

    FROM raw.fact_invoice i

    JOIN raw.dim_client c
        ON i.client_id = c.client_id

    WHERE i.status = 'PAID'
      AND i.days_to_pay IS NOT NULL

    GROUP BY
        c.client_id,
        c.client_name,
        c.payment_terms_days,
        c.payment_behaviour

    ORDER BY avg_days_to_pay DESC
    """

    clients = run_query(client_query)

    # --------------------------------------------------------
    # 4. MONTHLY CASH FLOW
    # --------------------------------------------------------

    cashflow_query = """
    WITH cash_in AS (
        SELECT
            STRFTIME(payment_date, '%Y-%m') AS month,
            SUM(amount) AS cash_inflow
        FROM raw.fact_invoice_payment
        WHERE payment_date IS NOT NULL
        GROUP BY 1
    ),

    cash_out AS (
        SELECT
            STRFTIME(paid_date, '%Y-%m') AS month,
            SUM(total_amount) AS cash_outflow
        FROM raw.fact_expense
        WHERE paid_date IS NOT NULL
          AND status = 'PAID'
        GROUP BY 1
    )

    SELECT
        COALESCE(i.month, o.month) AS month,

        COALESCE(i.cash_inflow, 0)
            AS cash_inflow,

        COALESCE(o.cash_outflow, 0)
            AS cash_outflow,

        COALESCE(i.cash_inflow, 0)
        - COALESCE(o.cash_outflow, 0)
            AS net_cash_flow

    FROM cash_in i

    FULL OUTER JOIN cash_out o
        ON i.month = o.month

    ORDER BY month
    """

    cashflow = run_query(cashflow_query)

    # --------------------------------------------------------
    # 5. CASH FLOW TOTALS
    # --------------------------------------------------------

    cash_total_query = """
    SELECT

        (
            SELECT COALESCE(SUM(amount), 0)
            FROM raw.fact_invoice_payment
            WHERE payment_date IS NOT NULL
        ) AS total_cash_inflow,

        (
            SELECT COALESCE(SUM(total_amount), 0)
            FROM raw.fact_expense
            WHERE status = 'PAID'
              AND paid_date IS NOT NULL
        ) AS total_cash_outflow
    """

    cash_totals = run_query(cash_total_query)

    # --------------------------------------------------------
    # 6. TOP OVERDUE CLIENTS
    # --------------------------------------------------------

    overdue_query = """
    SELECT
        c.client_id,
        c.client_name,
        c.payment_behaviour,
        c.payment_terms_days,

        COUNT(i.invoice_id) AS overdue_invoice_count,

        SUM(i.balance_due) AS overdue_amount,

        ROUND(
            AVG(i.days_past_due_at_cutoff), 2
        ) AS avg_days_overdue,

        MAX(i.days_past_due_at_cutoff)
            AS max_days_overdue

    FROM raw.fact_invoice i

    JOIN raw.dim_client c
        ON i.client_id = c.client_id

    WHERE i.status IN ('OVERDUE', 'PARTIALLY_PAID')
      AND i.balance_due > 0
      AND i.days_past_due_at_cutoff > 0

    GROUP BY
        c.client_id,
        c.client_name,
        c.payment_behaviour,
        c.payment_terms_days

    ORDER BY overdue_amount DESC
    """

    overdue = run_query(overdue_query)

    # --------------------------------------------------------
    # 7. INVOICE STATUS SUMMARY
    # --------------------------------------------------------

    status_query = """
    SELECT
        status,
        COUNT(*) AS invoice_count,
        SUM(total_amount) AS total_invoice_value,
        SUM(amount_paid) AS total_paid,
        SUM(balance_due) AS outstanding_amount

    FROM raw.fact_invoice

    GROUP BY status
    ORDER BY status
    """

    status = run_query(status_query)

    # --------------------------------------------------------
    # 8. RECONCILIATION
    # --------------------------------------------------------

    reconciliation_query = """
    SELECT
        COALESCE(SUM(balance_due), 0)
            AS total_open_receivables,

        COALESCE(SUM(
            CASE
                WHEN ageing_bucket_at_cutoff = '1-30 days'
                THEN balance_due ELSE 0
            END
        ), 0) AS bucket_1_30,

        COALESCE(SUM(
            CASE
                WHEN ageing_bucket_at_cutoff = 'Not yet due'
                THEN balance_due ELSE 0
            END
        ), 0) AS bucket_not_due,

        COALESCE(SUM(
            CASE
                WHEN ageing_bucket_at_cutoff = '61-90 days'
                THEN balance_due ELSE 0
            END
        ), 0) AS bucket_61_90,

        COALESCE(SUM(
            CASE
                WHEN ageing_bucket_at_cutoff = '90+ days'
                THEN balance_due ELSE 0
            END
        ), 0) AS bucket_90_plus,

        COALESCE(SUM(
            CASE
                WHEN ageing_bucket_at_cutoff = '31-60 days'
                THEN balance_due ELSE 0
            END
        ), 0) AS bucket_31_60

    FROM raw.fact_invoice

    WHERE status IN ('SENT', 'OVERDUE', 'PARTIALLY_PAID')
      AND balance_due > 0
    """

    reconciliation = run_query(reconciliation_query)

    return (
        ageing,
        receivables,
        clients,
        cashflow,
        cash_totals,
        overdue,
        status,
        reconciliation
    )


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def format_inr(value):
    value = float(value or 0)
    return f"₹{value / 10000000:.2f} Cr"


def format_rupees(value):
    value = float(value or 0)
    return f"₹{value:,.0f}"


# ============================================================
# LOAD ALL DATA
# ============================================================

try:
    (
        ageing,
        receivables,
        clients,
        cashflow,
        cash_totals,
        overdue,
        status,
        reconciliation
    ) = load_data()

except Exception as e:
    st.error(f"Unable to load dashboard data: {e}")
    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("💳 Dashboard Filters")

months = ["All Months"] + cashflow["month"].tolist()

selected_month = st.sidebar.selectbox(
    "Select Cash Flow Month",
    months
)

st.sidebar.divider()

st.sidebar.info(
    "Receivables ageing uses the dataset's stored "
    "cutoff values. The month filter applies to "
    "cash flow charts only."
)

if st.sidebar.button("🔄 Refresh Dashboard"):
    st.cache_data.clear()
    st.rerun()


# ============================================================
# FILTER CASH FLOW
# ============================================================

if selected_month == "All Months":
    filtered_cashflow = cashflow.copy()
else:
    filtered_cashflow = cashflow[
        cashflow["month"] == selected_month
    ].copy()


# ============================================================
# KPI SECTION
# ============================================================

st.subheader("📊 Financial Overview")

total_receivables = float(
    receivables.iloc[0]["total_receivables"] or 0
)

overdue_receivables = float(
    receivables.iloc[0]["overdue_receivables"] or 0
)

open_invoices = int(
    receivables.iloc[0]["total_open_invoices"] or 0
)

overdue_count = int(
    receivables.iloc[0]["overdue_invoice_count"] or 0
)

total_inflow = float(
    cash_totals.iloc[0]["total_cash_inflow"] or 0
)

total_outflow = float(
    cash_totals.iloc[0]["total_cash_outflow"] or 0
)

net_cash = total_inflow - total_outflow

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Open Receivables",
    format_inr(total_receivables),
    f"{open_invoices} invoices"
)

c2.metric(
    "Overdue Receivables",
    format_inr(overdue_receivables),
    f"{overdue_count} invoices",
    delta_color="inverse"
)

c3.metric(
    "Total Cash Inflow",
    format_inr(total_inflow)
)

c4.metric(
    "Net Cash Flow",
    format_inr(net_cash),
    delta_color="normal"
)

st.divider()


# ============================================================
# RECEIVABLES AGEING
# ============================================================

st.subheader("📅 Receivables Ageing Analysis")

st.caption(
    "Outstanding invoice balances grouped by days past due "
    "at the dataset cutoff."
)

col1, col2 = st.columns([1.5, 1])

with col1:

    ageing_chart = ageing.set_index(
        "ageing_bucket"
    )[["outstanding_amount"]]

    st.bar_chart(
        ageing_chart,
        horizontal=True,
        x_label="Outstanding Amount (₹)",
        y_label="Ageing Bucket"
    )

with col2:

    st.markdown("**Ageing Breakdown**")

    display_ageing = ageing.copy()

    display_ageing["outstanding_amount"] = (
        display_ageing["outstanding_amount"]
        .apply(format_rupees)
    )

    display_ageing.columns = [
        "Ageing Bucket",
        "Invoice Count",
        "Outstanding Amount"
    ]

    st.dataframe(
        display_ageing,
        use_container_width=True,
        hide_index=True
    )

st.divider()


# ============================================================
# CLIENT PAYMENT PERFORMANCE
# ============================================================

st.subheader("👥 Client Payment Performance")

st.caption(
    "Average payment days compared with agreed client payment terms."
)

if not clients.empty:

    client_chart_data = clients.sort_values(
        "avg_days_to_pay",
        ascending=False
    ).head(10)

    st.bar_chart(
        client_chart_data.set_index("client_name")[
            ["avg_days_to_pay"]
        ],
        horizontal=True,
        x_label="Average Days to Pay",
        y_label="Client"
    )

    st.markdown("**Detailed Client Payment Performance**")

    display_clients = clients.copy()

    display_clients.columns = [
        "Client ID",
        "Client Name",
        "Payment Terms (Days)",
        "Payment Behaviour",
        "Paid Invoice Count",
        "Average Days to Pay",
        "Days Beyond Terms"
    ]

    st.dataframe(
        display_clients,
        use_container_width=True,
        hide_index=True
    )

st.divider()


# ============================================================
# MONTHLY CASH FLOW
# ============================================================

st.subheader("💰 Monthly Cash Inflow vs Cash Outflow")

if not filtered_cashflow.empty:

    chart_data = filtered_cashflow.set_index("month")[
        ["cash_inflow", "cash_outflow"]
    ]

    st.bar_chart(
        chart_data,
        x_label="Month",
        y_label="Amount (₹)"
    )

    st.markdown("**Monthly Cash Flow Breakdown**")

    display_cashflow = filtered_cashflow.copy()

    for col in [
        "cash_inflow",
        "cash_outflow",
        "net_cash_flow"
    ]:
        display_cashflow[col] = (
            display_cashflow[col].apply(format_rupees)
        )

    display_cashflow.columns = [
        "Month",
        "Cash Inflow",
        "Cash Outflow",
        "Net Cash Flow"
    ]

    st.dataframe(
        display_cashflow,
        use_container_width=True,
        hide_index=True
    )

else:
    st.info("No cash flow records available for this month.")

st.divider()


# ============================================================
# TOP OVERDUE CLIENTS
# ============================================================

st.subheader("⚠️ Clients with Highest Overdue Balances")

if not overdue.empty:

    top_overdue = overdue.head(10).copy()

    chart_overdue = top_overdue.set_index(
        "client_name"
    )[["overdue_amount"]]

    st.bar_chart(
        chart_overdue,
        horizontal=True,
        x_label="Overdue Amount (₹)",
        y_label="Client"
    )

    display_overdue = overdue.copy()

    display_overdue["overdue_amount"] = (
        display_overdue["overdue_amount"]
        .apply(format_rupees)
    )

    display_overdue.columns = [
        "Client ID",
        "Client Name",
        "Payment Behaviour",
        "Payment Terms",
        "Overdue Invoice Count",
        "Overdue Amount",
        "Average Days Overdue",
        "Maximum Days Overdue"
    ]

    st.dataframe(
        display_overdue,
        use_container_width=True,
        hide_index=True
    )

else:
    st.success("No overdue clients found.")

st.divider()


# ============================================================
# INVOICE STATUS SUMMARY
# ============================================================

st.subheader("📄 Invoice Status Summary")

display_status = status.copy()

display_status["total_invoice_value"] = (
    display_status["total_invoice_value"]
    .apply(format_rupees)
)

display_status["total_paid"] = (
    display_status["total_paid"]
    .apply(format_rupees)
)

display_status["outstanding_amount"] = (
    display_status["outstanding_amount"]
    .apply(format_rupees)
)

display_status.columns = [
    "Invoice Status",
    "Invoice Count",
    "Total Invoice Value",
    "Total Paid",
    "Outstanding Amount"
]

st.dataframe(
    display_status,
    use_container_width=True,
    hide_index=True
)

st.divider()


# ============================================================
# RECONCILIATION
# ============================================================

st.subheader("🔍 Receivables Ageing Reconciliation")

rec = reconciliation.iloc[0]

bucket_total = (
    float(rec["bucket_not_due"] or 0)
    + float(rec["bucket_1_30"] or 0)
    + float(rec["bucket_31_60"] or 0)
    + float(rec["bucket_61_90"] or 0)
    + float(rec["bucket_90_plus"] or 0)
)

difference = float(rec["total_open_receivables"]) - bucket_total

rc1, rc2, rc3 = st.columns(3)

rc1.metric(
    "Total Open Receivables",
    format_rupees(rec["total_open_receivables"])
)

rc2.metric(
    "Total Ageing Buckets",
    format_rupees(bucket_total)
)

rc3.metric(
    "Reconciliation Difference",
    format_rupees(difference)
)

if abs(difference) < 0.01:
    st.success(
        "PASS: Ageing buckets reconcile exactly "
        "with total open receivables."
    )
else:
    st.error(
        "FAIL: Ageing buckets do not match "
        "total open receivables."
    )

st.caption(
    "Reconciliation compares stored invoice ageing buckets "
    "against the total open invoice balance."
)

st.divider()


# ============================================================
# BUSINESS INSIGHTS
# ============================================================

st.subheader("💡 Key Business Insights")

if not clients.empty:

    slowest_client = clients.iloc[0]

    fastest_client = clients.sort_values(
        "avg_days_to_pay"
    ).iloc[0]

    st.markdown(
        f"""
        - **Slowest-paying client:** {slowest_client['client_name']}
          with an average payment time of
          {slowest_client['avg_days_to_pay']} days.

        - **Fastest-paying client:** {fastest_client['client_name']}
          with an average payment time of
          {fastest_client['avg_days_to_pay']} days.

        - **Outstanding receivables:** {format_inr(total_receivables)}.

        - **Overdue receivables:** {format_inr(overdue_receivables)}.

        - **Net cash flow:** {format_inr(net_cash)} across the
          available reporting period.
        """
    )

if not overdue.empty:

    highest_overdue = overdue.iloc[0]

    longest_overdue = overdue.sort_values(
        "max_days_overdue",
        ascending=False
    ).iloc[0]

    st.markdown(
        f"""
        - **Highest overdue balance:** {highest_overdue['client_name']}
          ({format_rupees(highest_overdue['overdue_amount'])}).

        - **Longest overdue invoice:** {longest_overdue['client_name']}
          ({int(longest_overdue['max_days_overdue'])} days).
        """
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "PulseIQ | GROWMAR Data Analytics Track | "
    "Task 12 – Invoices, Receivables and Cash Flow"
)

st.caption(
    "Data source: DuckDB | Reporting period: April 2025 – "
    "September 2026 | Ageing: stored dataset cutoff"
)
