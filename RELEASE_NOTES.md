# PulseIQ v1.0.0 – Release Notes

**Release:** v1.0.0
**Project:** PulseIQ Analytics Dashboard
**Release Type:** Initial Final Handover
**Date:** 18 November 2026

## 1. Release Overview

PulseIQ v1.0.0 is the initial final-handover release of the PulseIQ analytics platform. It brings together workforce analytics, payroll reporting, financial performance monitoring, operational productivity analysis, AI signals, privacy controls and self-service KPI exploration.

The release also includes a metrics API, metric documentation, data lineage documentation and final reconciliation evidence.

## 2. Features Included

### 2.1 Workforce Analytics
- Monthly headcount monitoring.
- Employee movement and attrition analysis.
- Department-level workforce reporting.
- Executive workforce health scorecard.

### 2.2 Payroll and Financial Analytics
- Gross pay and net pay reporting.
- Employer payroll cost analysis.
- Payroll cost and revenue comparison.
- Revenue, net profit and operating margin monitoring.
- Receivables and Days Sales Outstanding (DSO) reporting.

### 2.3 Operational Analytics
- Task completion tracking.
- On-time delivery analysis.
- Team productivity and sprint performance.
- Operational KPI monitoring.

### 2.4 AI and KPI Exploration
- AI signals dashboard.
- Attrition-risk information.
- Self-service KPI explorer.
- Privacy-aware metric publication controls.

### 2.5 Metrics API and Documentation
The metrics API provides:
- `/health`
- `/metrics`
- `/metrics/{metric_id}`
- `/lineage/{metric_id}`
- `/freshness`

Supporting documentation includes API examples, metric definitions and metric lineage.

## 3. Data Quality and Reconciliation

The final validation executed 14 data-quality checks.

| Result | Count |
|---|---:|
| Passed | 5 |
| Failed | 9 |
| Errors | 0 |

The validation identified:
- Payroll-to-ledger reconciliation differences.
- Duplicate payroll records.
- An employee dimension-history overlap.
- Pipeline freshness issues.
- Attendance, leave, invoice and expense inconsistencies.

The September 2026 workforce reconciliation balanced at 440 employees. The difference between the 440 month-end headcount and 443 payroll employees was explained by three employees who exited during September but received partial-month payments.

The detailed results and investigation are documented in `docs/task20_final_reconciliation.md`.

## 4. Known Limitations

1. Three payroll-to-ledger reconciliation differences remain unresolved.
2. Two duplicate payroll records remain in the source data.
3. One employee dimension-history overlap requires further investigation.
4. The latest successful ETL run did not satisfy the configured 24-hour freshness requirement at the time of final validation.
5. Attendance, unpaid leave, invoice, expense and leave-date validation issues remain.
6. AI scoring freshness cannot be fully verified because `scored_at` is absent from the attrition-risk fact table.
7. The original PostgreSQL payroll and ledger loading process was not identified in the current repository.
8. Live reporting queries must apply the `can_publish()` privacy control before publishing metric groups.

These limitations are documented rather than hidden or bypassed.

## 5. Deployment and Execution

### Streamlit Application

Run the application locally using:

```bash
streamlit run app.py
```

### Metrics API

Start the API using:

```bash
uvicorn src.metrics_api:app --host 127.0.0.1 --port 8000
```

API health check:

```bash
curl http://127.0.0.1:8000/health
```

### Data Quality Validation

Run the data-quality checks using:

```bash
python scripts/run_dq_checks.py
```

The PostgreSQL connection requires the `PGPASSWORD` environment variable to be configured.

## 6. Documentation and Handover Files

Important project documentation includes:

- `docs/metrics_api.md`
- `docs/api_examples.md`
- `docs/lineage/metric_lineage.md`
- `docs/task20_final_reconciliation.md`
- `docs/data_quality_checks.md`
- `docs/metric_layer.md`

## 7. Release Status

Version `v1.0.0` represents the intended initial final-handover release.

The release tag and remote publication must be completed after final verification.

**Release note:** This version documents the delivered functionality and the known data-quality limitations. It does not claim that all reconciliation checks have passed.
