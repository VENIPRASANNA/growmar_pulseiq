SELECT task_id, started_date, completed_date, status
FROM warehouse.fact_task
WHERE completed_date < started_date
   OR (status = 'Done' AND completed_date IS NULL);
