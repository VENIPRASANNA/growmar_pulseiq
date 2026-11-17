# PulseIQ Hosted Data Refresh Plan

**Refresh frequency:** Monthly
**Configured schedule:** First day of each month, 9:15 AM IST
**Data source:** Local DuckDB warehouse and validated clean datasets
**Output:** Curated Parquet files

## 1. Refresh workflow
1. Update the local DuckDB warehouse.
2. Run scripts/export_hosted_data.py.
3. Generate curated aggregate Parquet datasets.
4. Apply minimum-group-size and suppression rules.
5. Validate schemas, row counts and file sizes.
6. Review data/hosted/manifest.json.
7. Publish only approved files from data/hosted/.
8. Verify the Streamlit deployment.

## 2. Export command
```bash
.venv/bin/python scripts/export_hosted_data.py
```

## 3. Current export statistics
| Item | Value |
|---|---:|
| Datasets | 19 |
| Total rows | 1,785 |
| Total size | 62,260 bytes |
| Format | Parquet |
| Minimum group size | 10 |

## 4. Privacy validation
- Check for employee names, identifiers and personal information.
- Confirm workforce, attendance and payroll groups meet the minimum size of 10.
- Confirm productivity groups meet the minimum size.
- Suppress anomaly exposure fields when exposure counts are below 10.
- Review invoice and receivables aggregates for disclosure risks.
- Ensure local databases and individual-level source files are not staged.
- Review the manifest and Git changes before committing.

Column checks alone do not guarantee privacy. Aggregate combinations and repeated releases must also be reviewed.

## 5. Refresh schedule and dependency
The hosted-data export is scheduled for the first day of each month at 9:15 AM IST. The separate monthly PDF report runs at 9:00 AM IST.

The exporter requires the local warehouse and validated source files. Local scheduled execution depends on the computer being powered on, the project directory being accessible, and the Python environment and source datasets being available.

**Current status:** Two cron jobs are configured: the monthly PDF report at 9:00 AM IST and the hosted-data export at 9:15 AM IST on the first day of each month. The hosted refresh script regenerates local Parquet datasets only; it does not automatically publish them to GitHub or Streamlit Community Cloud. The hosted export script has been manually tested successfully.

## 6. Manual publication procedure
1. Run the hosted-data exporter.
2. Review the export summary and manifest.
3. Run the privacy audit.
4. Review Git status.
5. Stage only approved dashboard code, documentation, exporter and hosted datasets.
6. Commit and push the reviewed changes.
7. Verify the Streamlit deployment and reporting cut-off.

## 7. Secrets management
The current public dashboard uses static curated data and does not require application credentials.
- Never hardcode passwords, API keys or tokens.
- Never commit .env files or private keys.
- Store future application credentials using the hosting platform secrets facility.
- Use secure local Git credential management for repository publication.

## 8. Recovery procedure
1. Do not publish incomplete datasets.
2. Preserve the last approved hosted release.
3. Inspect exporter output and validation errors.
4. Correct the source or transformation issue.
5. Regenerate the datasets and repeat the privacy audit.
6. Publish only after validation passes.
