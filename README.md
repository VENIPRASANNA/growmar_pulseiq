# PulseIQ – Workforce Analytics & Data Engineering Platform

**GROWMAR | Data Analytics Track | Phase 1, Phase 2 & Phase 3**

---

## 1. Project Overview

PulseIQ is a workforce analytics and data engineering platform developed as part of the GROWMAR Data Analytics Track.

The project focuses on transforming raw workforce and business data into meaningful insights through data processing, ETL pipelines, data validation, data warehousing, SQL analytics and interactive dashboards.

It helps analyse employee performance, attendance, attrition, payroll expenses, financial performance, invoices, departmental operations and AI-generated business signals.

The platform provides management with a consolidated view of workforce and company performance to support data-driven decision-making.

### Project Objectives

- Process and validate raw business datasets.
- Build a structured data warehouse.
- Perform workforce and financial analysis.
- Develop interactive dashboards using Streamlit.
- Identify data quality issues and business anomalies.
- Analyse department-level performance.
- Present key business metrics through an executive scorecard.

---

## 2. Technology Stack

| Category | Technologies |
|---|---|
| Programming Language | Python 3.12 |
| Data Analysis | Pandas, NumPy |
| Database | DuckDB, PostgreSQL |
| Visualization | Streamlit, Plotly |
| Query Language | SQL |
| Data Validation | Python, pytest |
| Data Engineering | ETL Pipeline |
| Containerization | Docker |
| Version Control | Git, GitHub |

---

# 3. Project Development Phases

The PulseIQ project was developed in three phases, covering 15 tasks.

## PHASE 1 – Foundation and Initial Analytics

**Focus:** Data understanding, workforce analytics and initial dashboard development.

### Main Activities

- Analysed the provided workforce dataset.
- Explored employee and organizational information.
- Processed data for analytical purposes.
- Developed initial workforce dashboards.
- Performed exploratory analysis and visualisation.

### Key Deliverables

- Initial workforce analytics.
- Data exploration and visualisation.
- Dashboard development.
- Phase 1 project report and evidence.

**Submission:** `phase-1/`

[View Phase 1 Report](phase-1/report/phase1_report.pdf)

---

## PHASE 2 – Advanced Analytics and Data Engineering

**Focus:** Workforce performance, payroll analytics, data validation and warehouse development.

### Task 6 – ETL and Data Validation

- Implemented an ETL validation pipeline.
- Applied data contract validation rules.
- Separated valid and rejected records.
- Generated execution summaries and validation logs.

### Task 7 – Attrition Analytics

- Analysed employee attrition trends.
- Examined workforce exits and retention patterns.
- Presented attrition insights through dashboards.

### Task 8 – Team Productivity

- Analysed team-level productivity.
- Compared task completion and performance.
- Developed productivity visualisations.

### Task 9 – Payroll Cost Analytics

- Analysed payroll expenses.
- Examined department-level payroll costs.
- Presented payroll trends and cost distribution.

### Task 10 – Budget vs Actual and KPI Targets

- Compared budgeted and actual values.
- Analysed KPI performance against targets.
- Identified performance gaps and variances.

### Key Deliverables

- ETL validation pipeline.
- Clean and quarantined datasets.
- Payroll and productivity dashboards.
- Budget and KPI dashboard.
- Data validation evidence.

**Submission:** `phase-2/`

[View Phase 2 Report](phase-2/report/DataAnalytics_VeniPrasanna%20S_Phase2_Report_Final.pdf)

---

## PHASE 3 – Business Intelligence and Executive Analytics

**Focus:** Financial performance, departmental impact, AI signals and executive-level reporting.

### Task 11 – Profit & Loss and Expense Analytics

- Analysed revenue and expenses.
- Calculated net profit and operating margin.
- Examined expense distribution.
- Developed a financial performance dashboard.

### Task 12 – Invoices, Receivables and Cash Flow

- Analysed invoice records.
- Identified outstanding and overdue receivables.
- Examined cash inflows.
- Performed invoice reconciliation.

### Task 13 – Cross-Department Impact

- Compared department-level performance.
- Analysed payroll and attendance metrics.
- Identified differences across departmental data.
- Developed a cross-department comparison dashboard.

### Task 14 – AI Signals Dashboard

- Analysed anomaly records.
- Presented estimated financial exposure.
- Visualised forecast information.
- Examined attrition risk signals.
- Included human-review indicators for AI-generated insights.

### Task 15 – Executive Company Health Scorecard

Developed an executive dashboard containing eight headline KPIs:

1. Headcount
2. Monthly Attrition
3. Attendance Rate
4. Overtime Share
5. Revenue
6. Net Profit
7. Operating Margin
8. Payroll as a Percentage of Revenue

### Key Deliverables

- Profit and Loss dashboard.
- Invoice and Cash Flow dashboard.
- Cross-Department Impact dashboard.
- AI Signals dashboard.
- Executive Health Scorecard.

**Submission:** `phase-3/`

[View Phase 3 Report](phase-3/report/DataAnalytics_VeniPrasanna_Phase3_Report.pdf)

---

# 4. Project Architecture

The project follows a data processing and analytics workflow.

```text
Raw Dataset
     |
     v
Data Loading
     |
     v
ETL Processing
     |
     v
Data Validation
     |
     +------------------+
     |                  |
     v                  v
Clean Data         Rejected Data
     |
     v
Data Warehouse
     |
     v
SQL Metric Views
     |
     v
Streamlit Dashboards
     |
     v
Business Insights
```

---

# 5. Repository Structure

```text
growmar_pulseiq/
│
├── 03_Data/
│   └── csv/
│
├── 05_Starter/
│   ├── load_to_duckdb.py
│   ├── metric_views_examples.sql
│   ├── pulseiq.duckdb
│   └── requirements.txt
│
├── phase-1/
│   ├── report/
│   ├── evidence/
│   ├── deliverables/
│   └── README.md
│
├── phase-2/
│   ├── report/
│   ├── evidence/
│   ├── deliverables/
│   └── README.md
│
├── phase-3/
│   ├── report/
│   ├── evidence/
│   ├── deliverables/
│   └── README.md
│
├── data/
│   ├── clean/
│   ├── rejected/
│   └── warehouse_export/
│
├── docs/
│   ├── create_dimensions.sql
│   ├── create_facts.sql
│   ├── metric_layer.md
│   ├── star_schema.mmd
│   └── evidence/
│
├── evidence/
│
├── pages/
│   ├── 1_Workforce_Details.py
│   ├── 2_Attendance_Leave_Trends.py
│   ├── 3_Attrition_Analytics.py
│   ├── 4_Team_Productivity.py
│   ├── 5_Payroll_Cost_Dashboard.py
│   ├── 6_Budget_vs_Actual_KPI_Targets.py
│   ├── 7_Profit_Loss_Analytics.py
│   ├── 8_Invoices_Receivables_Cashflow.py
│   ├── 9_Cross_Department_Impact.py
│   ├── 10_AI_Signals_Dashboard.py
│   └── 11_Executive_Health_Scorecard.py
│
├── scripts/
├── sql/
├── src/
│   ├── etl.py
│   ├── build_warehouse.py
│   └── privacy_gate.py
│
├── tests/
├── app.py
├── Dockerfile
├── README.md
└── .gitignore
```

---

# 6. Installation and Environment Setup

### Prerequisites

Install the following before running the project:

- Python 3.12
- Git
- pip
- Virtual environment support

### Step 1 – Clone the Repository

```bash
git clone https://github.com/VENIPRASANNA/growmar_pulseiq.git
cd growmar_pulseiq
```

### Step 2 – Create a Virtual Environment

```bash
python3.12 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

### Step 3 – Install Dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r 05_Starter/requirements.txt
python -m pip install pytest
```

---

# 7. How to Run the Project

Run the following commands from the repository root.

### Step 1 – Load Data into DuckDB

```bash
cd 05_Starter
python load_to_duckdb.py
cd ..
```

### Step 2 – Execute the ETL Pipeline

```bash
python src/etl.py
```

The ETL pipeline validates four contract-covered datasets:

- `fact_anomaly`
- `fact_attrition_risk`
- `fact_forecast`
- `fact_task`

Validated records are stored in:

- `data/clean/`

Rejected records are stored in:

- `data/rejected/`

Execution summaries are stored in:

- `logs/`

### Step 3 – Run the Streamlit Application

```bash
streamlit run app.py
```

Open the application in your browser:

```text
http://localhost:8501
```

Use the sidebar to navigate between the available dashboard pages.

---

# 8. Data Warehouse and Database Design

The project includes a PostgreSQL warehouse named `pulseiq_analytics` under the `warehouse` schema.

### Warehouse Components

- 11 dimension tables.
- 12 fact tables.
- Primary and foreign key relationships.
- Historical employee mapping.
- Data quality and orphan-record checks.

### Important SQL Files

- `docs/create_dimensions.sql` – Dimension table definitions.
- `docs/create_facts.sql` – Fact table definitions.
- `sql/metric_views.sql` – Metric view definitions.
- `docs/star_schema.mmd` – Star schema diagram.

The warehouse contains fact tables for payroll, attendance, leave, headcount, ledger, invoices, invoice payments, expenses, tasks, anomalies, attrition risk and forecasts.

---

# 9. Data Validation and Testing

The project uses automated validation to identify data quality issues.

### Validation Activities

- Data contract validation.
- Missing value checks.
- Invalid record detection.
- Date validation.
- ID format validation.
- Forecast bounds validation.
- Anomaly score validation.
- Record reconciliation.

### Run Automated Tests

```bash
python -m pytest -v
```

The ETL pipeline also checks that:

**Input Records = Passed Records + Quarantined Records**

---

# 10. Docker Execution

Build the Docker image:

```bash
docker build -t pulseiq-etl .
```

Run the ETL pipeline:

```bash
docker run --rm \
  -v "$PWD/05_Starter:/app/05_Starter:ro" \
  -v "$PWD/data/clean:/app/data/clean" \
  -v "$PWD/data/rejected:/app/data/rejected" \
  -v "$PWD/logs:/app/logs" \
  pulseiq-etl
```

---

# 11. Project Outcomes

Through the three development phases, PulseIQ delivers:

- Interactive workforce analytics dashboards.
- Data cleaning and validation workflows.
- A structured data warehouse.
- Financial and operational performance analysis.
- Department-level business comparisons.
- AI-based anomaly and forecast visualisations.
- An executive company health scorecard.

The project demonstrates practical applications of data analytics, data engineering, SQL, Python and business intelligence.

---

# 12. Future Enhancements

- Integrate real-time data pipelines.
- Improve predictive analytics capabilities.
- Add automated dashboard refresh.
- Expand anomaly detection models.
- Implement role-based dashboard access.
- Deploy the application to a cloud platform.
- Improve reporting and notification features.

---

# 13. Author and Project Links

**Developer:** Veni Prasanna S

**Project:** PulseIQ – Workforce Analytics & Data Engineering Platform

**Program:** GROWMAR – Data Analytics Track

**GitHub Repository:**

https://github.com/VENIPRASANNA/growmar_pulseiq

**Project Phases:**

- [Phase 1](phase-1/README.md)
- [Phase 2](phase-