# PulseIQ Governed Metric Layer — Task 4

## Build
Run from the repository root:

    .venv/bin/python scripts/create_metric_layer.py
    .venv/bin/python scripts/apply_metric_views.py
    .venv/bin/python scripts/validate_metric_layer.py

## Catalog
The official dictionary is 03_Data/csv/metric_dictionary.csv.
The catalog is metrics.metric_catalog, backed by metrics.metric_catalog_data.
All 28 metric definitions are included.

## Formula and data decisions
- M04 follows the official dictionary: monthly exits divided by starting headcount.
- M05 and M06 use rolling 12-month exit counts divided by average month-end headcount.
- M07-M15 are aggregated to department-month grain.
- PI-X0001 and PI-X0002 are excluded because they duplicate original payroll records.
- M16 uses ledger accounts 4001-4004. M17 includes income accounts 4xxx and expense accounts 5xxx.
- M19 uses positive debit amounts from payroll expense accounts 5001-5005.
- M20 uses the latest invoice date as the report date; confirm this assumption with the business owner.
- M21 is internal pending approval of its missing minimum group-size policy.
- M26 is unavailable because the anomaly feed does not establish the full scored population.
- M28 is unavailable because actual headcount ends in September 2026 and forecasts begin in October 2026.

## Privacy
- Payroll views aggregate to department-month and suppress groups below five.
- Attrition views suppress groups below ten.
- High-risk attrition is aggregated by department; named employees are not published.
- Nine metrics have undefined minimum group sizes and remain marked REVIEW_REQUIRED.

## Validation
scripts/validate_metric_layer.py checks view coverage, selected privacy controls, five hand-calculations, and the M26/M28 limitations.
