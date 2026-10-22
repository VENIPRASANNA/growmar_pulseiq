"""Create governed aggregate views for the Task 5 workforce dashboard."""
import duckdb

DB_PATH = "05_Starter/pulseiq.duckdb"

SQL = """
CREATE SCHEMA IF NOT EXISTS metrics;

CREATE OR REPLACE VIEW metrics.m29_department_headcount AS
SELECT
    h.month_start_date,
    h.department_id,
    d.department_name,
    h.headcount,
    h.group_size
FROM metrics.m01_headcount h
JOIN raw.dim_department d USING (department_id);

CREATE OR REPLACE VIEW metrics.m30_location_tier_headcount AS
WITH current_people AS (
    SELECT DISTINCT employee_id, work_location, work_mode
    FROM raw.dim_employee
    WHERE is_current = 'Y'
),
location_counts AS (
    SELECT
        l.city_tier,
        l.tier_number,
        COUNT(DISTINCT p.employee_id) AS headcount
    FROM current_people p
    JOIN raw.dim_location l USING (work_location)
    GROUP BY l.city_tier, l.tier_number
)
SELECT city_tier, tier_number, headcount
FROM location_counts
WHERE headcount >= 5;

CREATE OR REPLACE VIEW metrics.m31_work_mode_headcount AS
SELECT
    work_mode,
    COUNT(DISTINCT employee_id) AS headcount
FROM raw.dim_employee
WHERE is_current = 'Y'
GROUP BY work_mode
HAVING COUNT(DISTINCT employee_id) >= 5;
"""

def main():
    con = duckdb.connect(DB_PATH)
    try:
        con.execute(SQL)
        for view in (
            "m29_department_headcount",
            "m30_location_tier_headcount",
            "m31_work_mode_headcount",
        ):
            count = con.execute(
                f"SELECT COUNT(*) FROM metrics.{view}"
            ).fetchone()[0]
            print(f"metrics.{view}: {count} rows")
    finally:
        con.close()

if __name__ == "__main__":
    main()
