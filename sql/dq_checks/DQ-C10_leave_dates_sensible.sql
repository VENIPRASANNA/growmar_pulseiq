SELECT leave_request_id, start_date, end_date
FROM warehouse.fact_leave
WHERE end_date < start_date;
