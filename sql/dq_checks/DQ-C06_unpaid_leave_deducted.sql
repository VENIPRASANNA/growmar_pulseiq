-- Unpaid absence should be reflected in payroll LOP days, within 0.5 day tolerance.
WITH attendance AS (
    SELECT employee_id, period_end_date, SUM(unpaid_absence_days) AS unpaid_days
    FROM warehouse.fact_attendance_monthly
    GROUP BY employee_id, period_end_date
),
payroll AS (
    SELECT employee_id, period_end_date, SUM(lop_days) AS lop_days
    FROM warehouse.fact_payroll
    GROUP BY employee_id, period_end_date
)
SELECT a.employee_id, a.period_end_date, a.unpaid_days, COALESCE(p.lop_days, 0) AS lop_days
FROM attendance a
LEFT JOIN payroll p USING (employee_id, period_end_date)
WHERE a.unpaid_days > 0
  AND COALESCE(p.lop_days, 0) + 0.5 < a.unpaid_days;
