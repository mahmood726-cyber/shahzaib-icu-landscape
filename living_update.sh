#!/usr/bin/env bash
# Living Update — Unix cron wrapper
#
# Schedule via crontab:
#   crontab -e
#   0 3 * * * /path/to/living_update.sh
#
# Or run manually:
#   ./living_update.sh
#   ./living_update.sh --dry-run
#   ./living_update.sh --skip-enrich
#
# Logs to logs/living_YYYYMMDD.log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create logs directory if needed
mkdir -p logs

LOG_DATE="$(date +%Y%m%d)"
LOG_FILE="logs/living_${LOG_DATE}.log"

# Find Python
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: No python found" >> "$LOG_FILE"
    exit 1
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Living update starting" >> "$LOG_FILE"

EXIT_CODE=0
"$PYTHON" living_update.py "$@" >> "$LOG_FILE" 2>&1 || EXIT_CODE=$?

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Living update finished (exit code $EXIT_CODE)" >> "$LOG_FILE"

exit $EXIT_CODE
