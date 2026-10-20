-- Payroll employee IDs must exist in the employee dimension.
SELECT f.payroll_item_id, f.employee_id
FROM warehouse.fact_payroll f
WHERE f.employee_key <> -1
  AND NOT EXISTS (
      SELECT 1 FROM warehouse.dim_employee d
      WHERE d.employee_key = f.employee_key
        AND d.employee_id = f.employee_id
  );
