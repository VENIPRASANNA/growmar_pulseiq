#!/bin/bash
set -euo pipefail

PROJECT="/home/prasanna/Desktop/GROW-TASK/pulseiq"
LOG="$PROJECT/logs/hosted_refresh.log"

mkdir -p "$PROJECT/logs"
cd "$PROJECT"

echo "===== Hosted refresh started: $(date) =====" >> "$LOG"

"$PROJECT/.venv/bin/python" \
    "$PROJECT/scripts/export_hosted_data.py" >> "$LOG" 2>&1

echo "===== Hosted refresh completed: $(date) =====" >> "$LOG"
