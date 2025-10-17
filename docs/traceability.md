# Traceability Map

| 卡片 | 模块 | 产物 | 报告 |
| --- | --- | --- | --- |
| 111 | `preprocessing/merge_to_features.py` | `data/processed/features.parquet` | `results/merge_and_calibration_report.md` |
| 112 | `preprocessing/utils/error_ledger.py` | `data/raw/atas/error_ledger.csv` | `results/bar_continuity_report.md` |
| 116 | `preprocessing/calibration.py` | `calibration_profile.json` | `results/merge_and_calibration_report.md` |
| 117 | `validation/src/precheck_costs.py` | `results/precheck_costs_report.md` | `results/precheck_costs_report.json` |
| 118 | `validation/src/make_labels.py` | `data/processed/labels.parquet` | `logs/priority_downgrade.log` |
| 607 | `scripts/canary_switch_dryrun.py` | `results/canary_switch_dryrun.md` | `execution/switch_policy.yaml` |
| 808 | `validation/src/validate_outputs.py` | `results/*.meta.json` | `results/validate_outputs.log` |

`scripts/update_pipeline.ps1` 会在 `results/qc_summary.md` 写入 `data_manifest_hash`、`exporter_version`、`schema_signature` 与随机种子，确保产出可追溯。
