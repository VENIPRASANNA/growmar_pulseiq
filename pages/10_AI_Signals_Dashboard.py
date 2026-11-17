
from pathlib import Path
import os

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# =========================================================
# GROWMAR PHASE 3 - TASK 14
# AI SIGNALS DASHBOARD
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "05_Starter" / "pulseiq.duckdb"
CLEAN_DIR = BASE_DIR / "data" / "clean"

st.set_page_config(
    page_title="AI Signals | PulseIQ",
    page_icon="🤖",
    layout="wide",
)

st.title("AI Signals Dashboard")

st.caption(
    "GROWMAR • Phase 3 • Task 14 | "
    "AI anomaly detection, financial exposure, forecasting and attrition risk"
)

st.warning(
    "AI-generated signals and forecasts are decision-support information "
    "for human review. They are not confirmed fraud, misconduct, or "
    "guaranteed future outcomes."
)



# =========================================================
# HOSTED PAGE 10 - PUBLIC AGGREGATED DASHBOARD
# =========================================================

HOSTED_MODE = (
    os.getenv("PULSEIQ_HOSTED_MODE", "").lower() == "true"
    or not DB_PATH.exists()
)

if HOSTED_MODE:
    HOSTED_DATA = BASE_DIR / "data" / "hosted"

    @st.cache_data(ttl=300)
    def load_hosted_ai_data():
        anomaly_summary = pd.read_parquet(
            HOSTED_DATA / "anomaly_summary.parquet"
        )
        forecasts = pd.read_parquet(
            HOSTED_DATA / "forecast_company.parquet"
        )
        risk_summary = pd.read_parquet(
            HOSTED_DATA / "attrition_risk_summary.parquet"
        )
        actuals = pd.read_parquet(
            HOSTED_DATA / "ai_actuals_monthly.parquet"
        )
        return anomaly_summary, forecasts, risk_summary, actuals

    try:
        anomaly_summary, forecasts, risk_summary, actuals = (
            load_hosted_ai_data()
        )
    except Exception as exc:
        st.error(f"Unable to load hosted AI dashboard data: {exc}")
        st.info("Check the curated Parquet files in data/hosted/.")
        st.stop()

    actuals["month_start_date"] = pd.to_datetime(
        actuals["month_start_date"]
    )
    forecasts["forecast_month"] = pd.to_datetime(
        forecasts["forecast_month"]
    )
    risk_summary["as_of_date"] = pd.to_datetime(
        risk_summary["as_of_date"]
    )

    cutoff = (
        actuals["month_start_date"].max()
        + pd.offsets.MonthEnd(0)
    ).strftime("%d %B %Y")
    st.info(f"Company-wide data cut-off: {cutoff}")

    # -----------------------------------------------------
    # 1. AI SIGNALS OVERVIEW
    # -----------------------------------------------------

    st.subheader("AI Signals Overview")

    total_flagged = int(anomaly_summary["flagged_count"].sum())

    known_exposure = anomaly_summary["total_exposure"].sum(
        min_count=1
    )

    high_risk_count = int(
        risk_summary.loc[
            risk_summary["risk_band"] == "High",
            "prediction_count"
        ].sum()
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Flagged Anomalies", f"{total_flagged:,}")

    if pd.notna(known_exposure):
        c2.metric(
            "Known Money at Risk",
            f"₹{known_exposure / 10000000:.2f} Cr"
        )
    else:
        c2.metric("Known Money at Risk", "Unavailable")

    c3.metric(
        "High Attrition Risk Signals",
        f"{high_risk_count:,}"
    )
    c4.metric("Forecast Records", f"{len(forecasts):,}")

    st.caption(
        "Anomaly exposure is shown only for categories that meet "
        "the publication threshold. Suppressed categories are excluded "
        "from exposure totals; unknown exposure is not treated as zero."
    )

    # -----------------------------------------------------
    # 2. ANOMALY SUMMARY
    # -----------------------------------------------------

    st.divider()
    st.subheader("1. AI Anomaly Financial Risk Summary")

    anomaly_display = anomaly_summary.copy()

    fig = px.bar(
        anomaly_display.sort_values("flagged_count", ascending=True),
        x="flagged_count",
        y="anomaly_category",
        orientation="h",
        labels={
            "flagged_count": "Flagged records",
            "anomaly_category": "Anomaly category",
        },
        title="Aggregated Flagged Anomalies by Category",
    )
    fig.update_layout(template="plotly_white", height=420)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Category-level financial exposure**")

    exposure_display = anomaly_display[
        anomaly_display["total_exposure"].notna()
    ].copy()

    if not exposure_display.empty:
        fig = px.bar(
            exposure_display.sort_values(
                "total_exposure", ascending=True
            ),
            x="total_exposure",
            y="anomaly_category",
            orientation="h",
            labels={
                "total_exposure": "Known aggregate exposure (₹)",
                "anomaly_category": "Anomaly category",
            },
            title="Known Aggregate Financial Exposure",
        )
        fig.update_layout(template="plotly_white", height=380)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No publishable aggregate exposure values are available.")

    st.dataframe(
        anomaly_display.rename(columns={
            "anomaly_category": "Anomaly Category",
            "flagged_count": "Flagged Records",
            "exposure_record_count": "Records with Exposure",
            "total_exposure": "Known Exposure (₹)",
            "average_anomaly_score": "Average Anomaly Score",
        }).round(2),
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "Small anomaly categories are combined. Their financial "
        "exposure and anomaly scores are intentionally suppressed."
    )

    # -----------------------------------------------------
    # 3. FORECAST VS ACTUAL
    # -----------------------------------------------------

    st.divider()
    st.subheader("2. Company-wide Forecast vs Actual")

    metric_labels = {
        "headcount_end": "Headcount",
        "attrition_rate_monthly_pct": "Monthly Attrition Rate (%)",
    }

    selected_metric = st.selectbox(
        "Select forecast metric",
        options=list(metric_labels.keys()),
        format_func=lambda value: metric_labels[value],
    )

    selected_forecast = forecasts[
        forecasts["metric"] == selected_metric
    ].copy()

    actual_column = (
        "actual_headcount"
        if selected_metric == "headcount_end"
        else "actual_attrition_rate_pct"
    )

    actual = actuals[
        ["month_start_date", actual_column]
    ].rename(columns={
        "month_start_date": "month",
        actual_column: "actual_value",
    }).copy()

    predicted = selected_forecast[
        [
            "forecast_month",
            "forecast_value",
            "lower_80",
            "upper_80",
        ]
    ].rename(columns={
        "forecast_month": "month",
    }).copy()

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=actual["month"],
        y=actual["actual_value"],
        mode="lines+markers",
        name="Actual",
    ))

    fig.add_trace(go.Scatter(
        x=predicted["month"],
        y=predicted["forecast_value"],
        mode="lines+markers",
        name="Forecast",
    ))

    fig.add_trace(go.Scatter(
        x=pd.concat([
            predicted["month"],
            predicted["month"][::-1],
        ]),
        y=pd.concat([
            predicted["upper_80"],
            predicted["lower_80"][::-1],
        ]),
        fill="toself",
        fillcolor="rgba(100, 149, 237, 0.16)",
        line=dict(color="rgba(255,255,255,0)"),
        name="80% Prediction Interval",
        hoverinfo="skip",
    ))

    fig.update_layout(
        template="plotly_white",
        height=430,
        title=f"Actual and Forecast: {metric_labels[selected_metric]}",
        xaxis_title="Month",
        yaxis_title=metric_labels[selected_metric],
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    forecast_meta = selected_forecast.iloc[0]

    st.caption(
        f"Model: {forecast_meta['model_version']} | "
        f"Method: {forecast_meta['method']} | "
        f"Trained through: {forecast_meta['trained_through']}"
    )

    forecast_table = selected_forecast.copy()
    forecast_table["forecast_month"] = (
        forecast_table["forecast_month"].dt.strftime("%b %Y")
    )

    st.markdown("**Forecast values and 80% prediction intervals**")
    st.dataframe(
        forecast_table[
            [
                "forecast_month",
                "forecast_value",
                "lower_80",
                "upper_80",
            ]
        ].rename(columns={
            "forecast_month": "Month",
            "forecast_value": "Forecast",
            "lower_80": "Lower 80%",
            "upper_80": "Upper 80%",
        }).round(2),
        use_container_width=True,
        hide_index=True,
    )

    comparison = predicted.merge(actual, on="month", how="inner")

    st.markdown("**Forecast error analysis**")

    if not comparison.empty:
        comparison["error"] = (
            comparison["actual_value"] - comparison["forecast_value"]
        )
        comparison["absolute_error"] = comparison["error"].abs()
        comparison["month"] = comparison["month"].dt.strftime("%b %Y")

        st.dataframe(
            comparison[
                [
                    "month",
                    "actual_value",
                    "forecast_value",
                    "error",
                    "absolute_error",
                ]
            ].rename(columns={
                "month": "Month",
                "actual_value": "Actual",
                "forecast_value": "Forecast",
                "error": "Error (Actual - Forecast)",
                "absolute_error": "Absolute Error",
            }).round(2),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "No forecast months have actual values available yet. "
            "Forecast error analysis will become available when actual "
            "results for these forecast months are recorded."
        )

    # -----------------------------------------------------
    # 4. AGGREGATED ATTRITION RISK
    # -----------------------------------------------------

    st.divider()
    st.subheader("3. Company-wide AI Attrition Risk Signals")

    risk_date = risk_summary["as_of_date"].max()
    risk_display = risk_summary[
        risk_summary["as_of_date"] == risk_date
    ].copy()

    fig = px.bar(
        risk_display,
        x="risk_band",
        y="prediction_count",
        color="risk_band",
        category_orders={
            "risk_band": ["Low", "Medium", "High"]
        },
        labels={
            "risk_band": "AI risk band",
            "prediction_count": "Aggregated predictions",
        },
        title="Company-wide Attrition Risk Distribution",
    )
    fig.update_layout(template="plotly_white", height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        risk_display[
            ["risk_band", "prediction_count"]
        ].rename(columns={
            "risk_band": "Risk Band",
            "prediction_count": "Aggregated Predictions",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "Company-wide aggregate only. Individual employees, "
        "departments, risk scores and prediction reasons are not published."
    )

    # -----------------------------------------------------
    # 5. AI TRANSPARENCY
    # -----------------------------------------------------

    st.divider()
    st.subheader("4. AI Transparency and Human Review")

    st.markdown("""
    - **Anomaly detection:** Highlights unusual patterns in the validated demo data.
    - **Financial exposure:** Shows known aggregate estimates only for publishable categories.
    - **Forecasting:** Displays company-wide predictions and supplied 80% prediction intervals.
    - **Forecast errors:** Calculated only when actual values exist for forecast months.
    - **Attrition prediction:** Published as company-wide risk-band counts only.
    - **Privacy:** Individual employee and department-level AI risk predictions are excluded.
    - **Human review:** Every signal requires verification before action.
    """)

    st.warning(
        "Model outputs can contain false positives, false negatives and "
        "uncertainty. Do not use anomaly scores or attrition predictions "
        "alone to make employment, payroll or disciplinary decisions."
    )

    st.caption(
        "Source: privacy-reviewed aggregate Parquet datasets in data/hosted/. "
        "Forecast actuals are company-wide monthly aggregates."
    )

    st.stop()


# ---------------------------------------------------------
# LOAD VALIDATED DATA
# ---------------------------------------------------------

@st.cache_data(ttl=60)
def load_ai_data():
    anomaly = pd.read_csv(CLEAN_DIR / "fact_anomaly.csv")
    forecast = pd.read_csv(CLEAN_DIR / "fact_forecast.csv")
    attrition = pd.read_csv(CLEAN_DIR / "fact_attrition_risk.csv")

    anomaly["period"] = pd.to_datetime(anomaly["period"])
    anomaly["money_at_risk"] = pd.to_numeric(
        anomaly["money_at_risk"], errors="coerce"
    )
    anomaly["anomaly_score"] = pd.to_numeric(
        anomaly["anomaly_score"], errors="coerce"
    )

    forecast["forecast_month"] = pd.to_datetime(
        forecast["forecast_month"]
    )
    forecast["forecast_value"] = pd.to_numeric(
        forecast["forecast_value"], errors="coerce"
    )
    forecast["lower_80"] = pd.to_numeric(
        forecast["lower_80"], errors="coerce"
    )
    forecast["upper_80"] = pd.to_numeric(
        forecast["upper_80"], errors="coerce"
    )

    attrition["as_of_date"] = pd.to_datetime(
        attrition["as_of_date"]
    )
    attrition["risk_score_12m"] = pd.to_numeric(
        attrition["risk_score_12m"], errors="coerce"
    )

    return anomaly, forecast, attrition


@st.cache_data(ttl=60)
def load_actuals():
    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        headcount = con.execute("""
            SELECT
                month_start_date,
                SUM(headcount) AS actual_value
            FROM metrics.m29_department_headcount
            GROUP BY month_start_date
            ORDER BY month_start_date
        """).fetchdf()

        attrition_actual = con.execute("""
            SELECT
                month_start_date,
                SUM(exits) * 100.0 /
                    NULLIF(SUM(headcount_start), 0) AS actual_value
            FROM raw.fact_headcount_monthly
            WHERE department_id <> 'D00'
            GROUP BY month_start_date
            ORDER BY month_start_date
        """).fetchdf()

        return headcount, attrition_actual

    finally:
        con.close()


try:
    anomaly, forecast, attrition = load_ai_data()
    actual_headcount, actual_attrition = load_actuals()

except Exception as exc:
    st.error(f"Unable to load AI dashboard data: {exc}")
    st.info(
        "Check the validated CSV files and DuckDB metric views."
    )
    st.stop()


# ---------------------------------------------------------
# OVERVIEW KPIs
# ---------------------------------------------------------

flagged = anomaly[
    anomaly["flagged"].astype(str).str.upper() == "Y"
].copy()

known_exposure = flagged["money_at_risk"].sum(min_count=1)

with_exposure = int(
    flagged["money_at_risk"].notna().sum()
)

without_exposure = int(
    flagged["money_at_risk"].isna().sum()
)

high_risk_count = int(
    (attrition["risk_band"] == "High").sum()
)

st.subheader("AI Signals Overview")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Flagged Anomalies",
    f"{len(flagged):,}"
)

if pd.notna(known_exposure):
    c2.metric(
        "Known Money at Risk",
        f"₹{known_exposure / 10000000:.2f} Cr"
    )
else:
    c2.metric("Known Money at Risk", "Unavailable")

c3.metric(
    "High Attrition Risk Signals",
    f"{high_risk_count:,}"
)

c4.metric(
    "Forecast Records",
    f"{len(forecast):,}"
)

st.caption(
    f"{with_exposure:,} anomaly records have a monetary estimate; "
    f"{without_exposure:,} have no monetary exposure value. "
    "Unknown exposure is not treated as zero financial risk."
)


# ---------------------------------------------------------
# 1. ANOMALY FINANCIAL RISK
# ---------------------------------------------------------

st.divider()
st.subheader("1. AI Anomaly Financial Risk Ranking")

st.write(
    "This section ranks flagged anomaly categories by the sum of "
    "their available money-at-risk estimates. Higher exposure should "
    "receive earlier human investigation."
)

risk_summary = (
    flagged.groupby("reason_code", as_index=False)
    .agg(
        anomaly_records=("result_id", "count"),
        records_with_exposure=("money_at_risk", "count"),
        money_at_risk=(
            "money_at_risk",
            lambda x: x.sum(min_count=1)
        ),
        highest_score=("anomaly_score", "max"),
    )
    .sort_values(
        "money_at_risk",
        ascending=False,
        na_position="last"
    )
)

financial_risk = risk_summary[
    risk_summary["money_at_risk"].notna()
].copy()

if not financial_risk.empty:

    fig = px.bar(
        financial_risk.sort_values("money_at_risk"),
        x="money_at_risk",
        y="reason_code",
        orientation="h",
        text="money_at_risk",
        labels={
            "money_at_risk": "Estimated money at risk (₹)",
            "reason_code": "Anomaly category",
        },
        title="Estimated Financial Exposure by Anomaly Type",
    )

    fig.update_traces(
        texttemplate="₹%{x:,.0f}",
        textposition="outside",
    )

    fig.update_layout(
        template="plotly_white",
        height=480,
    )

    st.plotly_chart(fig, use_container_width=True)

    st.caption("AI-generated, for human review.")

    largest_category = financial_risk.loc[
        financial_risk["money_at_risk"].idxmax()
    ]

    st.info(
        f"AI insight: {largest_category['reason_code']} has the "
        f"largest known estimated exposure at "
        f"₹{largest_category['money_at_risk']:,.2f}. "
        "This is an investigation priority, not proof of an incorrect payment."
    )

else:
    st.info("No monetary exposure estimates are available.")

st.markdown("**Anomaly category details**")

risk_display = risk_summary.copy()

risk_display["money_at_risk"] = (
    risk_display["money_at_risk"].map(
        lambda x: f"₹{x:,.2f}" if pd.notna(x) else "Unavailable"
    )
)

risk_display["highest_score"] = (
    risk_display["highest_score"] * 100
).round(1)

risk_display = risk_display.rename(
    columns={
        "reason_code": "Anomaly Type",
        "anomaly_records": "Records",
        "records_with_exposure": "Records with Exposure",
        "money_at_risk": "Estimated Money at Risk",
        "highest_score": "Highest Anomaly Score (%)",
    }
)

st.dataframe(
    risk_display,
    use_container_width=True,
    hide_index=True,
)

st.info(
    "Attendance-related anomalies commonly have no money-at-risk "
    "estimate. Their financial exposure is unavailable, not zero."
)


# ---------------------------------------------------------
# 2. ANOMALY SIGNAL DISTRIBUTION
# ---------------------------------------------------------

st.divider()
st.subheader("2. Anomaly Signal Distribution")

left, right = st.columns(2)

with left:

    score_data = flagged.copy()

    score_data["score_percent"] = (
        score_data["anomaly_score"] * 100
    )

    fig = px.histogram(
        score_data,
        x="score_percent",
        nbins=15,
        labels={
            "score_percent": "Anomaly score (%)",
            "count": "Records",
        },
        title="Distribution of Anomaly Scores",
    )

    fig.update_layout(
        template="plotly_white",
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)

    st.caption("AI-generated, for human review.")

    average_score = score_data["score_percent"].mean()

    st.info(
        f"AI insight: The average anomaly score is "
        f"{average_score:.1f}%. The score represents how unusual "
        "a record is according to the model, not the probability "
        "that fraud or an error has occurred."
    )


with right:

    category_counts = (
        flagged["reason_code"]
        .value_counts()
        .rename_axis("reason_code")
        .reset_index(name="records")
    )

    fig = px.bar(
        category_counts.sort_values("records"),
        x="records",
        y="reason_code",
        orientation="h",
        labels={
            "records": "Flagged records",
            "reason_code": "Anomaly category",
        },
        title="Flagged Records by Anomaly Category",
    )

    fig.update_layout(
        template="plotly_white",
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)

    st.caption("AI-generated, for human review.")

    if not category_counts.empty:
        top_category = category_counts.loc[
            category_counts["records"].idxmax()
        ]

        st.info(
            f"AI insight: {top_category['reason_code']} is the most "
            f"frequent anomaly category with "
            f"{int(top_category['records']):,} flagged records."
        )


# ---------------------------------------------------------
# 3. FORECAST VS ACTUAL
# ---------------------------------------------------------

st.divider()
st.subheader("3. Forecast vs Actual Analysis")

st.write(
    "Forecast values are shown with their supplied 80% prediction "
    "intervals. Historical actuals are displayed separately. "
    "Forecasts are estimates and are not guaranteed outcomes."
)

forecast_metrics = sorted(
    forecast["metric"].unique()
)

selected_metric = st.selectbox(
    "Select forecast metric",
    forecast_metrics,
    format_func=lambda x: {
        "headcount_end": "Headcount",
        "attrition_rate_monthly_pct": "Monthly Attrition Rate (%)",
    }.get(x, x),
)

metric_forecast = forecast[
    forecast["metric"] == selected_metric
].copy()

if selected_metric == "headcount_end":

    actual = actual_headcount.copy()
    actual_label = "Actual Headcount"
    forecast_label = "Forecast Headcount"
    y_title = "Employees"

else:

    actual = actual_attrition.copy()
    actual_label = "Actual Monthly Exit Rate (%)"
    forecast_label = "Forecast Monthly Attrition Rate (%)"
    y_title = "Rate (%)"


actual["month_start_date"] = pd.to_datetime(
    actual["month_start_date"]
)

selected_department = "ALL"

if selected_metric == "headcount_end":

    available_departments = sorted(
        metric_forecast["department_id"].unique()
    )

    selected_department = st.selectbox(
        "Select forecast department",
        available_departments,
        format_func=lambda x: (
            "Overall Organisation" if x == "ALL" else x
        ),
    )

metric_forecast = metric_forecast[
    metric_forecast["department_id"] == selected_department
].sort_values("forecast_month")


if (
    selected_metric == "headcount_end"
    and selected_department != "ALL"
):

    con = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        actual = con.execute("""
            SELECT
                month_start_date,
                headcount AS actual_value
            FROM metrics.m29_department_headcount
            WHERE department_id = ?
            ORDER BY month_start_date
        """, [selected_department]).fetchdf()

    finally:
        con.close()

    actual["month_start_date"] = pd.to_datetime(
        actual["month_start_date"]
    )


if metric_forecast.empty:

    st.warning("No forecast records are available for this selection.")
    st.stop()


# Forecast chart

fig = go.Figure()

if not actual.empty:

    fig.add_trace(
        go.Scatter(
            x=actual["month_start_date"],
            y=actual["actual_value"],
            mode="lines+markers",
            name=actual_label,
            line=dict(
                color="#247BA0",
                width=3
            ),
        )
    )


# Upper prediction boundary

fig.add_trace(
    go.Scatter(
        x=metric_forecast["forecast_month"],
        y=metric_forecast["upper_80"],
        mode="lines",
        line=dict(width=0),
        showlegend=False,
        hoverinfo="skip",
    )
)


# Lower prediction boundary and shaded interval

fig.add_trace(
    go.Scatter(
        x=metric_forecast["forecast_month"],
        y=metric_forecast["lower_80"],
        mode="lines",
        line=dict(width=0),
        fill="tonexty",
        fillcolor="rgba(255,165,0,0.20)",
        name="80% Prediction Interval",
    )
)


# Forecast line

fig.add_trace(
    go.Scatter(
        x=metric_forecast["forecast_month"],
        y=metric_forecast["forecast_value"],
        mode="lines+markers",
        name=forecast_label,
        line=dict(
            color="#E07A24",
            width=3,
            dash="dash"
        ),
    )
)

fig.update_layout(
    template="plotly_white",
    height=480,
    xaxis_title="Month",
    yaxis_title=y_title,
    legend_title="Series",
)

st.plotly_chart(fig, use_container_width=True)

st.caption("AI-generated, for human review.")

st.info(
    "AI insight: Historical actuals and future predictions are shown "
    "separately. The shaded area represents the supplied 80% prediction "
    "interval, indicating a range of model uncertainty rather than a guarantee."
)


trained_through = metric_forecast["trained_through"].iloc[0]
model_version = metric_forecast["model_version"].iloc[0]
method = metric_forecast["method"].iloc[0]

st.caption(
    f"Model: {model_version} | Method: {method} | "
    f"Trained through: {trained_through}"
)


# ---------------------------------------------------------
# FORECAST VALUES AND CONFIDENCE RANGES
# ---------------------------------------------------------

forecast_comparison = metric_forecast[
    [
        "forecast_month",
        "forecast_value",
        "lower_80",
        "upper_80",
    ]
].copy()

forecast_comparison["month_key"] = (
    forecast_comparison["forecast_month"]
    .dt.to_period("M")
)

forecast_table = forecast_comparison.copy()

forecast_table["forecast_month"] = (
    forecast_table["forecast_month"].dt.strftime("%b %Y")
)

forecast_table = forecast_table[
    [
        "forecast_month",
        "forecast_value",
        "lower_80",
        "upper_80",
    ]
]

forecast_table.columns = [
    "Forecast Month",
    "Predicted Value",
    "Lower 80% Bound",
    "Upper 80% Bound",
]

st.markdown("**Forecast values and confidence ranges**")

st.dataframe(
    forecast_table.round(2),
    use_container_width=True,
    hide_index=True,
)


# ---------------------------------------------------------
# FORECAST ERROR TABLE
# ---------------------------------------------------------

st.markdown("**Forecast error analysis**")

actual_comparison = actual.copy()

if not actual_comparison.empty:

    actual_comparison["month_key"] = (
        actual_comparison["month_start_date"]
        .dt.to_period("M")
    )

    error_table = forecast_comparison.merge(
        actual_comparison[
            ["month_key", "actual_value"]
        ],
        on="month_key",
        how="inner",
    )

else:

    error_table = pd.DataFrame()


if not error_table.empty:

    error_table["error"] = (
        error_table["actual_value"]
        - error_table["forecast_value"]
    )

    error_table["absolute_error"] = (
        error_table["error"].abs()
    )

    error_table["month"] = (
        error_table["month_key"]
        .dt.strftime("%b %Y")
    )

    error_display = error_table[
        [
            "month",
            "actual_value",
            "forecast_value",
            "error",
            "absolute_error",
        ]
    ].copy()

    error_display.columns = [
        "Month",
        "Actual Value",
        "Forecast Value",
        "Error (Actual - Forecast)",
        "Absolute Error",
    ]

    st.dataframe(
        error_display.round(2),
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "A positive error means the actual value was higher than "
        "the forecast. A negative error means it was lower."
    )

else:

    st.info(
        "No forecast months have actual values available yet. "
        "Forecast errors cannot be calculated until actual data "
        "for the forecast period is recorded."
    )


# ---------------------------------------------------------
# 4. AI ATTRITION RISK SIGNALS
# ---------------------------------------------------------

st.divider()
st.subheader("4. AI Attrition Risk Signals")

st.write(
    "This section presents validated attrition predictions aggregated "
    "by department. Individual employee identities and predictions "
    "are not displayed."
)

attrition_summary = (
    attrition.groupby(
        ["department_id", "risk_band"],
        as_index=False
    )
    .size()
    .rename(columns={"size": "prediction_count"})
)

department_totals = (
    attrition.groupby("department_id")
    .size()
)

# Suppress departments with fewer than 10 predictions

safe_departments = department_totals[
    department_totals >= 10
].index

safe_attrition = attrition[
    attrition["department_id"].isin(safe_departments)
].copy()


if not safe_attrition.empty:

    band_summary = (
        safe_attrition.groupby(
            ["department_id", "risk_band"]
        )
        .size()
        .reset_index(name="prediction_count")
    )

    fig = px.bar(
        band_summary,
        x="department_id",
        y="prediction_count",
        color="risk_band",
        barmode="stack",
        category_orders={
            "risk_band": ["Low", "Medium", "High"]
        },
        labels={
            "department_id": "Department",
            "prediction_count": "Aggregated predictions",
            "risk_band": "AI risk band",
        },
        title="Department-Level Attrition Risk Distribution",
    )

    fig.update_layout(
        template="plotly_white",
        height=450,
    )

    st.plotly_chart(fig, use_container_width=True)

    st.caption("AI-generated, for human review.")

    highest_department = (
        safe_attrition.groupby("department_id")["risk_band"]
        .apply(lambda x: (x == "High").sum())
        .sort_values(ascending=False)
    )

    if not highest_department.empty:

        top_dept = highest_department.index[0]
        top_count = int(highest_department.iloc[0])

        st.info(
            f"AI insight: Department {top_dept} has the highest "
            f"number of High-band predictions among the displayed "
            f"departments ({top_count}). This is a signal for "
            "supportive HR review, not a confirmed future departure."
        )


    # Department-level summary

    dept_risk = (
        safe_attrition.groupby("department_id")
        .agg(
            prediction_count=("prediction_id", "count"),
            high_risk=(
                "risk_band",
                lambda x: (x == "High").sum()
            ),
            medium_risk=(
                "risk_band",
                lambda x: (x == "Medium").sum()
            ),
            average_risk_score=("risk_score_12m", "mean"),
        )
        .reset_index()
    )

    dept_risk["average_risk_score"] = (
        dept_risk["average_risk_score"] * 100
    )

    st.markdown("**Aggregated department risk summary**")

    st.dataframe(
        dept_risk.round(2),
        use_container_width=True,
        hide_index=True,
    )

else:

    st.info(
        "No departments currently meet the minimum group size "
        "required for displaying aggregated attrition predictions."
    )


st.caption(
    "Departments with fewer than 10 validated predictions are "
    "suppressed. Risk scores are model estimates, not confirmed "
    "employee decisions or guaranteed departures."
)


# ---------------------------------------------------------
# 5. AI TRANSPARENCY AND LIMITATIONS
# ---------------------------------------------------------

st.divider()
st.subheader("5. AI Transparency and Human Review")

st.markdown("""
- **Anomaly detection:** Identifies unusual patterns in payroll and attendance data.
- **Financial exposure:** Uses the supplied `money_at_risk` estimates only where available.
- **Forecasting:** Displays predicted values and the supplied 80% prediction interval.
- **Forecast errors:** Calculated only when actual values exist for forecast months.
- **Attrition prediction:** Uses the validated 425-record population and aggregates results by department.
- **Human review:** Every flagged anomaly and risk signal requires verification against source records before action.
""")

st.warning(
    "Model outputs can contain false positives, false negatives and "
    "uncertainty. Do not use anomaly scores or attrition predictions "
    "alone to make employment, payroll or disciplinary decisions."
)

st.caption(
    "Source: PulseIQ validated AI outputs in data/clean/. "
    "Forecast actuals are sourced from governed DuckDB metrics. "
    "Dashboard is for analytical support and human review."
)
