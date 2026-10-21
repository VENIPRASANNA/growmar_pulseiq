CREATE SCHEMA IF NOT EXISTS metrics;

-- M01: Headcount at month end.
CREATE OR REPLACE VIEW metrics.m01_headcount AS
SELECT
    month_start_date,
    department_id,
    headcount_end AS headcount,
    headcount_end AS group_size
FROM raw.fact_headcount_monthly
WHERE department_id <> 'D00'
  AND headcount_end >= 5;

-- M02: Hires by department and month.
CREATE OR REPLACE VIEW metrics.m02_hires AS
SELECT month_start_date, department_id,
       hires AS hires,
       headcount_end AS group_size
FROM raw.fact_headcount_monthly
WHERE department_id <> 'D00'
  AND headcount_end >= 5;

-- M03: Exits by department and month.
CREATE OR REPLACE VIEW metrics.m03_exits AS
SELECT month_start_date, department_id,
       exits AS exits,
       headcount_end AS group_size
FROM raw.fact_headcount_monthly
WHERE department_id <> 'D00'
  AND headcount_end >= 5;

-- M04: Official monthly formula = exits / starting headcount * 100.
CREATE OR REPLACE VIEW metrics.m04_attrition_monthly AS
SELECT month_start_date, department_id,
       exits,
       headcount_start,
       ROUND(100.0 * exits / NULLIF(headcount_start, 0), 2)
           AS attrition_rate_pct,
       headcount_end AS group_size
FROM raw.fact_headcount_monthly
WHERE department_id <> 'D00'
  AND headcount_end >= 10;

-- M05: Rolling 12-month exits / average month-end headcount * 100.
CREATE OR REPLACE VIEW metrics.m05_attrition_rolling_12m AS
WITH monthly AS (
    SELECT
        month_start_date, department_id, exits, headcount_end,
        COUNT(*) OVER (
            PARTITION BY department_id
            ORDER BY month_start_date
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS months_in_window,
        SUM(exits) OVER (
            PARTITION BY department_id
            ORDER BY month_start_date
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS exits_12m,
        AVG(headcount_end) OVER (
            PARTITION BY department_id
            ORDER BY month_start_date
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS avg_headcount_12m
    FROM raw.fact_headcount_monthly
)
SELECT month_start_date, department_id,
       exits_12m, avg_headcount_12m,
       ROUND(100.0 * exits_12m / NULLIF(avg_headcount_12m, 0), 2)
           AS attrition_rate_12m_pct,
       headcount_end AS group_size
FROM monthly
WHERE months_in_window = 12
  AND department_id <> 'D00'
  AND headcount_end >= 10;

-- M06: Rolling 12-month voluntary attrition rate.
CREATE OR REPLACE VIEW metrics.m06_voluntary_attrition_rate AS
WITH monthly AS (
    SELECT
        month_start_date, department_id, voluntary_exits, headcount_end,
        COUNT(*) OVER (
            PARTITION BY department_id
            ORDER BY month_start_date
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS months_in_window,
        SUM(voluntary_exits) OVER (
            PARTITION BY department_id
            ORDER BY month_start_date
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS voluntary_exits_12m,
        AVG(headcount_end) OVER (
            PARTITION BY department_id
            ORDER BY month_start_date
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS avg_headcount_12m
    FROM raw.fact_headcount_monthly
)
SELECT month_start_date, department_id,
       voluntary_exits_12m, avg_headcount_12m,
       ROUND(100.0 * voluntary_exits_12m
             / NULLIF(avg_headcount_12m, 0), 2)
           AS voluntary_attrition_rate_pct,
       headcount_end AS group_size
FROM monthly
WHERE months_in_window = 12
  AND department_id <> 'D00'
  AND headcount_end >= 10;

-- Shared clean payroll input: exclude the two verified injected duplicate records.
-- Raw source data is preserved; only published metric calculations exclude them.
CREATE OR REPLACE VIEW metrics.v_payroll_clean AS
SELECT *
FROM raw.fact_payroll
WHERE payroll_item_id NOT IN ('PI-X0001', 'PI-X0002');

-- M07: Gross pay aggregated to department-month; never publish employee salary rows.
CREATE OR REPLACE VIEW metrics.m07_gross_pay AS
SELECT d.month_start_date, p.department_id,
       ROUND(SUM(p.gross_pay), 2) AS gross_pay,
       COUNT(DISTINCT p.employee_id) AS employee_count,
       COUNT(DISTINCT p.employee_id) AS group_size
FROM metrics.v_payroll_clean p
JOIN raw.dim_date d ON d.date_key = p.date_key
GROUP BY d.month_start_date, p.department_id
HAVING COUNT(DISTINCT p.employee_id) >= 5;

-- M08: Net pay aggregated to department-month.
CREATE OR REPLACE VIEW metrics.m08_net_pay AS
SELECT d.month_start_date, p.department_id,
       ROUND(SUM(p.net_pay), 2) AS net_pay,
       COUNT(DISTINCT p.employee_id) AS employee_count,
       COUNT(DISTINCT p.employee_id) AS group_size
FROM metrics.v_payroll_clean p
JOIN raw.dim_date d ON d.date_key = p.date_key
GROUP BY d.month_start_date, p.department_id
HAVING COUNT(DISTINCT p.employee_id) >= 5;

-- M09: Employer cost aggregated to department-month.
CREATE OR REPLACE VIEW metrics.m09_payroll_employer_cost AS
SELECT d.month_start_date, p.department_id,
       ROUND(SUM(p.employer_cost), 2) AS employer_cost,
       COUNT(DISTINCT p.employee_id) AS employee_count,
       COUNT(DISTINCT p.employee_id) AS group_size
FROM metrics.v_payroll_clean p
JOIN raw.dim_date d ON d.date_key = p.date_key
GROUP BY d.month_start_date, p.department_id
HAVING COUNT(DISTINCT p.employee_id) >= 5;

-- M10: Employer cost per distinct paid employee.
CREATE OR REPLACE VIEW metrics.m10_cost_per_head AS
SELECT d.month_start_date, p.department_id,
       ROUND(SUM(p.employer_cost) /
             NULLIF(COUNT(DISTINCT p.employee_id), 0), 2) AS cost_per_head,
       COUNT(DISTINCT p.employee_id) AS employee_count,
       COUNT(DISTINCT p.employee_id) AS group_size
FROM metrics.v_payroll_clean p
JOIN raw.dim_date d ON d.date_key = p.date_key
GROUP BY d.month_start_date, p.department_id
HAVING COUNT(DISTINCT p.employee_id) >= 5;

-- M11: Overtime pay as a share of employer cost.
CREATE OR REPLACE VIEW metrics.m11_overtime_share AS
SELECT d.month_start_date, p.department_id,
       ROUND(100.0 * SUM(p.overtime_pay) /
             NULLIF(SUM(p.employer_cost), 0), 2) AS overtime_share_pct,
       COUNT(DISTINCT p.employee_id) AS employee_count,
       COUNT(DISTINCT p.employee_id) AS group_size
FROM metrics.v_payroll_clean p
JOIN raw.dim_date d ON d.date_key = p.date_key
GROUP BY d.month_start_date, p.department_id
HAVING COUNT(DISTINCT p.employee_id) >= 5;

-- M12: Variable pay as a share of gross pay.
CREATE OR REPLACE VIEW metrics.m12_variable_pay_share AS
SELECT d.month_start_date, p.department_id,
       ROUND(100.0 * SUM(p.variable_pay) /
             NULLIF(SUM(p.gross_pay), 0), 2) AS variable_pay_share_pct,
       COUNT(DISTINCT p.employee_id) AS employee_count,
       COUNT(DISTINCT p.employee_id) AS group_size
FROM metrics.v_payroll_clean p
JOIN raw.dim_date d ON d.date_key = p.date_key
GROUP BY d.month_start_date, p.department_id
HAVING COUNT(DISTINCT p.employee_id) >= 5;

-- M13: Attendance formula from the official dictionary.
CREATE OR REPLACE VIEW metrics.m13_attendance_rate AS
SELECT d.month_start_date, a.department_id,
       ROUND(100.0 * (
           SUM(a.present_days) + 0.5 * SUM(a.half_days_unpaid)
       ) / NULLIF(SUM(a.scheduled_days), 0), 2) AS attendance_rate_pct,
       COUNT(DISTINCT a.employee_id) AS employee_count,
       COUNT(DISTINCT a.employee_id) AS group_size
FROM raw.fact_attendance_monthly a
JOIN raw.dim_date d ON d.date_key = a.date_key
GROUP BY d.month_start_date, a.department_id
HAVING COUNT(DISTINCT a.employee_id) >= 5;

-- M14: Late arrivals per present day; report as a percentage.
CREATE OR REPLACE VIEW metrics.m14_late_arrival_rate AS
SELECT d.month_start_date, a.department_id,
       ROUND(100.0 * SUM(a.late_arrivals) /
             NULLIF(SUM(a.present_days), 0), 2) AS late_arrivals_per_100_present_days,
       COUNT(DISTINCT a.employee_id) AS employee_count,
       COUNT(DISTINCT a.employee_id) AS group_size
FROM raw.fact_attendance_monthly a
JOIN raw.dim_date d ON d.date_key = a.date_key
GROUP BY d.month_start_date, a.department_id
HAVING COUNT(DISTINCT a.employee_id) >= 5;

-- M15: Leave without pay days aggregated to department-month.
CREATE OR REPLACE VIEW metrics.m15_leave_without_pay_days AS
SELECT d.month_start_date, p.department_id,
       ROUND(SUM(p.lop_days), 2) AS leave_without_pay_days,
       COUNT(DISTINCT p.employee_id) AS employee_count,
       COUNT(DISTINCT p.employee_id) AS group_size
FROM metrics.v_payroll_clean p
JOIN raw.dim_date d ON d.date_key = p.date_key
GROUP BY d.month_start_date, p.department_id
HAVING COUNT(DISTINCT p.employee_id) >= 5;

-- M16: Revenue, accounts 4001-4004 only; excludes interest and GST.
CREATE OR REPLACE VIEW metrics.m16_revenue AS
SELECT
    DATE_TRUNC('month', l.entry_date)::DATE AS month_start_date,
    ROUND(-SUM(l.signed_amount_debit_positive), 2) AS revenue
FROM raw.fact_ledger l
WHERE l.account_code IN ('4001', '4002', '4003', '4004')
GROUP BY 1;

-- M17: Net profit = all 4xxx income less all 5xxx expenses.
-- Account 4900 interest income is included.
CREATE OR REPLACE VIEW metrics.m17_net_profit AS
SELECT
    DATE_TRUNC('month', l.entry_date)::DATE AS month_start_date,
    ROUND(-SUM(l.signed_amount_debit_positive), 2) AS net_profit
FROM raw.fact_ledger l
WHERE TRY_CAST(l.account_code AS INTEGER) BETWEEN 4000 AND 4999
   OR TRY_CAST(l.account_code AS INTEGER) BETWEEN 5000 AND 5999
GROUP BY 1;

-- M18: Net profit / revenue x 100.
CREATE OR REPLACE VIEW metrics.m18_operating_margin AS
SELECT r.month_start_date, r.revenue, p.net_profit,
       ROUND(100.0 * p.net_profit / NULLIF(r.revenue, 0), 2)
           AS operating_margin_pct
FROM metrics.m16_revenue r
JOIN metrics.m17_net_profit p USING (month_start_date);

-- M19: Ledger payroll accounts 5001-5005 / revenue x 100.
CREATE OR REPLACE VIEW metrics.m19_payroll_pct_revenue AS
WITH payroll_ledger AS (
    SELECT
        DATE_TRUNC('month', entry_date)::DATE AS month_start_date,
        SUM(signed_amount_debit_positive) AS payroll_cost_ledger
    FROM raw.fact_ledger
    WHERE account_code IN ('5001', '5002', '5003', '5004', '5005')
    GROUP BY 1
)
SELECT r.month_start_date,
       ROUND(p.payroll_cost_ledger, 2) AS payroll_cost_ledger,
       r.revenue,
       ROUND(100.0 * p.payroll_cost_ledger / NULLIF(r.revenue, 0), 2)
           AS payroll_pct_revenue
FROM metrics.m16_revenue r
JOIN payroll_ledger p USING (month_start_date);

-- M20: DSO = closing receivables / credit sales including GST in last 90 days * 90.
-- Invoice ledger dates are not required; invoice totals provide the GST-inclusive sales.
CREATE OR REPLACE VIEW metrics.m20_dso AS
WITH report_dates AS (
    SELECT MAX(invoice_date)::DATE AS report_date
    FROM raw.fact_invoice
),
receivables AS (
    SELECT SUM(i.balance_due) AS closing_receivables
    FROM raw.fact_invoice i
    CROSS JOIN report_dates d
    WHERE i.invoice_date <= d.report_date
      AND UPPER(COALESCE(i.status, '')) NOT IN ('DRAFT', 'CANCELLED')
),
sales_90d AS (
    SELECT SUM(i.total_amount) AS credit_sales_90d
    FROM raw.fact_invoice i
    CROSS JOIN report_dates d
    WHERE i.invoice_date > d.report_date - INTERVAL '90 days'
      AND i.invoice_date <= d.report_date
      AND UPPER(COALESCE(i.status, '')) NOT IN ('DRAFT', 'CANCELLED')
)
SELECT d.report_date,
       ROUND(r.closing_receivables, 2) AS closing_receivables,
       ROUND(s.credit_sales_90d, 2) AS credit_sales_90d,
       ROUND(90.0 * r.closing_receivables /
             NULLIF(s.credit_sales_90d, 0), 2) AS dso_days
FROM report_dates d
CROSS JOIN receivables r
CROSS JOIN sales_90d s;

-- M21: Overdue receivables by client and report date.
-- Client-level rows are sensitive; this view is internal pending an approved threshold.
CREATE OR REPLACE VIEW metrics.m21_overdue_receivables_internal AS
WITH report_dates AS (
    SELECT MAX(invoice_date)::DATE AS report_date
    FROM raw.fact_invoice
)
SELECT d.report_date, i.client_id,
       ROUND(SUM(i.balance_due), 2) AS overdue_receivables
FROM raw.fact_invoice i
CROSS JOIN report_dates d
WHERE i.due_date < d.report_date
  AND UPPER(COALESCE(i.status, '')) NOT IN ('DRAFT', 'CANCELLED')
  AND COALESCE(i.balance_due, 0) > 0
GROUP BY d.report_date, i.client_id;

-- M22: Task completion rate; cancelled tasks excluded.
CREATE OR REPLACE VIEW metrics.m22_task_completion_rate AS
SELECT
    t.team_id, t.sprint_id,
    COUNT(*) FILTER (WHERE LOWER(t.status) = 'done') AS completed_tasks,
    COUNT(*) FILTER (WHERE LOWER(t.status) <> 'cancelled') AS eligible_tasks,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE LOWER(t.status) = 'done')
        / NULLIF(COUNT(*) FILTER (
            WHERE LOWER(t.status) <> 'cancelled'
        ), 0), 2
    ) AS task_completion_rate_pct,
    COUNT(*) FILTER (WHERE LOWER(t.status) <> 'cancelled') AS group_size
FROM raw.fact_task t
GROUP BY t.team_id, t.sprint_id
HAVING COUNT(*) FILTER (WHERE LOWER(t.status) <> 'cancelled') >= 5;

-- M23: On-time delivery among completed tasks.
CREATE OR REPLACE VIEW metrics.m23_on_time_delivery_rate AS
SELECT
    t.team_id, t.sprint_id,
    COUNT(*) FILTER (
        WHERE LOWER(t.status) = 'done'
          AND UPPER(COALESCE(t.completed_on_time, '')) = 'Y'
    ) AS completed_on_time_tasks,
    COUNT(*) FILTER (WHERE LOWER(t.status) = 'done') AS completed_tasks,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE LOWER(t.status) = 'done'
              AND UPPER(COALESCE(t.completed_on_time, '')) = 'Y'
        ) / NULLIF(COUNT(*) FILTER (
            WHERE LOWER(t.status) = 'done'
        ), 0), 2
    ) AS on_time_delivery_rate_pct,
    COUNT(*) FILTER (WHERE LOWER(t.status) = 'done') AS group_size
FROM raw.fact_task t
GROUP BY t.team_id, t.sprint_id
HAVING COUNT(*) FILTER (WHERE LOWER(t.status) = 'done') >= 5;

-- M24: Velocity = story points completed in the sprint.
CREATE OR REPLACE VIEW metrics.m24_velocity AS
SELECT
    t.team_id, t.sprint_id,
    SUM(t.story_points) FILTER (WHERE LOWER(t.status) = 'done')
        AS completed_story_points,
    COUNT(*) FILTER (WHERE LOWER(t.status) = 'done') AS completed_tasks,
    COUNT(*) FILTER (WHERE LOWER(t.status) = 'done') AS group_size
FROM raw.fact_task t
GROUP BY t.team_id, t.sprint_id
HAVING COUNT(*) FILTER (WHERE LOWER(t.status) = 'done') >= 5;

-- M25: Average cycle time for completed tasks with valid dates.
CREATE OR REPLACE VIEW metrics.m25_average_cycle_time AS
SELECT
    t.team_id, t.sprint_id,
    ROUND(AVG(DATE_DIFF('day', t.started_date, t.completed_date)), 2)
        AS average_cycle_time_days,
    COUNT(*) FILTER (
        WHERE t.started_date IS NOT NULL
          AND t.completed_date IS NOT NULL
          AND t.completed_date >= t.started_date
          AND LOWER(t.status) = 'done'
    ) AS valid_completed_tasks,
    COUNT(*) FILTER (WHERE LOWER(t.status) = 'done') AS group_size
FROM raw.fact_task t
GROUP BY t.team_id, t.sprint_id
HAVING COUNT(*) FILTER (WHERE LOWER(t.status) = 'done') >= 5;

-- M26: The source feed currently contains only flagged records.
-- A flag rate cannot be inferred without the complete scored population.
CREATE OR REPLACE VIEW metrics.m26_anomaly_flag_rate AS
SELECT
    CAST(NULL AS DATE) AS month_start_date,
    CAST(NULL AS VARCHAR) AS source_dataset,
    CAST(NULL AS BIGINT) AS flagged_records,
    CAST(NULL AS BIGINT) AS scored_records,
    CAST(NULL AS DOUBLE) AS anomaly_flag_rate_pct
WHERE FALSE;

-- M27: High-risk share by department; never expose named employees.
CREATE OR REPLACE VIEW metrics.m27_high_risk_share AS
SELECT
    department_id,
    COUNT(*) FILTER (WHERE LOWER(risk_band) = 'high') AS high_risk_employees,
    COUNT(DISTINCT employee_id) AS employees_scored,
    ROUND(
        100.0 * COUNT(DISTINCT employee_id) FILTER (
            WHERE LOWER(risk_band) = 'high'
        ) / NULLIF(COUNT(DISTINCT employee_id), 0), 2
    ) AS high_risk_share_pct,
    COUNT(DISTINCT employee_id) AS group_size
FROM raw.fact_attrition_risk
GROUP BY department_id
HAVING COUNT(DISTINCT employee_id) >= 10;

-- M28: MAPE only when actual headcount exists for the forecast month.
-- ALL aggregates are excluded to avoid mixing company and department grains.
CREATE OR REPLACE VIEW metrics.m28_forecast_error_mape AS
SELECT
    f.forecast_month AS month_start_date,
    f.department_id,
    f.forecast_value,
    h.headcount_end AS actual_headcount,
    ROUND(
        100.0 * ABS(h.headcount_end - f.forecast_value)
        / NULLIF(h.headcount_end, 0), 2
    ) AS absolute_percentage_error
FROM raw.fact_forecast f
JOIN raw.fact_headcount_monthly h
  ON h.month_start_date = f.forecast_month
 AND h.department_id = f.department_id
WHERE f.metric = 'headcount_end'
  AND f.department_id <> 'ALL'
  AND h.headcount_end > 0;

-- Public metric catalog view (the source catalog retains unresolved thresholds).
CREATE OR REPLACE VIEW metrics.v_metric_catalog AS
SELECT *
FROM metrics.metric_catalog
ORDER BY metric_id;
