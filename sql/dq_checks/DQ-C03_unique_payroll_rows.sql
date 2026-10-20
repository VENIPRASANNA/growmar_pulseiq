-- DQ-C03: One payroll row per employee per payroll run.
-- Returns duplicate employee/run combinations.

SELECT
    employee_id,
    run_id,
    COUNT(*) AS duplicate_count
FROM warehouse.fact_payroll
GROUP BY employee_id, run_id
HAVING COUNT(*) > 1
ORDER BY run_id, employee_id;
