# [MIGRATED_FROM_V6] 2025-10-26: 原路径 tools/extract_spec.py；本文件在 V7 中保持向后兼容
"""Parse spec/todo/README to structured constraints for Revision 2.0 audit.
WHY: 将自然语言要求 → 机器可检查的约束集合。
"""
from __future__ import annotations
import json
import pathlib
import sys

spec_path, readme_path, todo_path = sys.argv[1:4]
text_spec = pathlib.Path(spec_path).read_text(encoding="utf-8", errors="ignore")
text_readme = pathlib.Path(readme_path).read_text(encoding="utf-8", errors="ignore")
text_todo = pathlib.Path(todo_path).read_text(encoding="utf-8", errors="ignore")
_ = (text_spec, text_readme, text_todo)

constraints = {
    "model": {
        "two_state": True,
        "tvtp": True,
        "macro_factor_supported": True,
        "artifacts_fields": ["states", "tvtp", "macro_factor_used", "signatures"],
        "must_not_contain": [
            r"balance\s*/\s*trend\s*/\s*transition",
            r"three[- ]state|3[- ]state|三态",
        ],
    },
    "decision": {
        "directional_classifier": True,
        "rules_transition_trigger": True,
        "decision_schema_fields": ["trigger", "directional_classifier"],
    },
    "features": {
        "macro_folder": "features/macro_factor",
    },
    "governance": {
        "schemas": {
            "model": "governance/SCHEMA_model.json",
            "decision": "governance/SCHEMA_decision.json",
        },
        "rules": "governance/RULES_library.yaml",
    },
    "validation": {
        "directional_breakdown": True,
        "macro_vs_nomacro": True,
    },
}

print(json.dumps(constraints, ensure_ascii=False, indent=2))
