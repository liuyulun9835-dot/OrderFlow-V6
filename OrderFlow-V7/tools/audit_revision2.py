# [MIGRATED_FROM_V6] 2025-10-26: 原路径 tools/audit_revision2.py；本文件在 V7 中保持向后兼容
"""Audit repository against Revision 2.0 constraints.
WHY: 自动化检测规范偏差，提升审计覆盖率。
"""
from __future__ import annotations
import json
import pathlib
import re
import sys
from typing import Any

ROOT = pathlib.Path(sys.argv[1]).resolve()
constraints: dict[str, Any] = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))

report: dict[str, Any] = {"violations": [], "warnings": [], "notes": []}

artifact_fields = constraints["model"]["artifacts_fields"]
rg_three_state = re.compile("|".join(constraints["model"]["must_not_contain"]), re.IGNORECASE)

scan_patterns = ("*.py", "*.md", "*.yaml", "*.yml", "*.json", "*.txt")
three_hits: list[str] = []
for pattern in scan_patterns:
    for path in ROOT.rglob(pattern):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if rg_three_state.search(text):
            three_hits.append(str(path.relative_to(ROOT)))
if three_hits:
    report["violations"].append({"id": "legacy_three_state", "files": sorted(set(three_hits))})

rules_path = pathlib.Path(constraints["governance"]["rules"])
if not (ROOT / rules_path).exists():
    report["violations"].append({"id": "missing_rules_library", "path": str(rules_path)})
else:
    rules_text = (ROOT / rules_path).read_text(encoding="utf-8", errors="ignore")
    if "transition(" not in rules_text:
        report["violations"].append({"id": "missing_transition_trigger", "path": str(rules_path)})

model_schema_path = pathlib.Path(constraints["governance"]["schemas"]["model"])
decision_schema_path = pathlib.Path(constraints["governance"]["schemas"]["decision"])
for schema_path, required_keys in [
    (model_schema_path, artifact_fields),
    (decision_schema_path, constraints["decision"]["decision_schema_fields"]),
]:
    full_path = ROOT / schema_path
    if not full_path.exists():
        report["violations"].append({"id": "missing_schema", "path": str(schema_path)})
        continue
    schema_text = full_path.read_text(encoding="utf-8", errors="ignore")
    for key in required_keys:
        if key not in schema_text:
            report["violations"].append({"id": "schema_field_missing", "schema": str(schema_path), "field": key})

macro_folder = pathlib.Path(constraints["features"]["macro_folder"])
if not (ROOT / macro_folder).exists():
    report["violations"].append({"id": "missing_macro_factor_folder", "path": str(macro_folder)})

if not any((ROOT / "decision").rglob("directional_classifier.py")):
    report["violations"].append({"id": "missing_directional_classifier", "path": "decision/directional_classifier.py"})

if not any((ROOT / "model" / "hmm_tvtp_hsmm").rglob("state_inference.py")):
    report["violations"].append({"id": "missing_state_inference", "path": "model/hmm_tvtp_hsmm/state_inference.py"})

print(json.dumps(report, ensure_ascii=False, indent=2))
