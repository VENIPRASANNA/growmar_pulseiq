-- The feed must be within seven days of its latest as-of date and scored_at within 24h of latest scoring.
SELECT prediction_id, as_of_date
FROM warehouse.fact_attrition_risk
WHERE as_of_date < (SELECT MAX(as_of_date) FROM warehouse.fact_attrition_risk) - 7;
