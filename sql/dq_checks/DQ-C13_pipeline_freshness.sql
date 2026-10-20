-- C13 is evaluated by scripts/run_dq_checks.py using the ETL run-log CSV.
-- This SQL checks the latest successful run after the runner loads it into
-- public.etl_run_log. An absent or stale successful run is a violation.
SELECT MAX(finished_at) AS latest_successful_run
FROM public.etl_run_log
WHERE status = 'SUCCESS'
HAVING MAX(finished_at) IS NULL
    OR MAX(finished_at) < NOW() - INTERVAL '24 hours';
