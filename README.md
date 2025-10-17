# OrderFlow V6

## Project Overview
OrderFlow V6 是一个以订单流与市场微结构为核心的多层交易研究与执行平台，强调“数据 → 指标 → 状态 → 验证 → 决策 → 执行”的分层架构，结合数据驱动、状态模型、统计控制与成本鲁棒特性实现可迁移的高频/中频策略能力。

## Inheritance
系统延续了 V4/V5 中的因子模块、状态分类、决策树与风控执行接口，同时在 V6 中引入 HMM/TVTP/HSMM 状态模型、非线性概率与多维评分框架，并保持与既有执行/验证接口的兼容，内部实现升级为面向校准与多源状态的架构。

## Development Path
V6 采用 Plan-A 的双轨渐进路线：
- **轨道 A（Binance 低/中频）**：先构建稳定的状态机与验证闭环，输出基线状态源。
- **轨道 B（ATAS Tick/L2 高频）**：持续滚动采集，完成 minute↔tick 映射与校准，在通过成本鲁棒与执行可达性闸门后热切换为主源。
选择 Plan-A 的原因是“核心资产 = 系统 + 数据 + 校准器”，可长期沉淀跨粒度复用能力并降低状态源切换风险。

## Data & Merging
三类数据按照统一 UTC、右闭左开边界与 manifest 管理：
- **ATAS Bar（≤3 个月）**：落地至 `data/raw/atas/bar/{symbol}/resolution={X}/date=YYYY-MM-DD/`，生成 `export_manifest.json` 与连续性报告。
- **ATAS 真 Tick（7 天滚动）**：近窗 JSON，超窗转 Parquet 至 `data/raw/atas/tick/{symbol}/date=YYYY-MM-DD/`，每日产出 `tick_quality_report.md`。
- **Binance 行情**：`data/exchange/{symbol}/kline_1m.parquet` 补足长期窗口。
基于 `preprocessing/align/index.parquet` 与 `preprocessing/configs/merge.yaml` 构建可声明式的对齐索引，执行 Tick>ATAS Bar>Binance 的降级策略，并通过 `mapping_tick2bar.pkl`、`calibration_profile.json` 与 `results/merge_and_calibration_report.md` 固化 PSI/KS、置信度/ECE 校准及 HSMM 黏性策略。最终产出 `features_lowfreq.parquet`、`features_hft.parquet` 等命名规范的特征集。

## Validation
Validator v2 结合单/多变量显著性、FDR、VIF 与成本鲁棒门槛，借助 `validation/configs/validator_v2.yaml`、`validation/src/qc_report.py` 等工具实现一键验证。新引入的 `validation/precheck/costs_gate.md` 作为前置闸门，确保 base/+50%/×2 成本与成交可达性达标后方可进入 401–405 的完整验证流。

## Execution
执行层以 `strategy_core` 决策树和评分为核心，配合 `execution/switch_policy.yaml` 的 AB 双源热切换策略：当轨 B 满足校准/鲁棒/可执行性要求时切主，异常时回滚轨 A，并在 `logs/switch_audit/` 中保留审计记录，兼容 V5 的执行接口以确保升级可控。

## Milestones & Health Metrics
已完成 000–108 的工程卡片、ATAS 导出与 Binance 历史拉取，实现最小闭环。健康度面板聚焦：连续性/缺失率、对齐一致率、PSI/KS/ECE、置信度校准、成本鲁棒通过率与执行可达性，指标成果将沉淀在 `results/qc/`、`results/merge_and_calibration_report.md`、`validation` 输出中。

## Repo Structure
```text
OrderFlow-V6/
├── atas_integration/
├── data/
├── docs/
├── execution/
├── logs/
├── models/
├── orderflow_v6/
├── preprocessing/
├── results/
├── scripts/
├── strategy_core/
├── tests/
├── utils/
└── validation/
```

关键目录与脚本：
- [atas_integration/indicators/SimplifiedDataExporter.cs](atas_integration/indicators/SimplifiedDataExporter.cs)：ATAS 指标导出与回放配置。
- [preprocessing/fetch_kline.py](preprocessing/fetch_kline.py)、[preprocessing/merge_to_features.py](preprocessing/merge_to_features.py)：行情抓取与特征合并脚本。
- [scripts/init_data_tree.py](scripts/init_data_tree.py)：数据分层占位初始化。
- [validation/src/qc_report.py](validation/src/qc_report.py)、[validation/src/validate_json.py](validation/src/validate_json.py)：数据质控与 schema 校验。
- [results/README.md](results/README.md)：实验与报告复现指引。

## Quickstart
1. 安装依赖：`poetry install`
2. 初始化目录：`python scripts/init_data_tree.py`
3. 拉取/追加行情并合并特征：
   ```powershell
   python scripts/update_pipeline.ps1 -Symbol BTCUSDT -Since 2024-01-01 -Until 2024-01-07
   ```
   `preprocessing/merge_to_features.py` 需显式传入 `--kline data/exchange/BTCUSDT/kline_1m.parquet` 与 `--atas-dir data/raw/atas/bar/BTCUSDT`，默认 UTC 右闭左开。
详细任务与路径请参考 [任务卡片库](docs/OrderFlow%20V6%20—%20任务卡片库V1.1.md) 与 [工程日志](工程日志_order_flow_v_6_（_2025_10_15_）.md)。

## Results & Reports
所有合并、校准、验证与 QC 报告需落盘至 `results/`：
- `results/bar_continuity_report.md` / `results/tick_quality_report.md`：连续性与 tick 质量基线。
- `results/merge_and_calibration_report.md`：minute↔tick 映射与分层校准结论。
- `results/precheck_costs_report.md`：成本闸门敏感度曲线。
- `results/canary_switch_dryrun.md`：热切换策略干跑结果。
更多复现指引见 [results/README.md](results/README.md)。
