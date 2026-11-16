
#!/bin/bash

PROJECT_DIR="/home/prasanna/Desktop/GROW-TASK/pulseiq"
PYTHON="$PROJECT_DIR/.venv/bin/python"
DB="$PROJECT_DIR/05_Starter/pulseiq.duckdb"
REPORT_DIR="$PROJECT_DIR/reports"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$REPORT_DIR" "$LOG_DIR"

REPORT_MONTH=$(date -d "$(date +%Y-%m-01) -1 month" +%Y-%m)

cd "$PROJECT_DIR" || exit 1

echo "[$(date)] Generating report for $REPORT_MONTH" >> "$LOG_DIR/monthly_report.log"

"$PYTHON" "$PROJECT_DIR/build_report.py" \
    --month "$REPORT_MONTH" \
    --db "$DB" \
    --output-dir "$REPORT_DIR" \
    >> "$LOG_DIR/monthly_report.log" 2>&1

if [ $? -eq 0 ]; then
    echo "[$(date)] Report generated successfully." >> "$LOG_DIR/monthly_report.log"
else
    echo "[$(date)] Report generation failed." >> "$LOG_DIR/monthly_report.log"
    exit 1
fi
