# [MIGRATED_FROM_V6] 2025-10-26: 原路径 tools/score_progress.py；本文件在 V7 中保持向后兼容
"""Score engineering progress per layer using simple presence checks.
WHY: 量化工程进度，形成治理闭环指标。
"""
from __future__ import annotations
import json
import pathlib
import sys
from typing import Any

root = pathlib.Path(sys.argv[1]).resolve()
spec: dict[str, Any] = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))


def exists(path: pathlib.Path, kind: str | None = None) -> bool:
    target = root / path
    if kind == "dir":
        return target.exists() and target.is_dir()
    return target.exists()


def contains(path: pathlib.Path, keys: list[str]) -> bool:
    if not keys:
        return True
    target = root / path
    if not target.exists() or target.is_dir():
        return False
    text = target.read_text(encoding="utf-8", errors="ignore")
    return all(key in text for key in keys)


summary: dict[str, Any] = {}
for layer, cfg in spec.items():
    checks: list[dict[str, Any]] = cfg["checks"]
    completed: list[str] = []
    missing: list[str] = []
    for check in checks:
        path = pathlib.Path(check["path"])
        check_type = check.get("type")
        if exists(path, check_type) and contains(path, check.get("must_contain", [])):
            completed.append(check["id"])
        else:
            missing.append(check["id"])
    pct = round(100.0 * len(completed) / max(1, len(checks)), 1)
    summary[layer] = {"progress_pct": pct, "done": completed, "missing": missing}

print(json.dumps(summary, ensure_ascii=False, indent=2))
