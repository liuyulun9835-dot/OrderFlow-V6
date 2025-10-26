# OrderFlow V7 — 任务卡片（首版）

## 数据 Data
- [Data-101] ATAS 守护进程：保障订单流导入 + 心跳监控；生成 `data/manifests/atas_guard.json`。
- [Data-102] 分钟连续性审计：对齐撮合日历、补洞并输出 `output/qa/data_continuity.md`。
- [Data-103] macro_factor 慢锚生成：基于 `features/macro_factor/config.yaml` 导出 `macro_factor_slowanchor.parquet`。

## 特征 Features
- [Feat-201] 微结构流水线：winsorize→zscore→缺失策略，生成 `data/processed/microflow/latest.npy`。
- [Feat-202] 慢锚合成：合并 macro_factor 与 microflow，提供给 clusterer_dynamic。
- [Feat-203] rolling_cluster_labeler：根据 TVTP 输出生成 `labels_rollover.parquet`。

## 模型 Models
- [Model-301] clusterer_dynamic 滚动训练（W=30d, Δ=1d, λ=0.97）→ `labels_wt.npy`, `cluster_artifacts.json`。
- [Model-302] hmm_tvtp_adaptive 训练（drivers=[macro_anchor, drift]）→ `tvtp_artifacts.json`。
- [Model-303] 校准评估：计算 ECE/Brier/abstain_rate/prototype_drift，写入 validator_v2。

## 决策 Decision
- [Decision-401] transition_prob>τ 触发方向判别器，clarity→仓位映射函数实现。
- [Decision-402] 冷却 900s + drift 门控集成至 `decision_engine.py`。
- [Decision-403] rules 库更新：transition/low_confidence 示例完成并对接 orchestrator。

## 验证与发布 Validation & Shipping
- [Valid-501] validator_v2：串联 drift/calibration/abstain 三道门。
- [Valid-502] 生成 `output/publish_docs/VALIDATION.md` & `OF_V7_stats.xlsx`；附签名。
- [Ship-601] 发布流水：更新 `output/publish_docs/CHANGELOG.md` 并绑定门控结果。

## 编排 Orchestration
- [Orch-701] 全流程 orchestrator（数据→特征→模型→发布），支持锁与重试策略。
- [Orch-702] 运行日志：集成至 `output/qa/orchestrator_logs/`。
