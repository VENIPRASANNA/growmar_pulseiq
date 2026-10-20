-- Query-time privacy gate: returns metric groups whose distinct employee count is below the dictionary threshold.
-- The runner treats this as a policy/query check; it must not publish undersized groups.
SELECT m.metric_id, m.metric_name, m.minimum_group_size
FROM pulseiq.metric_dictionary m
WHERE m.minimum_group_size IS NULL;
