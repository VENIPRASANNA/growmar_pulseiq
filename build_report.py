from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)


PROJECT_DIR = Path(__file__).resolve().parent
DB_PATH = PROJECT_DIR / "05_Starter" / "pulseiq.duckdb"
OUTPUT_DIR = PROJECT_DIR / "reports"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a PulseIQ monthly workforce report."
    )
    parser.add_argument(
        "--month",
        required=True,
        help="Reporting month in YYYY-MM format. Example: 2026-09",
    )
    parser.add_argument(
        "--db",
        default=str(DB_PATH),
        help="Path to the PulseIQ DuckDB database.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(OUTPUT_DIR),
        help="Directory where the PDF report will be saved.",
    )
    return parser.parse_args()


def get_styles():
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontSize=19,
            leading=23,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#17365D"),
            spaceAfter=5,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            fontSize=12,
            leading=14,
            textColor=colors.HexColor("#17365D"),
            spaceBefore=8,
            spaceAfter=4,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SmallNote",
            parent=styles["Normal"],
            fontSize=7.5,
            leading=9,
            textColor=colors.HexColor("#555555"),
        )
    )

    return styles


def query_df(con, sql, params=None):
    return con.execute(sql, params or []).df()



def get_thresholds(con):
    rows = query_df(
        con,
        """
        SELECT metric_id, minimum_group_size
        FROM metrics.metric_catalog
        """
    )

    thresholds = {}

    for _, row in rows.iterrows():
        metric_id = str(row["metric_id"]).lower()
        value = row["minimum_group_size"]

        if pd.isna(value):
            continue

        # Extract the numeric portion from values such as "5 tasks"
        import re
        match = re.search(r"\d+", str(value))

        if match:
            thresholds[metric_id] = int(match.group())

    return thresholds



def can_publish(metric_id, employee_count, thresholds):
    threshold = thresholds.get(metric_id.lower())

    if threshold is None:
        return True

    return employee_count is not None and employee_count >= threshold



def get_month_data(con, view_name, month_start):
    return query_df(
        con,
        f"""
        SELECT *
        FROM metrics.{view_name}
        WHERE month_start_date = ?
        """,
        [month_start],
    )


def get_latest_source_month(con, month_start):
    views = [
        "m01_headcount",
        "m04_attrition_monthly",
        "m07_gross_pay",
        "m11_overtime_share",
        "m13_attendance_rate",
        "m16_revenue",
        "m17_net_profit",
    ]

    latest_dates = []

    for view in views:
        try:
            result = con.execute(
                f"""
                SELECT MAX(month_start_date)
                FROM metrics.{view}
                WHERE month_start_date <= ?
                """,
                [month_start],
            ).fetchone()

            if result and result[0]:
                latest_dates.append(result[0])

        except Exception as error:
            print(f"Warning: Could not read metrics.{view}: {error}")

    return max(latest_dates) if latest_dates else None


def get_total(df, column):
    if df.empty or column not in df.columns:
        return None

    return pd.to_numeric(df[column], errors="coerce").sum()


def get_weighted_average(df, value_column, weight_column):
    if df.empty:
        return None

    if value_column not in df.columns or weight_column not in df.columns:
        return None

    values = pd.to_numeric(df[value_column], errors="coerce")
    weights = pd.to_numeric(df[weight_column], errors="coerce")

    valid = values.notna() & weights.notna() & (weights > 0)

    if not valid.any():
        return None

    return (values[valid] * weights[valid]).sum() / weights[valid].sum()


def format_number(value, decimals=2):
    if value is None or pd.isna(value):
        return "Unavailable"

    return f"{value:,.{decimals}f}"


def format_currency(value):
    if value is None or pd.isna(value):
        return "Unavailable"

    return f"INR {value:,.2f}"


def get_monthly_metrics(con, month_start, thresholds):
    headcount = get_month_data(con, "m01_headcount", month_start)
    attrition = get_month_data(con, "m04_attrition_monthly", month_start)
    payroll = get_month_data(con, "m07_gross_pay", month_start)
    overtime = get_month_data(con, "m11_overtime_share", month_start)
    attendance = get_month_data(con, "m13_attendance_rate", month_start)

    revenue = get_month_data(con, "m16_revenue", month_start)
    profit = get_month_data(con, "m17_net_profit", month_start)

    department = get_month_data(con, "m29_department_headcount", month_start)

    total_headcount = get_total(headcount, "headcount")

    total_exits = get_total(attrition, "exits")
    starting_headcount = get_total(attrition, "headcount_start")

    if (
        attrition.empty
        or not can_publish("m04_attrition_monthly", starting_headcount, thresholds)
    ):
        attrition_rate = None
        total_exits = None
    else:
        attrition_rate = (
            total_exits / starting_headcount * 100
            if starting_headcount and starting_headcount > 0
            else None
        )

    if not can_publish("m01_headcount", total_headcount, thresholds):
        total_headcount = None

    attendance_rate = get_weighted_average(
        attendance,
        "attendance_rate_pct",
        "employee_count",
    )

    overtime_rate = get_weighted_average(
        overtime,
        "overtime_share_pct",
        "employee_count",
    )

    gross_pay = get_total(payroll, "gross_pay")
    total_revenue = get_total(revenue, "revenue")
    net_profit = get_total(profit, "net_profit")

    net_margin = (
        net_profit / total_revenue * 100
        if total_revenue and total_revenue > 0 and net_profit is not None
        else None
    )

    # Department breakdown is suppressed if any department fails
    # the minimum group-size threshold.
    department_publishable = True

    if not department.empty:
        for _, row in department.iterrows():
            if not can_publish(
                "m01_headcount",
                row["headcount"],
                thresholds,
            ):
                department_publishable = False
                break

    if not department_publishable:
        department = pd.DataFrame()

    return {
        "headcount": total_headcount,
        "exits": total_exits,
        "attrition_rate": attrition_rate,
        "attendance_rate": attendance_rate,
        "overtime_rate": overtime_rate,
        "gross_pay": gross_pay,
        "revenue": total_revenue,
        "net_profit": net_profit,
        "net_margin": net_margin,
        "department": department,
    }


def get_previous_headcount(con, month_start):
    previous_month = pd.Timestamp(month_start) - pd.DateOffset(months=1)
    previous_month = previous_month.strftime("%Y-%m-%d")

    previous = get_month_data(
        con,
        "m01_headcount",
        previous_month,
    )

    return get_total(previous, "headcount")


def create_kpi_table(metrics):
    rows = [
        ["Metric", "Value"],
        ["Total Headcount", format_number(metrics["headcount"], 0)],
        ["Attrition Rate", format_number(metrics["attrition_rate"]) + "%"],
        ["Employee Exits", format_number(metrics["exits"], 0)],
        ["Attendance Rate", format_number(metrics["attendance_rate"]) + "%"],
        ["Overtime Share", format_number(metrics["overtime_rate"]) + "%"],
        ["Gross Payroll", format_currency(metrics["gross_pay"])],
        ["Revenue", format_currency(metrics["revenue"])],
        ["Net Profit", format_currency(metrics["net_profit"])],
        ["Net Profit Margin", format_number(metrics["net_margin"]) + "%"],
    ]

    table = Table(rows, colWidths=[75 * mm, 85 * mm])

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                    colors.white,
                    colors.HexColor("#EAF0F8"),
                ]),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    return table


def create_department_table(department):
    if department.empty:
        return Paragraph(
            "Department-level headcount breakdown suppressed due to privacy rules.",
            getSampleStyleSheet()["Normal"],
        )

    rows = [["Department", "Headcount"]]

    for _, row in department.iterrows():
        rows.append([
            str(row["department_name"]),
            format_number(row["headcount"], 0),
        ])

    table = Table(rows, colWidths=[110 * mm, 50 * mm])

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                    colors.white,
                    colors.HexColor("#EAF0F8"),
                ]),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    return table


def build_pdf(month, db_path, output_dir):
    month_start = pd.Timestamp(f"{month}-01")
    month_end = month_start + pd.offsets.MonthEnd(0)

    if not Path(db_path).exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"PulseIQ_Monthly_Report_{month}.pdf"

    con = duckdb.connect(str(db_path), read_only=True)

    try:
        thresholds = get_thresholds(con)

        metrics = get_monthly_metrics(
            con,
            month_start.strftime("%Y-%m-%d"),
            thresholds,
        )

        previous_headcount = get_previous_headcount(
            con,
            month_start.strftime("%Y-%m-%d"),
        )

        latest_source_month = get_latest_source_month(
            con,
            month_start.strftime("%Y-%m-%d"),
        )

        generated_at = datetime.now().astimezone().strftime(
            "%d %B %Y, %I:%M %p %Z"
        )

    finally:
        con.close()

    styles = get_styles()

    document = SimpleDocTemplate(
        str(output_file),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    story = []

    story.append(
        Paragraph(
            f"PulseIQ Monthly Workforce Report - {month}",
            styles["ReportTitle"],
        )
    )

    story.append(
        Paragraph(
            f"Reporting Period: {month_start.strftime('%d %B %Y')} "
            f"to {month_end.strftime('%d %B %Y')}",
            styles["Normal"],
        )
    )

    story.append(
        Paragraph(
            f"Generated: {generated_at}",
            styles["SmallNote"],
        )
    )

    latest_text = (
        latest_source_month.strftime("%B %Y")
        if latest_source_month
        else "Unavailable"
    )

    story.append(
        Paragraph(
            f"Data Cut-off: Selected reporting month {month}; "
            f"latest available source month on or before this period: "
            f"{latest_text}. The database does not contain an ingestion timestamp.",
            styles["SmallNote"],
        )
    )

    story.append(Spacer(1, 8))

    story.append(
        Paragraph("1. Executive KPI Summary", styles["SectionHeading"])
    )

    story.append(create_kpi_table(metrics))

    story.append(
        Paragraph("2. Workforce Overview", styles["SectionHeading"])
    )

    story.append(
        Paragraph(
            f"Current month headcount: "
            f"<b>{format_number(metrics['headcount'], 0)}</b>. "
            f"Previous month headcount: "
            f"<b>{format_number(previous_headcount, 0)}</b>.",
            styles["Normal"],
        )
    )

    story.append(
        Paragraph("3. Attrition Overview", styles["SectionHeading"])
    )

    story.append(
        Paragraph(
            f"Employee exits: <b>{format_number(metrics['exits'], 0)}</b>. "
            f"Monthly attrition rate: "
            f"<b>{format_number(metrics['attrition_rate'])}%</b>.",
            styles["Normal"],
        )
    )

    story.append(
        Paragraph("4. Attendance and Overtime", styles["SectionHeading"])
    )

    story.append(
        Paragraph(
            f"Weighted attendance rate: "
            f"<b>{format_number(metrics['attendance_rate'])}%</b>. "
            f"Weighted overtime share: "
            f"<b>{format_number(metrics['overtime_rate'])}%</b>.",
            styles["Normal"],
        )
    )

    story.append(
        Paragraph("5. Payroll and Financial Overview", styles["SectionHeading"])
    )

    story.append(
        Paragraph(
            f"Gross payroll: <b>{format_currency(metrics['gross_pay'])}</b>. "
            f"Revenue: <b>{format_currency(metrics['revenue'])}</b>. "
            f"Net profit: <b>{format_currency(metrics['net_profit'])}</b>. "
            f"Net profit margin: <b>{format_number(metrics['net_margin'])}%</b>.",
            styles["Normal"],
        )
    )

    story.append(
        Paragraph("6. Department-wise Headcount", styles["SectionHeading"])
    )

    story.append(create_department_table(metrics["department"]))

    story.append(
        Paragraph("7. Data Quality, Privacy and Limitations", styles["SectionHeading"])
    )

    story.append(
        Paragraph(
            "This report reads existing DuckDB metric views without recalculating "
            "source facts. Department headcount and attrition apply the M01 and "
            "M04 minimum group-size rules. Attendance and overtime are weighted "
            "by employee_count. Missing monthly values are shown as unavailable, "
            "not imputed. The database has no ingestion timestamp; the report "
            "therefore shows its generation time and latest available source "
            "month separately.",
            styles["SmallNote"],
        )
    )

    document.build(story)

    return output_file


def main():
    args = parse_args()

    try:
        datetime.strptime(args.month, "%Y-%m")
    except ValueError:
        raise SystemExit("Invalid month format. Use YYYY-MM, for example 2026-09.")

    output_file = build_pdf(
        month=args.month,
        db_path=args.db,
        output_dir=args.output_dir,
    )

    print("Report generated successfully.")
    print(f"Output: {output_file}")


if __name__ == "__main__":
    main()
