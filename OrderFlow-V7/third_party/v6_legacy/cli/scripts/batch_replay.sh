#!/usr/bin/env bash
set -euo pipefail

SYMBOL=${1:-}
START_DATE=${2:-}
END_DATE=${3:-}

if [[ -z "$SYMBOL" || -z "$START_DATE" || -z "$END_DATE" ]]; then
  echo "Usage: ./batch_replay.sh SYMBOL START_DATE END_DATE" >&2
  exit 1
fi

mkdir -p logs
LOG_FILE="logs/replay.log"

echo "[$(date --iso-8601=seconds)] Starting batch replay for $SYMBOL from $START_DATE to $END_DATE" >> "$LOG_FILE"

current_date=$(date -d "$START_DATE" +%Y-%m-%d)
final_date=$(date -d "$END_DATE" +%Y-%m-%d)

while [[ "$current_date" < "$final_date" || "$current_date" == "$final_date" ]]; do
  echo "Running ATAS replay for $current_date" >> "$LOG_FILE"
  /opt/atas/atas --mode Replay --symbol "$SYMBOL" --from "$current_date" --to "$current_date" --export-json >> "$LOG_FILE" 2>&1 || true
  current_date=$(date -d "$current_date + 1 day" +%Y-%m-%d)
done

echo "[$(date --iso-8601=seconds)] Batch replay completed for $SYMBOL" >> "$LOG_FILE"
