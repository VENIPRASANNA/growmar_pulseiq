-- DQ-C02: Debits and credits must balance within 0.005 per journal entry.
-- Returns journal entries that do not balance.

SELECT
    entry_id,
    ROUND(SUM(debit)::numeric, 3) AS total_debit,
    ROUND(SUM(credit)::numeric, 3) AS total_credit,
    ROUND((SUM(debit) - SUM(credit))::numeric, 3) AS difference
FROM warehouse.fact_ledger
GROUP BY entry_id
HAVING ABS(SUM(debit) - SUM(credit)) > 0.005
ORDER BY entry_id;
