import duckdb
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "05_Starter" / "pulseiq.duckdb"

SQL = """
CREATE OR REPLACE VIEW metrics.m32_department_headcount_share AS
WITH latest_month AS (
    SELECT MAX(month_start_date) AS month_start_date
    FROM metrics.m29_department_headcount
),
department_counts AS (
    SELECT
        department_id,
        department_name,
        SUM(headcount) AS department_headcount
    FROM metrics.m29_department_headcount
    WHERE month_start_date = (SELECT month_start_date FROM latest_month)
    GROUP BY department_id, department_name
)
SELECT
    department_id,
    department_name,
    department_headcount,
    SUM(department_headcount) OVER () AS total_headcount,
    ROUND(
        100.0 * department_headcount
        / NULLIF(SUM(department_headcount) OVER (), 0),
        2
    ) AS headcount_share_pct
FROM department_counts;
"""

with duckdb.connect(str(DB)) as con:
    con.execute(SQL)
    print(con.execute("""
        SELECT *
        FROM metrics.m32_department_headcount_share
        ORDER BY department_headcount DESC
    """).fetchdf().to_string(index=False))
