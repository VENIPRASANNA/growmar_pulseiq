# PulseIQ Data Quality Checks

## Status meanings

- PASS: No violating rows were found.
- FAIL: One or more violating rows were found.
- ERROR: The check could not run or its result could not be verified.
- Results are stored in `public.dq_results`.

## Severity decisions

Critical failures should block publication of affected outputs until reviewed. Warning failures should be investigated but need not block unrelated outputs.

| Check | Plain-English explanation | Severity | Reason |
|---|---|---|---|
| DQ-C01 | Monthly payroll employer cost must match ledger salary-related expenses within ₹0.01. | Critical | Protects financial accuracy. |
| DQ-C02 | Debits and credits must balance for each journal entry within 0.005. | Critical | Protects accounting integrity. |
| DQ-C03 | Each employee must have one payroll row per run. | Critical | Prevents duplicate payroll. |
| DQ-C04 | Payroll employee keys must resolve to the correct employee dimension record, except explicitly unknown keys. | Critical | Protects employee attribution. |
| DQ-C05 | Attendance must not occur after the employee's exit month. | Warning | HR dates may need confirmation. |
| DQ-C06 | Unpaid absence must be reflected in payroll loss-of-pay days within 0.5 day. | Warning | Detects leave/payroll mapping issues. |
| DQ-C07 | Paid amount must not exceed invoice total, and balance due must not be materially negative. | Warning | Detects invoice/payment inconsistencies. |
| DQ-C08 | Expense total must equal amount excluding GST plus GST within ₹0.01. | Warning | Protects expense arithmetic. |
| DQ-C09 | A task cannot finish before it starts; Done tasks need a completion date. | Warning | Detects inconsistent task data. |
| DQ-C10 | Leave end date cannot precede start date. | Warning | Detects invalid leave dates. |
| DQ-C11 | Prediction as-of dates must be within seven days of the latest date in the feed. | Warning | Stale predictions may mislead users. |
| DQ-C12 | Employee dimension validity periods must not overlap. | Critical | Protects historical joins. |
| DQ-C13 | The latest successful ETL run must be within 24 hours. | Critical | Prevents stale data being presented as current. |
| DQ-C14 | Metric groups must meet the metric dictionary's minimum group size before publication. | Critical | Protects employee privacy. |

## Known limitations

1. DQ-C11 only checks `as_of_date`. `warehouse.fact_attrition_risk` has no `scored_at` column, so the 24-hour scoring freshness rule is not verified.
2. DQ-C13 needs a real ETL run log. A missing log cannot be treated as proof of freshness.
3. DQ-C14 is a query-time privacy rule. Reporting queries must call `src/privacy_gate.py` before publishing groups. The current automated runner tests the policy function but does not inspect live manager queries.
4. Existing failures must be investigated and documented, not hidden by deleting source data or weakening thresholds.

## DQ-C14 publication rule

The metric dictionary is sourced from `03_Data/csv/metric_dictionary.csv`. Before publishing a metric group, load its threshold and call `can_publish(metric_id, distinct_employee_count, thresholds)` from `src/privacy_gate.py`. Suppress the group when the function returns `False`. If a threshold is missing, publication is blocked until a policy is approved.

## Current baseline

The latest recorded run reported 14 checks: 6 PASS, 8 FAIL, 0 ERROR.
Run ID: `a2a941fa-43ee-4c7e-ac3a-d2b50600521a`.
The eight failing checks are C01, C03, C05, C06, C07, C08, C10, and C12.
These results describe the current warehouse state and should be retained as evidence until investigated.

## Validation-vault comparison status

The required `unlock_PQ-03.csv` answer key was not found in the project parent directory or under the user's home directory. Therefore, the comparison against the 11 planted issues remains pending. Do not claim that the 11 issues were reconciled or invent the expected answers. Complete this comparison when the supplied validation vault becomes available.

## Test coverage note

The bad-row harness reports 13 isolated bad-row detection tests passing, and the C14 privacy-gate unit tests pass. These tests use isolated examples; they are not a claim that all 14 production SQL files were independently executed against deliberately corrupted copies of every production table. C14 is tested as a Python policy function, not as a live-query audit.
