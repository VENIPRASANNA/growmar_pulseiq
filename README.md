# PulseIQ — ETL Data Validation Pipeline

## 1. Project Overview

PulseIQ is a data engineering project that loads workforce analytics data, validates records against data contracts, and separates valid records from rejected records.

**Technology stack:** Python 3.12, Pandas, DuckDB, pytest, and Docker.

## 2. Project Structure

- `03_Data/` — Source dataset and CSV files.
- `05_Starter/` — DuckDB database, data loader, and dependencies.
- `src/etl.py` — ETL validation pipeline.
- `tests/test_etl.py` — Automated validation-rule tests.
- `data/clean/` — Validated records.
- `data/rejected/` — Quarantined records and validation reasons.
- `logs/` — ETL execution summaries.
- `Dockerfile` — Container configuration.

## 3. Environment Setup

Activate the Python virtual environment and install dependencies:

```bash
source .venv/bin/activate
python -m pip install -r 05_Starter/requirements.txt
python -m pip install pytest
```

## 4. Load Raw Data

Run the starter loader from the project root:

```bash
cd 05_Starter
python load_to_duckdb.py
cd ..
```

## 5. Run the ETL Pipeline

```bash
python src/etl.py
```

The pipeline validates four contract-covered tables: `fact_anomaly`, `fact_attrition_risk`, `fact_forecast`, and `fact_task`.

Clean records are written to `data/clean/`. Rejected records, including validation reasons, are written to `data/rejected/`.

Execution summaries are written to `logs/etl_summary.csv` and `logs/etl_summary.json`.

The pipeline checks that input rows equal passed rows plus quarantined rows.

## 6. Docker Execution

Build the image:

```bash
docker build -t pulseiq-etl .
```

Run the pipeline:

```bash
docker run --rm \
  -v "$PWD/05_Starter:/app/05_Starter:ro" \
  -v "$PWD/data/clean:/app/data/clean" \
  -v "$PWD/data/rejected:/app/data/rejected" \
  -v "$PWD/logs:/app/logs" \
  pulseiq-etl
```

## 7. Automated Tests

```bash
python -m pytest -v
```

The current test suite contains six rule-level tests covering anomaly scores, forecast bounds, task dates, task start-date rules, ID formats, and monthly periods.

These tests do not replace a full end-to-end integration test.

## 8. Latest Recorded Results

| Table | Input | Passed | Quarantined |
|---|---:|---:|---:|
| `fact_anomaly` | 405 | 405 | 0 |
| `fact_attrition_risk` | 430 | 425 | 5 |
| `fact_forecast` | 72 | 72 | 0 |
| `fact_task` | 28,868 | 28,848 | 20 |
| **Total** | **29,775** | **29,750** | **25** |

These are the results of the latest recorded run and should be updated if the source data or validation rules change.

## 9. Data Quality Decisions and Limitations

- Five attrition predictions dated `2026-03-31` are quarantined because the pipeline treats the latest available date, `2026-09-30`, as the batch date. The source does not provide a separate batch identifier, so this is an assumption requiring confirmation.
- Twenty task records are quarantined: twelve have completion dates earlier than their start dates, and eight have status `Done` without a completion date.
- The anomaly feature source datasets are not available in the loaded raw schema. Source-record existence for anomaly records therefore remains unverified.
- Unexpected columns are reported and preserved in outputs rather than automatically rejected. Missing required contract columns stop validation.
- Only the four tables with supplied contracts are validated by this ETL pipeline.

## 10. Submission Checklist

Before submission, verify the source files, clean outputs, quarantine outputs, summary logs, automated tests, Docker execution, and required GitHub evidence.

## 11. Task 2 — Data Warehouse and Star Schema

### Warehouse Design

The PostgreSQL warehouse is stored in the `pulseiq_analytics` database under the `warehouse` schema. It contains 11 dimension tables and 12 fact tables.

- `docs/create_dimensions.sql` — dimension table definitions.
- `docs/create_facts.sql` — fact table definitions.
- `docs/star_schema.mmd` — Mermaid entity-relationship diagram.
- `docs/evidence/warehouse_row_counts.csv` — recorded fact row counts.
- `docs/evidence/warehouse_exceptions.md` — documented data-quality and mapping exceptions.

The fact tables connect to dimensions through surrogate or business keys, as appropriate. Primary keys are defined for all 12 fact tables, and foreign-key constraints enforce the supported relationships.

### Fact Tables and Row-Count Reconciliation

| Fact table | Warehouse rows | Reconciliation basis |
|---|---:|---|
| `fact_payroll` | 7,344 | Raw source rows |
| `fact_attendance_monthly` | 7,343 | Raw source rows |
| `fact_leave` | 3,441 | Raw source rows |
| `fact_headcount_monthly` | 891 | Raw source rows |
| `fact_ledger` | 6,784 | Raw source rows |
| `fact_invoice` | 743 | Raw source rows |
| `fact_invoice_payment` | 709 | Raw source rows |
| `fact_expense` | 501 | Raw source rows |
| `fact_task` | 28,848 | Task 1 passed rows |
| `fact_anomaly` | 405 | Task 1 passed rows |
| `fact_attrition_risk` | 425 | Task 1 passed rows |
| `fact_forecast` | 72 | Task 1 passed rows |
| **Total** | **56,506** | |

The eight raw-source facts retain their source row counts. The four Task 1-validated feeds contain their passed-row counts, excluding quarantined records.

### Historical Employee Mapping

Employee facts use `employee_key` to reference a specific employee dimension version. This supports historical reporting against the employee version assigned to a fact, rather than joining only on `employee_id` and potentially using the wrong department after an employee transfer.

For payroll and attendance, the intended historical version is the one valid at the reporting period end. However, source employee-history gaps remain unresolved:

- Payroll: 82 mapped rows have no employee version covering the period end; two additional records use the documented unknown key `-1`.
- Attendance: 85 rows have no employee version covering the period end.
- These records are documented in `docs/evidence/warehouse_exceptions.md`. No employee versions or validity dates were invented to hide the gaps.

Task records have no suitable event date for historical resolution, so they use the unique employee version marked as current.

### Orphan Checks and Exceptions

Foreign-key constraints enforce the supported fact-to-dimension relationships. Additional checks found zero orphan rows for the tested special relationships:

- Payroll employee keys: zero orphan rows; two documented unknown keys.
- Forecast departments: zero orphan rows; 12 intentional `ALL` aggregate rows.
- Ledger department assignments: zero invalid non-null department keys; 5,688 NULL assignments awaiting business-rule confirmation.
- Anomaly employee keys: zero orphan rows; 21 unresolved employee mappings stored as NULL.

A missing or unresolved employee mapping is not the same as a foreign-key orphan. Known exceptions and source-history limitations are recorded in `docs/evidence/warehouse_exceptions.md`.

The date dimension extends through `2027-03-31` to cover forecast months. Holiday and working-day flags after `2026-12-31` are provisional and must be refreshed against an authoritative calendar before operational use.
