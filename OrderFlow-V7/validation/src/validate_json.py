#!/usr/bin/env python3
# [MIGRATED_FROM_V6] 2025-10-26: 原路径 orderflow_v_6/validation/src/validate_json.py；本文件在 V7 中保持向后兼容
"""Validate ATAS JSON exports against the repository schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import Draft7Validator


def load_schema(schema_path: Path) -> Dict[str, Any]:
    with schema_path.open("r", encoding="utf-8") as schema_file:
        return json.load(schema_file)


def collect_json_files(data_root: Path) -> List[Path]:
    if not data_root.exists():
        return []
    return sorted(path for path in data_root.rglob("*.json") if path.is_file())


def validate_documents(validator: Draft7Validator, documents: List[Path]) -> List[str]:
    errors: List[str] = []
    for document_path in documents:
        try:
            with document_path.open("r", encoding="utf-8") as document_file:
                payload = json.load(document_file)
        except json.JSONDecodeError as exc:
            errors.append(f"{document_path}: JSON decode error - {exc}")
            continue

        for error in validator.iter_errors(payload):
            errors.append(f"{document_path}: {error.message}")

    return errors


def render_report(report_path: Path, errors: List[str], files_checked: int) -> None:
    report_lines = ["# JSON Validation Report", ""]
    report_lines.append(f"*Total files checked:* {files_checked}")

    if errors:
        report_lines.append(f"*Files with errors:* {len(errors)}")
        report_lines.append("")
        report_lines.append("## Errors")
        report_lines.extend(f"- {line}" for line in errors)
    else:
        report_lines.append("*Files with errors:* 0")
        report_lines.append("")
        report_lines.append("All JSON documents conform to the schema.")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")


def main() -> None:
    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[2]
    schema_path = repo_root / "preprocessing" / "schemas" / "atas_schema.json"
    data_root = repo_root / "data" / "atas"
    report_path = repo_root / "results" / "json_validation_report.md"

    schema = load_schema(schema_path)
    validator = Draft7Validator(schema)

    documents = collect_json_files(data_root)
    errors = validate_documents(validator, documents)
    render_report(report_path, errors, len(documents))


if __name__ == "__main__":
    main()
