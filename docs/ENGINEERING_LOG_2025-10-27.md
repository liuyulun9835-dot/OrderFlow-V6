# 工程日志｜中央数据厨房（2025-10-27）

## 今日完成
- 在 `data` 分支**剥离模型/决策/验证代码**，仓库专注于数据层。
- 设计并落地**中央数据厨房**目录结构（crawler/storage/align/features/publish/daemon）。
- 新增 **对齐与校准**脚本：`kitchen/align/align_ab_streams.py`（统一 UTC/right-closed，Binance minute_close 对齐）。
- 新增 **微观特征**脚本：`kitchen/features/make_features_micro.py`（含 bar_vpo_* 与 OHLC 派生；缺失留 NA 并打 `impute_flag`）。
- 新增 **快照发布**脚本：`kitchen/publish/*`（manifest + signatures + 原子发布至 snapshots/<date> + LATEST 指针）。
- 新增 **治理契约**：`governance/SCHEMA_data.json`、`SCHEMA_features.json`、`CONTROL_kitchen.yaml`（覆盖率/价差/时钟阈值）。
- 新增 **总控与爬虫编排**：`scripts/launcher.py`、`scripts/binance_runner.py`；保留用户脚本 `scripts/fetch_binance_1m.py`。
- 新增 **占位**：`scripts/start_atas.ps1`、`scripts/watchdog_atas.py`（ATAS GUI 自动化待后续完善）。
- 新增 **Makefile** 目标：`data.*` 与 `kitchen.run`。

## 未完成 / 待续
- ATAS 自动化：工作区恢复、指标心跳、异常重启策略——**占位**已建，待具体方案补全。
- 对齐阈值的长期监控与告警通道（Telegram/Email）。
- 云端对象存储（S3/MinIO/OSS）推送脚本（rclone/cli）接入。
- `kitchen/daemon/kitchen_daemon.py` 目前为最小轮询版，待接入调度器/重试策略。

## 使用提示
- 最小流水线：
  1. `python -m kitchen.align.align_ab_streams --atas <ATAS_FILE> --binance <BINANCE_FILE>`
  2. `python -m kitchen.features.make_features_micro`
  3. `python -m kitchen.publish.make_manifest && python -m kitchen.publish.make_signatures`
  4. `python -m kitchen.publish.publish_snapshot`
