
import streamlit as st
import duckdb
import pandas as pd
from pathlib import Path

# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Profit & Loss Analytics | PulseIQ",
    page_icon="💰",
    layout="wide"
)

DB_PATH = (
    Path(__file__).resolve().parents[1]
    / "05_Starter"
    / "pulseiq.duckdb"
)

st.title("💰 Profit & Loss Analytics")
st.caption(
    "Financial performance, expense analysis and vendor spending | PulseIQ"
)

# --------------------------------------------------
# DATA LOADING
# --------------------------------------------------

@st.cache_data
def load_data():
    con = duckdb.connect(str(DB_PATH), read_only=True)

    # Monthly P&L
    pnl = con.execute("""
        SELECT
            l.posting_period,

            SUM(
                CASE WHEN a.account_type = 'INCOME'
                THEN l.credit - l.debit ELSE 0 END
            ) AS revenue,

            SUM(
                CASE WHEN a.account_type = 'EXPENSE'
                THEN l.debit - l.credit ELSE 0 END
            ) AS expenses

        FROM raw.fact_ledger l

        JOIN raw.dim_account a
            ON l.account_code = a.account_code

        WHERE a.statement = 'Profit & Loss'
          AND a.is_group = 'N'

        GROUP BY l.posting_period
        ORDER BY l.posting_period
    """).df()

    pnl["net_profit"] = pnl["revenue"] - pnl["expenses"]

    pnl["profit_margin"] = (
        pnl["net_profit"] / pnl["revenue"].replace(0, pd.NA)
    ) * 100

    # Expense categories
    categories = con.execute("""
        SELECT
            a.account_name AS category,
            COUNT(*) AS expense_count,
            SUM(e.amount_excl_gst) AS total_spend

        FROM raw.fact_expense e

        LEFT JOIN raw.dim_account a
            ON e.category_account = a.account_code

        GROUP BY a.account_name
        ORDER BY total_spend DESC
    """).df()

    # Vendor analysis
    vendors = con.execute("""
        SELECT
            COALESCE(v.vendor_name, 'Unknown Vendor') AS vendor_name,
            COUNT(*) AS expense_count,
            SUM(e.amount_excl_gst) AS total_spend

        FROM raw.fact_expense e

        LEFT JOIN raw.dim_vendor v
            ON e.vendor_id = v.vendor_id

        GROUP BY v.vendor_name
        ORDER BY total_spend DESC
        LIMIT 10
    """).df()

    # Expense reconciliation
    reconciliation = con.execute("""
        SELECT
            COUNT(*) AS expense_records,

            SUM(CASE
                WHEN l.entry_id IS NOT NULL THEN 1
                ELSE 0
            END) AS matched_records,

            SUM(CASE
                WHEN l.entry_id IS NULL THEN 1
                ELSE 0
            END) AS unmatched_records,

            SUM(e.amount_excl_gst) AS expense_total,

            SUM(CASE
                WHEN l.entry_id IS NOT NULL
                THEN l.debit - l.credit
                ELSE 0
            END) AS ledger_total

        FROM raw.fact_expense e

        LEFT JOIN raw.fact_ledger l
            ON e.ledger_entry_id = l.entry_id
           AND e.category_account = l.account_code
    """).df()

    con.close()

    return pnl, categories, vendors, reconciliation


# --------------------------------------------------
# CURRENCY FORMAT
# --------------------------------------------------

def format_inr(value):
    value = float(value or 0)

    if abs(value) >= 10000000:
        return f"₹{value / 10000000:.2f} Cr"

    if abs(value) >= 100000:
        return f"₹{value / 100000:.2f} L"

    return f"₹{value:,.0f}"


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

if not DB_PATH.exists():
    st.error(f"Database not found: {DB_PATH}")
    st.stop()

try:
    pnl, categories, vendors, reconciliation = load_data()
except Exception as error:
    st.error(f"Unable to load financial data: {error}")
    st.stop()

if pnl.empty:
    st.warning("No financial records available.")
    st.stop()


# --------------------------------------------------
# SIDEBAR FILTER
# --------------------------------------------------

st.sidebar.header("Financial Filters")

months = ["All Months"] + pnl["posting_period"].tolist()

selected_month = st.sidebar.selectbox(
    "Select Reporting Period",
    months
)

if selected_month == "All Months":
    filtered_pnl = pnl.copy()
    selected_label = "All 18 Reporting Months"
else:
    filtered_pnl = pnl[
        pnl["posting_period"] == selected_month
    ].copy()

    selected_label = selected_month

st.sidebar.divider()
st.sidebar.caption("Data Source: DuckDB / raw schema")
st.sidebar.caption(f"Reporting Period: {selected_label}")


# --------------------------------------------------
# FINANCIAL OVERVIEW
# --------------------------------------------------

total_revenue = filtered_pnl["revenue"].sum()
total_expenses = filtered_pnl["expenses"].sum()
net_profit = total_revenue - total_expenses

profit_margin = (
    net_profit / total_revenue * 100
    if total_revenue else 0
)

st.subheader("Financial Overview")
st.caption(f"Selected Period: {selected_label}")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Total Revenue",
    format_inr(total_revenue)
)

c2.metric(
    "Total Expenses",
    format_inr(total_expenses)
)

c3.metric(
    "Net Profit",
    format_inr(net_profit)
)

c4.metric(
    "Profit Margin",
    f"{profit_margin:.2f}%"
)


# --------------------------------------------------
# MONTHLY FINANCIAL PERFORMANCE
# --------------------------------------------------

st.divider()
st.subheader("Monthly Revenue vs Expenses")

chart_data = filtered_pnl.set_index("posting_period")[
    ["revenue", "expenses"]
]

st.line_chart(chart_data)

st.subheader("Net Profit Trend")

st.bar_chart(
    filtered_pnl.set_index("posting_period")[["net_profit"]]
)


# --------------------------------------------------
# PROFIT MARGIN
# --------------------------------------------------

st.subheader("Profit Margin Trend")

st.line_chart(
    filtered_pnl.set_index("posting_period")[["profit_margin"]]
)


# --------------------------------------------------
# EXPENSE CATEGORY ANALYSIS
# --------------------------------------------------

st.divider()
st.subheader("Expense Category Analysis")

if selected_month != "All Months":
    con = duckdb.connect(str(DB_PATH), read_only=True)

    categories_filtered = con.execute("""
        SELECT
            a.account_name AS category,
            COUNT(*) AS expense_count,
            SUM(e.amount_excl_gst) AS total_spend

        FROM raw.fact_expense e

        LEFT JOIN raw.dim_account a
            ON e.category_account = a.account_code

        WHERE strftime(e.expense_date, '%Y-%m') = ?

        GROUP BY a.account_name
        ORDER BY total_spend DESC
    """, [selected_month]).df()

    con.close()
else:
    categories_filtered = categories

if not categories_filtered.empty:
    st.bar_chart(
        categories_filtered.set_index("category")[["total_spend"]]
    )

    st.dataframe(
        categories_filtered,
        use_container_width=True,
        hide_index=True
    )


# --------------------------------------------------
# TOP 10 VENDORS
# --------------------------------------------------

st.divider()
st.subheader("Top 10 Vendors by Spending")

if selected_month != "All Months":
    con = duckdb.connect(str(DB_PATH), read_only=True)

    vendors_filtered = con.execute("""
        SELECT
            COALESCE(v.vendor_name, 'Unknown Vendor') AS vendor_name,
            COUNT(*) AS expense_count,
            SUM(e.amount_excl_gst) AS total_spend

        FROM raw.fact_expense e

        LEFT JOIN raw.dim_vendor v
            ON e.vendor_id = v.vendor_id

        WHERE strftime(e.expense_date, '%Y-%m') = ?

        GROUP BY v.vendor_name
        ORDER BY total_spend DESC
        LIMIT 10
    """, [selected_month]).df()

    con.close()
else:
    vendors_filtered = vendors

st.bar_chart(
    vendors_filtered.set_index("vendor_name")[["total_spend"]]
)

st.dataframe(
    vendors_filtered,
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# PROFIT & LOSS STATEMENT
# --------------------------------------------------

st.divider()
st.subheader("Detailed Profit & Loss Statement")

statement = pd.DataFrame({
    "Financial Metric": [
        "Total Revenue",
        "Total Expenses",
        "Net Profit",
        "Profit Margin"
    ],
    "Amount": [
        total_revenue,
        total_expenses,
        net_profit,
        profit_margin
    ]
})

statement["Amount"] = statement.apply(
    lambda row: (
        f"{row['Amount']:.2f}%"
        if row["Financial Metric"] == "Profit Margin"
        else format_inr(row["Amount"])
    ),
    axis=1
)

st.dataframe(
    statement,
    use_container_width=True,
    hide_index=True
)

# Monthly detail
st.subheader("Monthly Financial Breakdown")

display_pnl = filtered_pnl.copy()

for column in ["revenue", "expenses", "net_profit"]:
    display_pnl[column] = display_pnl[column].apply(format_inr)

display_pnl["profit_margin"] = (
    display_pnl["profit_margin"].map(
        lambda x: f"{x:.2f}%"
    )
)

st.dataframe(
    display_pnl,
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# DATA RECONCILIATION
# --------------------------------------------------

st.divider()
st.subheader("Financial Data Reconciliation")

rec = reconciliation.iloc[0]

difference = abs(
    rec["expense_total"] - rec["ledger_total"]
)

matched = int(rec["matched_records"])
unmatched = int(rec["unmatched_records"])

r1, r2, r3 = st.columns(3)

r1.metric(
    "Expense Records",
    f"{int(rec['expense_records']):,}"
)

r2.metric(
    "Matched Records",
    f"{matched:,}"
)

r3.metric(
    "Unmatched Records",
    f"{unmatched:,}"
)

st.write(
    "Expense Table Total:",
    format_inr(rec["expense_total"])
)

st.write(
    "Ledger Matched Total:",
    format_inr(rec["ledger_total"])
)

st.write(
    "Reconciliation Difference:",
    format_inr(difference)
)

if unmatched == 0 and difference < 0.01:
    st.success(
        "Reconciliation Passed: All expense records "
        "match their corresponding ledger postings."
    )
else:
    st.warning(
        "Reconciliation requires investigation."
    )


# --------------------------------------------------
# BUSINESS INSIGHTS
# --------------------------------------------------

st.divider()
st.subheader("Key Business Insights")

if not filtered_pnl.empty:

    best_profit = filtered_pnl.loc[
        filtered_pnl["net_profit"].idxmax()
    ]

    lowest_margin = filtered_pnl.loc[
        filtered_pnl["profit_margin"].idxmin()
    ]

    highest_revenue = filtered_pnl.loc[
        filtered_pnl["revenue"].idxmax()
    ]

    st.markdown(
        f"""
        - **Highest Revenue:** {highest_revenue['posting_period']}
          with {format_inr(highest_revenue['revenue'])}.
        - **Highest Net Profit:** {best_profit['posting_period']}
          with {format_inr(best_profit['net_profit'])}.
        - **Lowest Profit Margin:** {lowest_margin['posting_period']}
          with {lowest_margin['profit_margin']:.2f}%.
        """
    )

if not categories_filtered.empty:
    top_category = categories_filtered.iloc[0]

    st.markdown(
        f"- **Highest Expense Category:** {top_category['category']} "
        f"with {format_inr(top_category['total_spend'])}."
    )

if not vendors_filtered.empty:
    top_vendor = vendors_filtered.iloc[0]

    st.markdown(
        f"- **Highest Spending Vendor:** {top_vendor['vendor_name']} "
        f"with {format_inr(top_vendor['total_spend'])}."
    )


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.divider()

st.caption(
    "PulseIQ | Profit & Loss and Expense Analytics | "
    "Data sourced from DuckDB financial tables."
)
