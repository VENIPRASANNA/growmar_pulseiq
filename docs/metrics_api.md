# PulseIQ Metrics API and Data Lineage

## 1. Overview

The PulseIQ Metrics API exposes five governed workforce and operational
KPIs through FastAPI. It reads published aggregate views from DuckDB.

- Local base URL: http://127.0.0.1:8000
- Interactive API documentation: /docs
- OpenAPI schema: /openapi.json

## 2. Available Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | / | API welcome message |
| GET | /health | API and database health |
| GET | /metrics | List five KPI definitions |
| GET | /metrics/{metric_id} | Retrieve KPI data |
| GET | /lineage/{metric_id} | Retrieve metric lineage |
| GET | /freshness | Retrieve source freshness |

The KPI endpoint supports a limit parameter between 1 and 500.
The default limit is 100.

## 3. KPI Definitions

| ID | KPI | Formula | Source table | Published view | Grain |
|---|---|---|---|---|---|
| M01 | Headcount | Month-end headcount | raw.fact_headcount_monthly | metrics.m01_headcount | Department x month |
| M04 | Monthly Attrition Rate | Exits / headcount_start x 100 | raw.fact_headcount_monthly | metrics.m04_attrition_monthly | Department x month |
| M07 | Gross Pay | SUM(gross_pay) | raw.fact_payroll | metrics.m07_gross_pay | Department x month |
| M22 | Task Completion Rate | Completed / eligible tasks x 100 | raw.fact_task | metrics.m22_task_completion_rate | Team x sprint |
| M27 | High-Risk Share | High-risk employees / employees scored x 100 | raw.fact_attrition_risk | metrics.m27_high_risk_share | Department |

## 4. Privacy Thresholds

| KPI | Minimum group size |
|---|---:|
| M01 | 5 |
| M04 | 10 |
| M07 | 5 |
| M22 | 5 eligible tasks |
| M27 | 10 |

The published SQL views apply minimum group-size rules. The API
also checks group size before returning records.
