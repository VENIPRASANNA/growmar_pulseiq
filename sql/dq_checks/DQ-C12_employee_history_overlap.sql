SELECT a.employee_id, a.employee_key AS earlier_key, b.employee_key AS later_key,
       a.valid_from AS earlier_from, a.valid_to AS earlier_to,
       b.valid_from AS later_from, b.valid_to AS later_to
FROM warehouse.dim_employee a
JOIN warehouse.dim_employee b
  ON a.employee_id = b.employee_id
 AND a.employee_key < b.employee_key
 AND a.valid_from <= b.valid_to
 AND b.valid_from <= a.valid_to;
