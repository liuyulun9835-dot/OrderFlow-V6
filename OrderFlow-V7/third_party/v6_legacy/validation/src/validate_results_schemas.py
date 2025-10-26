#!/usr/bin/env python3
"""Validate results artifacts against published JSON Schemas."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_ROOT = REPO_ROOT / "validation" / "schemas"
SCHEMAS: dict[str, Path] = {
    "output/results/merge_metrics.json": SCHEMA_ROOT / "results_merge_metrics.schema.json",
    "output/results/calibration_profile.json": SCHEMA_ROOT / "results_calibration_profile.schema.json",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ok = True
    for rel_path, schema_path in SCHEMAS.items():
        data_path = REPO_ROOT / rel_path
        if not data_path.exists():
            print(f"[results-schema] SKIP (not found): {rel_path}")
            continue
        schema = load_json(schema_path)
        data = load_json(data_path)
        validator = Draft7Validator(schema)
        errors = sorted(validator.iter_errors(data), key=lambda err: err.path)
        if errors:
            ok = False
            print(f"[results-schema] FAIL: {rel_path}")
            for error in errors:
                location = "/".join(str(part) for part in error.path) or "<root>"
                print(f"  - {location}: {error.message}")
        else:
            print(f"[results-schema] PASS: {rel_path}")
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
