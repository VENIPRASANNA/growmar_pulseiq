# Task 20 – Final Data Reconciliation and Data Quality Report

## 1. Introduction

As part of Task 20 – Board Pack and Final Handover, a final data reconciliation and data-quality assessment was performed on the PulseIQ analytics warehouse.

The objective was to validate the consistency, accuracy, completeness and reliability of the available business data before the final project release.

The assessment covered payroll, financial ledger, employee records, attendance, invoices, expenses, leave records, task data, AI feeds and privacy controls.

The validation was performed using the existing Data Quality (DQ) framework and PostgreSQL warehouse.

## 2. Validation Summary

A total of 14 data-quality checks were executed.

| Result | Number of Checks |
|---|---:|
| Passed | 5 |
| Failed | 9 |
| Errors | 0 |
| Total | 14 |

**DQ Run ID:** `43bb6c80-fe24-48cc-8550-a8a5753ef744`

The results indicate that several validation rules passed successfully, while critical reconciliation and data-integrity issues require further investigation.

## 3. Data Quality Check Results

### 3.1 Critical Checks

| Check ID | Validation | Result | Bad Rows |
|---|---|---|---:|
| DQ-C01 | Payroll equals ledger | FAIL | 5 |
| DQ-C02 | Ledger balanced | PASS | 0 |
| DQ-C03 | Unique payroll rows | FAIL | 2 |
| DQ-C04 | No orphan employees | PASS | 0 |
| DQ-C12 | Dimension history does not overlap | FAIL | 1 |
| DQ-C13 | Pipeline freshness | FAIL | 1 |
| DQ-C14 | Minimum group size | PASS | 0 |

### 3.2 Warning Checks

| Check ID | Validation | Result | Bad Rows |
|---|---|---|---:|
| DQ-C05 | No attendance after exit | FAIL | 4 |
| DQ-C06 | Unpaid leave deducted | FAIL | 1 |
| DQ-C07 | Invoice arithmetic | FAIL | 1 |
| DQ-C08 | Expense arithmetic | FAIL | 1 |
| DQ-C09 | Task dates sensible | PASS | 0 |
| DQ-C10 | Leave dates sensible | FAIL | 2 |
| DQ-C11 | AI feeds are fresh | PASS | 0 |

## 4. Detailed Reconciliation Findings

### 4.1 Payroll and Ledger Reconciliation

The payroll-to-ledger validation identified five months with differences between payroll employer cost and ledger expense accounts 5001–5005.

| Month | Payroll Cost (₹) | Ledger Cost (₹) | Difference (₹) |
|---|---:|---:|---:|
| May 2025 | 40,717,628.17 | 40,655,815.02 | +61,813.15 |
| December 2025 | 47,420,813.68 | 47,322,486.26 | +98,327.42 |
| February 2026 | 44,198,850.60 | 44,044,038.71 | +154,811.89 |
| April 2026 | 62,264,040.50 | 62,168,025.50 | +96,015.00 |
| June 2026 | 54,664,233.35 | 54,682,683.35 | -18,450.00 |

Positive differences indicate that payroll cost is greater than the corresponding ledger expense. The negative difference indicates that ledger expense is greater than payroll cost.

### 4.2 Duplicate Payroll Records

Two duplicate payroll records were identified.

| Employee ID | Payroll Run | Duplicate Payroll Item IDs |
|---|---|---|
| EMP-0598 | PR-2025-05 | PI-000761, PI-X0002 |
| EMP-0194 | PR-2026-02 | PI-004059, PI-X0001 |

The duplicate employer-cost values were ₹61,813.15 and ₹154,811.89 respectively.

These values exactly explain the May 2025 and February 2026 reconciliation differences.

The existing payroll-cleaning view excludes these two payroll item IDs. However, the original DQ validation still identifies them as duplicate records.

The records were not deleted because the original source-loading process and business approval for modifying financial records were not available.

### 4.3 Remaining Payroll and Ledger Differences

After identifying the duplicate records, three reconciliation differences remain unexplained.

| Month | Department | Difference |
|---|---|---:|
| December 2025 | D09 | ₹98,327.42 |
| April 2026 | D01 | ₹96,015.00 |
| June 2026 | D01 | -₹18,450.00 |

Further investigation of the payroll components and ledger accounts showed that certain salary and employer PF allocations did not match.

The payroll component totals were internally consistent, but the corresponding ledger expense allocations differed.

The original PostgreSQL payroll and ledger loading process was not found in the current project repository. Therefore, these differences remain classified as unresolved source-data reconciliation exceptions.

No financial records or reconciliation rules were modified to force a passing result.

### 4.4 Ledger Balance Validation

The ledger balance check passed successfully.

**Result:** PASS
**Bad Rows:** 0

This indicates that the tested journal entries satisfy the ledger balancing validation. However, balanced journal entries do not necessarily guarantee that payroll expenses are allocated to the correct accounts.

### 4.5 Employee Dimension History

The dimension-history validation identified one overlapping employee record.

- Employee ID: EMP-0001
- Earlier record: Employee Key 100000
- Later record: Employee Key 100001
- Overlapping period: 3 May 2012 to 12 May 2012

The overlap requires further review of the employee dimension's historical effective-date boundaries.

No historical records were modified during this assessment.

### 4.6 Pipeline Freshness

The pipeline freshness validation failed because the latest successful ETL execution was older than the required 24-hour freshness limit.

Latest successful ETL timestamp:

`2026-11-01 00:01:40 +05:30`

DQ execution timestamp:

`2026-11-18 18:19:48.478026 +05:30`

The pipeline therefore did not satisfy the configured freshness requirement at the time of validation.

### 4.7 Attendance, Leave, Invoice and Expense Checks

The following warning-level issues were identified:

| Check ID | Issue | Bad Rows |
|---|---|---:|
| DQ-C05 | Attendance records after employee exit | 4 |
| DQ-C06 | Unpaid leave deduction mismatch | 1 |
| DQ-C07 | Invoice arithmetic inconsistency | 1 |
| DQ-C08 | Expense arithmetic inconsistency | 1 |
| DQ-C10 | Invalid leave date ranges | 2 |

These records require source-level investigation and correction through an approved data-quality process.

### 4.8 AI Feed Freshness and Privacy Validation

The AI feed freshness check passed based on the available as-of-date comparison.

However, 24-hour scoring freshness could not be verified because the `scored_at` field is absent from the `fact_attrition_risk` table.

The minimum group-size privacy check also passed.

The DQ framework notes that live reporting queries must call `can_publish()` before releasing metric groups.

## 5. Workforce Reconciliation

September 2026 workforce records were also reconciled.

The published workforce data excludes department D00 because of the minimum group-size privacy rule.

| Description | Employees |
|---|---:|
| Starting headcount | 426 |
| Hires | 17 |
| Exits | 3 |
| Ending headcount | 440 |

The headcount bridge is:

**426 + 17 - 3 = 440**

The workforce reconciliation therefore balances successfully.

### Payroll Employee Count Comparison

The September payroll view reports 443 employees, compared with 440 month-end active employees.

The difference of three employees was investigated.

The additional payroll records belonged to employees who exited during September but received payment for the days worked before their exit dates.

| Employee ID | Department | Exit Date | Payable Days |
|---|---|---|---:|
| EMP-0479 | D01 | 01-09-2026 | 1 |
| EMP-0621 | D01 | 25-09-2026 | 25 |
| EMP-0677 | D04 | 10-09-2026 | 10 |

These are valid partial-month payroll payments and explain why the payroll employee count is higher than the month-end headcount.

This difference is explained and is not classified as a confirmed data-quality error.

## 6. Key Recommendations

1. Review the payroll and ledger allocation differences for December 2025, April 2026 and June 2026.
2. Investigate the duplicate payroll records and establish an approved source-data correction process.
3. Review the overlapping employee dimension history and confirm the effective-date rules.
4. Execute the ETL pipeline regularly and monitor its last successful execution time.
5. Investigate attendance, leave, invoice and expense validation failures.
6. Introduce a `scored_at` timestamp in the AI prediction data to support reliable freshness validation.
7. Ensure all public reporting queries apply the minimum group-size privacy policy.
8. Maintain regular payroll-to-ledger reconciliation before publishing financial reports.

## 7. Final Conclusion

The final reconciliation exercise successfully evaluated 14 data-quality checks across the PulseIQ analytics warehouse.

Five checks passed and nine checks failed. The assessment identified duplicate payroll records, unresolved payroll-to-ledger differences, an employee dimension-history overlap, pipeline freshness issues and several warning-level data inconsistencies.

The workforce headcount reconciliation was successful, and the September payroll employee-count difference was explained by legitimate partial-month payments to employees who exited during the month.

The ledger balancing and minimum group-size privacy checks also passed.

Although several data-quality issues remain unresolved, the investigation provides a clear record of the findings, their impact and the recommended corrective actions.

The final DQ results have been retained without altering source financial records or weakening validation rules.

**Overall Status: Partially Reconciled – Outstanding Data Quality Issues Require Further Investigation.**
