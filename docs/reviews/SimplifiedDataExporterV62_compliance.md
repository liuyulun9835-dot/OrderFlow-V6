# SimplifiedDataExporterV62 功能性检视

本文针对用户提供的 `SimplifiedDataExporterV62` C# 指标代码，与仓库中对 ATAS 导出器的既有功能性要求进行对照检视。

## 参考基线
- 仓库当前提供的指标实现为 `orderflow_v_6/integrations/atas/indicators/SimplifiedDataExporter.cs`，其在工程日志中被要求写出 `window_id`、`flush_seq` 等字段并声明窗口语义。【F:docs/工程日志_order_flow_v_6_（_2025_10_17_).md†L57-L58】
- 指标 README 约定了输出文件与字段：
  - 输出 `latest.json`（覆盖）与每日分区 JSONL 文件；
  - 字段至少包含 `timestamp`、OHLCV、`poc/vah/val/cvd`、`absorption_*`、`exporter_version`、`schema_version` 等。【F:orderflow_v_6/integrations/atas/indicators/ATAS_EXPORTER_README.md†L12-L21】
- 工程指引要求在 ATAS 中加载的指标名称为 “SimplifiedDataExporter”。【F:orderflow_v_6/integrations/atas/indicators/ATAS_EXPORTER_README.md†L5-L11】

## 符合项
- **输出结构**：代码在 `WritePayload` 中同时写入根目录下的 `latest.json` 与按日期分区的 `bar_YYYYMMDD.jsonl` 文件，满足 README 对产物的要求。
- **字段覆盖**：序列化文档中保留了既有字段（OHLCV、`poc`、`vah`、`val`、`cvd`、`absorption_*`、`window_id`、`flush_seq`、`fingerprint`、`schema_version` 等），并额外增加了 VPO 相关字段；新增字段不会破坏既有下游校验。
- **窗口约束**：`CollectCompletedMinutes` 与 `window_convention` 的写法继承了现有版本，继续保证“分钟右闭区间”语义。
- **日志与目录安全**：仍然通过 `EnsureExportDirectory`、互斥锁与 `SafeMode` 控制启动期写入，符合稳定性约束。

## 风险与不符合项
1. **指标类型重命名**：类名从 `SimplifiedDataExporter` 改为 `SimplifiedDataExporterV62`，同时命名空间改为 `AtasCustomIndicators.V62`。这会导致已存在的 ATAS 布局或脚本无法直接找到 README 所述的 “SimplifiedDataExporter” 指标类型，需要同步更新加载说明或保留旧类型别名，否则不满足仓库对可加载名称的要求。【F:orderflow_v_6/integrations/atas/indicators/ATAS_EXPORTER_README.md†L5-L11】
2. **公共枚举命名空间变化**：`TimezoneOption`、`SessionModeKind` 等枚举被放到命名空间之外。仓库现有实现将这些类型暴露在 `AtasCustomIndicators` 命名空间下；外部脚本若引用 `AtasCustomIndicators.TimezoneOption` 会在新版下解析失败，需要将枚举与结构恢复到命名空间内以避免破坏现有引用。【F:orderflow_v_6/integrations/atas/indicators/SimplifiedDataExporter.cs†L319-L361】

## 结论
在保留原有类名/命名空间，并将辅助类型重新放回命名空间的前提下，代码的主体逻辑与仓库功能性要求保持一致；否则会引入对现有部署脚本及引用的兼容性破坏。
