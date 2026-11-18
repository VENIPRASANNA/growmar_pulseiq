# Task 18 – Privacy Break-It Notes

## 1. Objective
Test whether role restrictions and minimum-group-size
privacy controls prevent unauthorized KPI access.

## 2. Tests Performed

| Test | Expected Result | Actual Result |
|---|---|---|
| HR accesses another department | Blocked | PASS |
| Manager accesses another team | Blocked | PASS |
| Executive accesses department data | Blocked | PASS |
| Admin accesses unresolved metric M24 | Blocked | PASS |
| Invalid metric M99 | Blocked | PASS |
| HR changes to team dimension | Blocked | PASS |
| Manager changes to department dimension | Blocked | PASS |
| Executive changes to team dimension | Blocked | PASS |
| HR automatic scope | D07 only | PASS |
| Manager automatic scope | T08 only | PASS |
| Group size below 10 | Suppressed | PASS |
| Group size equal to 10 | Allowed | PASS |
| Actual M04 query | No groups below 10 | PASS |

## 3. Privacy Threshold Test

Metric: M04
Minimum group size: 10 employees

- Group size 9: Blocked
- Group size 10: Allowed
- Actual records returned: 651
- Smallest returned group: 10
- Groups below threshold: 0

## 4. Observations

- Role-based access restrictions are enforced.
- HR is restricted to department D07.
- Manager is restricted to team T08.
- Executive users can access company-level KPIs only.
- Unapproved metrics are rejected.
- Small groups are excluded from query results.

## 5. Identified Limitation

Administrator access includes broad department and team
visibility. Comparing aggregate totals with component groups
could potentially reveal suppressed values through differencing.

Minimum-group-size suppression alone does not eliminate
this risk.

Further controls such as complementary suppression,
restricted drill-down and query auditing would be required
for stronger production-grade protection.

## 6. Conclusion

The tested role restrictions and minimum-group-size
controls behaved as expected. The remaining differencing
risk is documented for future improvement.
