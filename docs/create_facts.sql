-- Generated from DuckDB raw fact schemas.
-- Creates tables only in warehouse; does not modify public or staging.
CREATE SCHEMA IF NOT EXISTS warehouse;

CREATE TABLE IF NOT EXISTS warehouse.fact_payroll (
    "payroll_item_id" TEXT,
    "run_id" TEXT,
    "employee_id" TEXT,
    "date_key" BIGINT,
    "employee_key" BIGINT,
    "period_end_date" DATE,
    "department_id" TEXT,
    "role_id" TEXT,
    "payable_days" DOUBLE PRECISION,
    "lop_days" DOUBLE PRECISION,
    "overtime_hours_paid" DOUBLE PRECISION,
    "variable_pay_type" TEXT,
    "monthly_fixed_gross" BIGINT,
    "basic" DOUBLE PRECISION,
    "hra" DOUBLE PRECISION,
    "conveyance" DOUBLE PRECISION,
    "medical" DOUBLE PRECISION,
    "special_allowance" DOUBLE PRECISION,
    "earned_fixed_pay" DOUBLE PRECISION,
    "overtime_pay" DOUBLE PRECISION,
    "variable_pay" DOUBLE PRECISION,
    "gross_pay" DOUBLE PRECISION,
    "pf_employee" DOUBLE PRECISION,
    "esi_employee" DOUBLE PRECISION,
    "professional_tax" BIGINT,
    "tds" DOUBLE PRECISION,
    "other_deductions" BIGINT,
    "total_deductions" DOUBLE PRECISION,
    "net_pay" DOUBLE PRECISION,
    "pf_employer" DOUBLE PRECISION,
    "esi_employer" DOUBLE PRECISION,
    "employer_cost" DOUBLE PRECISION,
    "headcount_flag" BIGINT,
    CONSTRAINT fact_payroll_pkey PRIMARY KEY ("payroll_item_id")
);

CREATE TABLE IF NOT EXISTS warehouse.fact_attendance_monthly (
    "attendance_fact_id" TEXT,
    "employee_id" TEXT,
    "date_key" BIGINT,
    "employee_key" BIGINT,
    "department_id" TEXT,
    "scheduled_days" BIGINT,
    "present_days" BIGINT,
    "wfh_days" BIGINT,
    "half_days_unpaid" BIGINT,
    "paid_leave_days" BIGINT,
    "unpaid_absence_days" BIGINT,
    "late_arrivals" BIGINT,
    "avg_hours_worked" DOUBLE PRECISION,
    "overtime_hours" DOUBLE PRECISION,
    "attendance_rate" DOUBLE PRECISION,
    "period_end_date" DATE,
    CONSTRAINT fact_attendance_monthly_pkey PRIMARY KEY ("attendance_fact_id")
);

CREATE TABLE IF NOT EXISTS warehouse.fact_leave (
    "leave_request_id" TEXT,
    "employee_id" TEXT,
    "employee_key" BIGINT,
    "leave_type_code" TEXT,
    "start_date_key" BIGINT,
    "end_date_key" BIGINT,
    "start_date" DATE,
    "end_date" DATE,
    "days" BIGINT,
    "status" TEXT,
    "applied_on" DATE,
    "decided_on" DATE,
    "approver_id" TEXT,
    "reason" TEXT,
    CONSTRAINT fact_leave_pkey PRIMARY KEY ("leave_request_id")
);

CREATE TABLE IF NOT EXISTS warehouse.fact_headcount_monthly (
    "date_key" BIGINT,
    "month_start_date" DATE,
    "department_id" TEXT,
    "headcount_start" BIGINT,
    "hires" BIGINT,
    "exits" BIGINT,
    "voluntary_exits" BIGINT,
    "transfers_in" BIGINT,
    "transfers_out" BIGINT,
    "headcount_end" BIGINT,
    "attrition_rate_monthly_pct" DOUBLE PRECISION,
    CONSTRAINT fact_headcount_monthly_pkey PRIMARY KEY ("date_key", "department_id")
);

CREATE TABLE IF NOT EXISTS warehouse.fact_ledger (
    "line_id" TEXT,
    "entry_id" TEXT,
    "date_key" BIGINT,
    "entry_date" DATE,
    "posting_period" TEXT,
    "financial_year" TEXT,
    "account_code" BIGINT,
    "debit" DOUBLE PRECISION,
    "credit" DOUBLE PRECISION,
    "signed_amount_debit_positive" DOUBLE PRECISION,
    "cost_center_department_id" TEXT,
    "source_type" TEXT,
    "source_id" TEXT,
    CONSTRAINT fact_ledger_pkey PRIMARY KEY ("line_id")
);

CREATE TABLE IF NOT EXISTS warehouse.fact_invoice (
    "invoice_id" TEXT,
    "invoice_number" TEXT,
    "client_id" TEXT,
    "invoice_date_key" BIGINT,
    "invoice_date" DATE,
    "due_date" DATE,
    "service_line_account" BIGINT,
    "subtotal" BIGINT,
    "gst_rate_percent" BIGINT,
    "gst_amount" BIGINT,
    "total_amount" BIGINT,
    "amount_paid" BIGINT,
    "balance_due" BIGINT,
    "status" TEXT,
    "last_payment_date" DATE,
    "days_to_pay" DOUBLE PRECISION,
    "days_past_due_at_cutoff" BIGINT,
    "ageing_bucket_at_cutoff" TEXT,
    "carried_in_from_prior_period" TEXT,
    "ledger_entry_id" TEXT,
    CONSTRAINT fact_invoice_pkey PRIMARY KEY ("invoice_id")
);

CREATE TABLE IF NOT EXISTS warehouse.fact_invoice_payment (
    "payment_id" TEXT,
    "invoice_id" TEXT,
    "payment_date_key" BIGINT,
    "payment_date" DATE,
    "amount" DOUBLE PRECISION,
    "payment_mode" TEXT,
    "reference_no" TEXT,
    "received_by" TEXT,
    "ledger_entry_id" TEXT,
    CONSTRAINT fact_invoice_payment_pkey PRIMARY KEY ("payment_id")
);

CREATE TABLE IF NOT EXISTS warehouse.fact_expense (
    "expense_id" TEXT,
    "expense_date" DATE,
    "expense_date_key" BIGINT,
    "category_account" BIGINT,
    "vendor_id" TEXT,
    "bill_reference" TEXT,
    "description" TEXT,
    "department_id" TEXT,
    "amount_excl_gst" BIGINT,
    "gst_rate_percent" BIGINT,
    "gst_amount" DOUBLE PRECISION,
    "total_amount" DOUBLE PRECISION,
    "due_date" DATE,
    "paid_date" DATE,
    "status" TEXT,
    "payment_mode" TEXT,
    "submitted_by" TEXT,
    "approved_by" TEXT,
    "ledger_entry_id" TEXT,
    "payment_ledger_entry_id" TEXT,
    CONSTRAINT fact_expense_pkey PRIMARY KEY ("expense_id")
);

CREATE TABLE IF NOT EXISTS warehouse.fact_task (
    "task_id" TEXT,
    "team_id" TEXT,
    "sprint_id" TEXT,
    "assignee_employee_id" TEXT,
    "task_type" TEXT,
    "priority" TEXT,
    "story_points" BIGINT,
    "created_date" DATE,
    "started_date" DATE,
    "due_date" DATE,
    "completed_date" DATE,
    "status" TEXT,
    "reopened_count" BIGINT,
    "cycle_time_days" DOUBLE PRECISION,
    "is_overdue_at_cutoff" TEXT,
    "completed_on_time" TEXT,
    CONSTRAINT fact_task_pkey PRIMARY KEY ("task_id")
);

CREATE TABLE IF NOT EXISTS warehouse.fact_anomaly (
    "result_id" TEXT,
    "source_dataset" TEXT,
    "record_id" TEXT,
    "employee_id" TEXT,
    "period" DATE,
    "anomaly_score" DOUBLE PRECISION,
    "flagged" TEXT,
    "reason_code" TEXT,
    "reason_text" TEXT,
    "money_at_risk" DOUBLE PRECISION,
    "model_version" TEXT,
    "scored_at" TIMESTAMP,
    "period_key" BIGINT,
    CONSTRAINT fact_anomaly_pkey PRIMARY KEY ("result_id")
);

CREATE TABLE IF NOT EXISTS warehouse.fact_attrition_risk (
    "prediction_id" TEXT,
    "employee_id" TEXT,
    "as_of_date_key" BIGINT,
    "department_id" TEXT,
    "as_of_date" DATE,
    "risk_score_12m" DOUBLE PRECISION,
    "risk_band" TEXT,
    "top_reason_1" TEXT,
    "top_reason_2" TEXT,
    "top_reason_3" TEXT,
    "model_version" TEXT,
    "model_note" TEXT,
    "employee_key" BIGINT,
    CONSTRAINT fact_attrition_risk_pkey PRIMARY KEY ("prediction_id")
);

CREATE TABLE IF NOT EXISTS warehouse.fact_forecast (
    "forecast_id" TEXT,
    "metric" TEXT,
    "department_id" TEXT,
    "forecast_month" DATE,
    "forecast_value" DOUBLE PRECISION,
    "lower_80" DOUBLE PRECISION,
    "upper_80" DOUBLE PRECISION,
    "method" TEXT,
    "trained_through" TEXT,
    "model_version" TEXT,
    "forecast_month_key" BIGINT,
    CONSTRAINT fact_forecast_pkey PRIMARY KEY ("forecast_id")
);
