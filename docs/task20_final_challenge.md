# Task 20 – Final Challenge: Automated DQ Summary Report

## 1. Improvement Overview

An automated Data Quality (DQ) Summary Report feature was developed for the PulseIQ analytics platform.

The feature reads the latest validation results from the PostgreSQL `public.dq_results` table and generates a Markdown report containing the validation summary, critical failures and detailed check results.

## 2. Reason for Selecting This Improvement

The existing DQ framework executes multiple validation checks, but reviewing individual results manually takes additional time.

An automated summary makes it easier for analysts and project stakeholders to understand the overall data-quality status and identify critical issues quickly.

## 3. Implementation Details

**File created:** `scripts/dq_summary.py`

Key features:

- Automatically identifies the latest DQ run.
- Calculates total PASS, FAIL and ERROR counts.
- Identifies critical validation failures.
- Displays detailed results for all checks.
- Generates a Markdown report inside the `reports/` directory.
- Uses read-only database queries without modifying warehouse records.

## 4. Testing and Results

The script was executed successfully using the latest live DQ run.

**DQ Run ID:** `43bb6c80-fe24-48cc-8550-a8a5753ef744`

| Validation Result | Count |
|---|---:|
| Total checks | 14 |
| PASS | 5 |
| FAIL | 9 |
| ERROR | 0 |
| Critical failures | 4 |

**Generated report:** `reports/dq_summary_43bb6c80.md`

The generated report correctly displayed the latest run information, overall status, critical failures and detailed validation results.

## 5. Benefits

1. Reduces manual effort in reviewing DQ results.
2. Improves visibility into critical data-quality issues.
3. Provides a consistent summary for project handover.
4. Supports faster investigation and decision-making.
5. Preserves the existing validation framework and source data.

## 6. Design Decision

A separate Python script was selected instead of modifying the existing DQ execution framework.

This approach keeps the improvement independent, reduces the risk of affecting existing functionality and allows the summary report to be generated whenever required.

## 7. Conclusion

The automated DQ Summary Report successfully extends PulseIQ's existing data-quality framework. It provides a clear overview of validation results and helps stakeholders identify critical issues without modifying the underlying warehouse data.

The improvement was implemented and tested successfully on the dedicated Git branch `feature/dq-summary-report`.
