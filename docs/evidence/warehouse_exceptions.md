# PulseIQ Warehouse — Known Exceptions

## 1. Payroll employee-key exceptions

Two payroll records use employee_key = -1, which does not exist in warehouse.dim_employee.

| Payroll item | Employee ID | Period end | Department | Gross pay |
|---|---|---|---|---:|
| PI-X0003 | EMP-9001 | 2026-04-30 | D01 | 96015.00 |
| PI-X0004 | EMP-9002 | 2025-12-31 | D09 | 96527.42 |

**Treatment:** Both records are preserved. No employee dimension rows were invented. Mapping remains unresolved pending confirmation.

## 2. Anomaly employee-key exceptions

The clean anomaly feed contains 405 records:
- 384 matched to an employee version valid at reporting month-end.
- 21 had no valid employee version at month-end.
- 0 had multiple matching versions.

**Treatment:** All 405 records are preserved. The 21 unresolved employee_key values remain NULL. See `anomaly_employee_key_unmatched.csv`.

## 3. Ledger department assignments

Some ledger rows have NULL cost_center_department_id. These are unassigned or unavailable cost centers, not confirmed orphan keys. Records are preserved pending business-rule confirmation.

## 4. SCD Type 2 employee history

One overlapping validity interval was found for EMP-0001:
- employee_key 100000: 2012-01-19 through 2012-05-12.
- employee_key 100001: 2012-05-03 through 2015-05-13.

The overlap is 2012-05-03 through 2012-05-12. Both versions have the same department and role. Source history was not modified; confirmation from the data owner is needed.

## 5. Task employee mapping

Task records have no event date suitable for historical employee-version resolution. Assignees are mapped to the unique employee version marked is_current = 'Y'.

- Clean task rows loaded: 28,848
- Matched employee keys: 28,848
- Unmatched employee keys: 0
- Multiple current-version matches: 0

## 6. Date dimension extension

The warehouse date dimension was extended through 2027-03-31 to cover forecast months beyond the original range. Dates after 2026-12-31 use provisional holiday flags (`is_holiday = 'N'`) and weekday-based working-day flags. Refresh these flags against an authoritative holiday calendar before operational use.

## 7. Row-count reconciliation

See `warehouse_row_counts.csv` for the live warehouse counts.

The eight raw-source facts match their source row counts. The four Task 1-validated feeds match their passed-row counts:

- fact_task: 28,848
- fact_anomaly: 405
- fact_attrition_risk: 425
- fact_forecast: 72

The two unresolved payroll records remain included in the payroll count.
