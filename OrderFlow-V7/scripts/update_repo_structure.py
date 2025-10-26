# [MIGRATED_FROM_V6] 2025-10-26: 原路径 scripts/update_repo_structure.py；本文件在 V7 中保持向后兼容
from pathlib import Path
import re

TREE = r"""
/                                # 根目录：治理 / 控制 / 契约 层
├── governance/
│   ├── CONTROL_naming.md
│   ├── CONTROL_costs.yaml
│   ├── CONTROL_switch_policy.yaml
│   ├── RULES_library.yaml
│   ├── SCHEMA_data.json
│   ├── SCHEMA_features.json
│   ├── SCHEMA_model.json
│   ├── SCHEMA_decision.json
│   └── SCHEMA_execution.json
├── output/
│   ├── publish_docs/{ARCHITECTURE.md,VALIDATION.md,CHANGELOG.md,publish_docs_source.md}
│   ├── qa/{qc_summary.md,validator_report.md,cost_sensitivity.md,qa_source_intent.md}
│   ├── results/{merge_and_calibration_report.md,validator_report.md,qc_summary.md,results_source_intent.md}
│   └── report/{release.yml,INVESTIGATION.md,report_source_intent.md}
├── docs/
│   └── migrations/{card_mapping.csv,file_moves.csv,import_rewrites.csv}
├── third_party/
│   └── v6_legacy/{core,validation,cli,utils}
├── data/
│   ├── raw/{exchange,atas/{bar,tick}}
│   ├── preprocessing/{schemas,align}
│   ├── calibration/
│   ├── features/
│   └── processed/
├── model/{factors,hmm_tvpt_hsmm,calibration,artifacts}
├── decision/{rules,scoring,engine,logs}
├── execution/{risk,matching,routing,switch}
└── makefile / pyproject.toml
""".strip()

README = Path("README.md")
text = README.read_text(encoding="utf-8")
start = "<!-- REPO_STRUCTURE_START -->"
end = "<!-- REPO_STRUCTURE_END -->"
replacement = f"## Repo Structure\n{start}\n\n```\n{TREE}\n```\n\n{end}"
pattern = re.compile(r"## Repo Structure\n```[\s\S]*?```", re.MULTILINE)
if pattern.search(text):
    new_text = pattern.sub(replacement, text, count=1)
elif start in text and end in text:
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    block = f"{start}\n\n```\n{TREE}\n```\n\n{end}"
    new_text = before + block + after
else:
    block = f"\n\n{replacement}\n"
    new_text = text.strip() + block
README.write_text(new_text, encoding="utf-8")
print("README Repo Structure updated.")
