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
# OrderFlow V6 可追溯索引（Traceability Matrix）

> 结构：卡片 → 脚本/配置 → 产物 → 报告/签名。依据《OrderFlow V6 综合项目说明书（理论强化版）》与本仓库卡片库编制。

## 数据分层与 Manifest
| 卡片 | 脚本/配置 | 产物 | 报告/签名 |
| --- | --- | --- | --- |
| 109/110 | `scripts/manifest/generate_manifest.py`（占位）<br>`scripts/manifest/hash_manifest.py` | `manifest/*.json`（含 `source_ranges`, `schema_signature`, `exporter_meta`, `lineage`）<br>`results/manifest_hash.txt` | `results/qc_summary.md`（`data_manifest_hash` 字段） |
| 111/112 | `atas_integration/exporter.py`<br>`atas_integration/tick_capture.py` | `data/raw/atas/bar/*`<br>`data/raw/atas/tick/*`<br>`data/raw/atas/error_ledger.csv` | `bar_continuity_report.md`<br>`tick_quality_report.md`（CV、p99 阈值） |

## 映射、校准与降级
| 卡片 | 脚本/配置 | 产物 | 报告/签名 |
| --- | --- | --- | --- |
| 115 | `preprocessing/align/build_index.py` | `preprocessing/align/index.parquet` | `results/qc_summary.md`（索引一致率） |
| 116 | `preprocessing/align/minute_tick_mapping.py` | `mapping_tick2bar.pkl`<br>`calibration_profile.json` | `results/merge_and_calibration_report.md`（PSI/KS/ECE、错配率、边界截图） |
| 117 | `preprocessing/align/calibration_audit.py` | `calibration_profile.json`（降级段、`calibration_hash`） | `results/qc_summary.md`（不可合并段） |
| 118 | `validation/precheck/run_precheck.py`<br>`validation/configs/priority_downgrade.yaml` | `validation/precheck/costs_gate.md` | 预检日志（含 `embargo_bars`、`purge_kfold`、降级记录） |

## Validator 与统计控制
| 卡片 | 脚本/配置 | 产物 | 报告/签名 |
| --- | --- | --- | --- |
| 403/404 | `validation/src/univariate_tests.py`<br>`validation/src/multivariate_tests.py`<br>`validation/configs/preregister.yaml` | 显著性/效应量表 | `report.md`（FDR-BH/Max-T 校正、预注册引用） |
| 405 | `validation/src/cost_robustness.py` | 成本敏感性表 | `report.md`（三档成本对比） |
| 406 | `validation/src/publish_outputs.py` | `OF_V6_stats.xlsx`<br>`combo_matrix.parquet`<br>`white_black_list.json`<br>`report.md` | 四键签名（`schema_version`、`build_id`、`data_manifest_hash`、`calibration_hash`） |

## 执行、监控与发布
| 卡片 | 脚本/配置 | 产物 | 报告/签名 |
| --- | --- | --- | --- |
| 607 | `execution/switch_policy.yaml`<br>`execution/switch_engine.py` | 切换策略配置<br>`logs/switch_audit/*.log` | 金丝雀演练报告（收益/滑点/换手/状态持久度） |
| 808 | `validation/src/qc_dashboard.py` | `results/qc/date=*/**`<br>`results/qc_summary.md` | 告警工单/补跑记录 |
| 863 | `docs/traceability.md`（本文件）<br>`COMPLIANCE.md`<br>`releases/release.yml` | 发布与合规包 | 审计记录、CI Gate 日志 |

## 使用指引
1. 根据卡片编号查找对应脚本，确保 manifest 与 calibration 哈希与发布绑定。
2. 所有报告需在 `results/` 或 `validation/out/` 中保留，并在 `releases/release.yml` 中引用版本号与签名。
3. 若新增卡片或产物，请同步更新本表，以保持单一事实来源。

