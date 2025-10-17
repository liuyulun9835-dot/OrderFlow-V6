#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLAN_SCRIPT="$ROOT_DIR/scripts/plan_restructure.py"

if [[ ! -f "$PLAN_SCRIPT" ]]; then
  echo "Plan script not found at $PLAN_SCRIPT" >&2
  exit 1
fi

python3 "$PLAN_SCRIPT" --mode plan --repo-root "$ROOT_DIR"

echo -e "\nPlan complete. Review docs/migrations/file_moves_plan.csv and docs/migrations/import_rewrite_plan.csv before applying.\nThis wrapper will continue only after confirmation."
read -r -p "Apply the restructure now? [y/N] " REPLY

case "$REPLY" in
  [yY][eE][sS]|[yY])
    python3 "$PLAN_SCRIPT" --mode apply --repo-root "$ROOT_DIR"
    ;;
  *)
    echo "Skipped apply phase."
    ;;
esac
