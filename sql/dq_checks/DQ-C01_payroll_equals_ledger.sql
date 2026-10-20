-- DQ-C01: Payroll employer cost must reconcile to ledger accounts 5001-5005.
-- Returns one row per month that differs by more than INR 0.01.

WITH payroll AS (
    SELECT
        TO_CHAR(period_end_date, 'YYYY-MM') AS month,
        SUM(employer_cost) AS payroll_cost
    FROM warehouse.fact_payroll
    GROUP BY 1
),
ledger AS (
    SELECT
        posting_period AS month,
        SUM(debit) AS ledger_cost
    FROM warehouse.fact_ledger
    WHERE account_code BETWEEN 5001 AND 5005
    GROUP BY 1
)
SELECT
    p.month,
    ROUND(p.payroll_cost::numeric, 2) AS payroll_cost,
    ROUND(COALESCE(l.ledger_cost, 0)::numeric, 2) AS ledger_cost,
    ROUND((p.payroll_cost - COALESCE(l.ledger_cost, 0))::numeric, 2) AS difference
FROM payroll p
LEFT JOIN ledger l USING (month)
WHERE ABS(p.payroll_cost - COALESCE(l.ledger_cost, 0)) > 0.01
ORDER BY p.month;
