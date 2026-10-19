-- Generated from DuckDB raw dimension schemas.
-- Creates tables only in warehouse; does not modify public.
CREATE SCHEMA IF NOT EXISTS warehouse;

CREATE TABLE IF NOT EXISTS warehouse.dim_department (
    department_id VARCHAR NOT NULL,
    department_name VARCHAR,
    cost_center VARCHAR,
    description VARCHAR,
    is_leadership VARCHAR,
    CONSTRAINT dim_department_pkey PRIMARY KEY (department_id)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_role (
    role_id VARCHAR NOT NULL,
    department_id VARCHAR,
    role_title VARCHAR,
    level BIGINT,
    grade VARCHAR,
    band_min_annual BIGINT,
    band_mid_annual BIGINT,
    band_max_annual BIGINT,
    overtime_eligible VARCHAR,
    band_reference_year BIGINT,
    CONSTRAINT dim_role_pkey PRIMARY KEY (role_id)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_location (
    work_location VARCHAR NOT NULL,
    state VARCHAR,
    city_tier VARCHAR,
    tier_number BIGINT,
    CONSTRAINT dim_location_pkey PRIMARY KEY (work_location)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_leave_type (
    leave_type_code VARCHAR NOT NULL,
    leave_type_name VARCHAR,
    pay_type VARCHAR,
    annual_quota_days BIGINT,
    prorated_for_joiners VARCHAR,
    carry_forward_allowed VARCHAR,
    max_carry_forward_days BIGINT,
    policy_note VARCHAR,
    CONSTRAINT dim_leave_type_pkey PRIMARY KEY (leave_type_code)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_account (
    account_code BIGINT NOT NULL,
    account_name VARCHAR,
    account_type VARCHAR,
    normal_balance VARCHAR,
    parent_code DOUBLE PRECISION,
    is_group VARCHAR,
    statement VARCHAR,
    is_active VARCHAR,
    CONSTRAINT dim_account_pkey PRIMARY KEY (account_code)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_client (
    client_id VARCHAR NOT NULL,
    client_name VARCHAR,
    industry VARCHAR,
    city VARCHAR,
    state_or_region VARCHAR,
    country VARCHAR,
    client_type VARCHAR,
    gst_registration VARCHAR,
    payment_terms_days BIGINT,
    payment_behaviour VARCHAR,
    primary_service_line BIGINT,
    contact_email VARCHAR,
    onboarded_on DATE,
    is_active VARCHAR,
    CONSTRAINT dim_client_pkey PRIMARY KEY (client_id)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_vendor (
    vendor_id VARCHAR NOT NULL,
    vendor_name VARCHAR,
    primary_expense_account BIGINT,
    payment_terms_days BIGINT,
    city VARCHAR,
    gst_registration VARCHAR,
    is_active VARCHAR,
    CONSTRAINT dim_vendor_pkey PRIMARY KEY (vendor_id)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_team (
    team_id VARCHAR NOT NULL,
    team_name VARCHAR,
    department_id VARCHAR,
    team_lead_employee_id VARCHAR,
    active_members BIGINT,
    planning_cadence VARCHAR,
    board_tool VARCHAR,
    CONSTRAINT dim_team_pkey PRIMARY KEY (team_id)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_sprint (
    sprint_id VARCHAR NOT NULL,
    sprint_name VARCHAR,
    start_date DATE,
    end_date DATE,
    working_days BIGINT,
    financial_year VARCHAR,
    CONSTRAINT dim_sprint_pkey PRIMARY KEY (sprint_id)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_employee (
    employee_key BIGINT NOT NULL,
    employee_id VARCHAR,
    full_name VARCHAR,
    gender VARCHAR,
    date_of_birth DATE,
    hire_date DATE,
    exit_date DATE,
    employment_status VARCHAR,
    employment_type VARCHAR,
    department_id VARCHAR,
    role_id VARCHAR,
    role_title VARCHAR,
    job_level BIGINT,
    manager_id VARCHAR,
    work_location VARCHAR,
    work_mode VARCHAR,
    highest_education VARCHAR,
    valid_from DATE,
    valid_to DATE,
    is_current VARCHAR,
    change_reason VARCHAR,
    CONSTRAINT dim_employee_pkey PRIMARY KEY (employee_key)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_date (
    date DATE,
    date_key BIGINT NOT NULL,
    year BIGINT,
    quarter BIGINT,
    month_number BIGINT,
    month_name VARCHAR,
    year_month VARCHAR,
    week_of_year BIGINT,
    day_of_week VARCHAR,
    is_weekend VARCHAR,
    is_holiday VARCHAR,
    is_working_day VARCHAR,
    financial_year VARCHAR,
    fiscal_quarter VARCHAR,
    fiscal_month_number BIGINT,
    is_month_end VARCHAR,
    month_start_date DATE,
    month_end_date DATE,
    CONSTRAINT dim_date_pkey PRIMARY KEY (date_key)
);
