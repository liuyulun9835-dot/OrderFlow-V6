# 工程日志 · OrderFlow_V6 · （2025-10-17）—修订版

> 记录人：QA 团队（林 / 周 / 邵） · 范围：OrderFlow‑V6 仓库、工程卡片、V6 综合项目说明书（理论强化版）

---

## 前情提要（Context & Outcomes）

**本次对话做了什么**
- **角色确认**：按 *Part 2: prompt_qa_team*，以独立 QA 身份进行结构化审阅与验收，只依据仓库代码、工程卡片与理论说明书三件套。
- **一致性审查**：检查代码与卡片口径（路径/Schema/UTC/offset/容差/分层校准/成本 Gate/签名等），输出一份 **20 项一次性验收闸门核表**。
- **开发改动复核**：审阅开发团队两条 Codex 指令（卡片修改 + 代码修复），逐条加注 QA 意见；随后对更新压缩包进行复验。
- **最终裁定**：在补齐两处 P0 与一处口径澄清后，QA 返回 **【修改方案通过】**。

**本轮对话的定位**
- 仅记录**已完成的讨论与验收结果**；不包含任何未来计划或路线建议，避免影响后续会话的理解与决策。

---

# Output task 1: Executive Summary（高管摘要）

### 讨论与决策的核心要点
- **聚焦工作内容**（本轮收口范围）
  - 以 **Plan‑A 双轨**的最低可验证闭环为准绳，**只验“数据→校准→成本→质量告警→签名与合规→金丝雀演练（草案）”**。
  - 不涉及未来状态机实现与真实热切换，仅验证前置护栏与证据链是否完备。

- **关键决策**
  1) **口径统一**：UTC、右闭左开、`direction=backward` 合并、5–15s 容差、错配率<0.1%（跨分钟就近吸附占比）。
  2) **分层校准**：按波动/量能四分位评估 PSI/KS/ECE；阈值 **PSI<0.2、KS 统计量≤0.1（或 p>0.05，固定其一）、ECE<3%**；越线即不可合并并触发降级。
  3) **成本闸门**：base / +50% / ×2 三档任一档净效应<0 → 阻断；且 base 档 **边际收益 ≥ 1.5× 成本**。
  4) **签名与合规**：所有 Validator 产物写入 `schema_version/build_id/data_manifest_hash/calibration_hash`；CI 检查 `COMPLIANCE.md` 必备章节关键字。
  5) **切换前置**（仅作为演练口径）：PSI≤0.1、错配率<0.1%、ECE<3%、bar 连续性≥99.9%、成本 Gate 通过。

### 实际产出（Artifacts）
- **工程卡片与文档**
  - `order_flow_v_6_todo.md`：新增/强化 109/110/111/112/116/117/118/403/404/405/406/607/808 的**产物/门槛/DoD**，并在页末新增 **P0 Gate 顺序**（Schema→连续性→校准→成本→Validator/签名→Switch）。
  - `COMPLIANCE.md`：用途/保留期/再分发/脱敏四段；CI 含关键字 Gate。
  - `docs/traceability.md`：建立 **卡片→脚本→产物→报告** 的索引链路。
  - `releases/release.yml`：绑定 `data_manifest_hash + calibration_hash + model_artifact_id`，用于回滚与影子/金丝雀保留。

- **报告与配置**
  - `bar_continuity_report.md`：连续性≥99.9%；不达标时阻断。
  - `tick_quality_report.md`：到达间隔 **CV≤1.5 & p99≤3×median**；不达标时阻断。
  - `merge_and_calibration_report.md`：`[-2,+2]min` offset 评分曲线；错配率定义与统计，<0.1% 达标。
  - `calibration_profile.json`：分层（波动/量能四分位）**PSI/KS/ECE** 三元组与 PASS/FAIL；越线段列表。
  - `validation/configs/priority_downgrade.yaml`：越线/缺口→自动降级到 bar 标签并记录日志。
  - `validation/configs/costs.yaml`、`validation/configs/preregister.yaml`：成本评估与检验预注册。

- **脚本与 Gate**
  - `preprocessing/calibration.py`：分层 Quantile Mapping + 指标计算。
  - `validation/src/precheck_costs.py`：base/+50%/×2 三档评估，任一档<0 即退出；打印成本敏感性曲线。
  - `validation/src/validate_outputs.py`：检查产物签名四键，一致性失败即拒收。
  - `scripts/update_pipeline.ps1`：在 `qc_summary.md` 回填 `seed、data_manifest_hash、exporter_version、schema_signature`。
  - `scripts/canary_switch_dryrun.py`：输出演练版 pre/post（收益/滑点/换手/状态持久度）。

- **导出器与 Schema 对齐**
  - `SimplifiedDataExporter.cs` 写出 `window_id/flush_seq` 并声明“分钟右闭左开”。
  - `preprocessing/schemas/atas_schema.json` 同时支持**扁平/嵌套**吸收字段与元字段白名单。

- **单测与 CI**
  - 单测覆盖：offset/容差、双 Schema、分层校准、成本 Gate、分钟边界（right‑closed）。
  - CI：`TZ=UTC`、仅 lint+pytest、含 **cost gate** 与 **signature gate**、合规关键字检查。

### 验收结论（QA Verdict）
- 初次审阅发现两项 P0 与一项口径澄清；开发修正后，**全部门槛达标**。
- QA 发出最终回执：**【修改方案通过】**。

> 注：本摘要仅陈述本轮对话的**讨论要点与实得成果**，不含未来工作规划。

---

# Output task 2: The Chronicle（对话史记）

**Chronicle‑A｜一致性审查**
- 对齐“UTC、右闭左开、direction=backward、5–15s 容差、错配率<0.1%”等口径；统一分层校准阈值；确认降级策略接入。

**Chronicle‑B｜开发改动审阅**
- 审核两条 Codex 指令（卡片侧/代码侧）：在关键处加注 QA 备注（阈值、定义、Gate 顺序、合规模板、签名四键、CI 检查项）。

**Chronicle‑C｜复验与裁定**
- 新压缩包跑核表：17/20 先达标 → 指定两处 P0（切换前置 PSI 过松；CI 缺合规 Gate）与一处 KS 口径澄清 → 修正后重验全过 → 出具“通过”。

**Chronicle‑D｜证据与索引**
- 证据产物：连续性/间隔报告、offset 曲线与错配率、分层校准 JSON、成本 Gate 报告、产物签名检查日志、合规文档关键字检查。
- 索引文件：`docs/traceability.md` 将卡片 ID ↔ 脚本 ↔ 产物 ↔ 报告一一对应，确保复盘时“证据链闭合”。

---

> 本工程日志 **仅记录已完成的讨论与验收**，不含任何未来任务或时间表，确保后续会话的自主规划不受干扰。

