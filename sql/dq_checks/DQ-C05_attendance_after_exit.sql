-- Attendance must not occur after the employee's exit month.
SELECT a.attendance_fact_id, a.employee_id, a.period_end_date, d.exit_date
FROM warehouse.fact_attendance_monthly a
JOIN warehouse.dim_employee d ON d.employee_key = a.employee_key
WHERE d.exit_date IS NOT NULL
  AND a.period_end_date > (date_trunc('month', d.exit_date) + interval '1 month - 1 day')::date;
