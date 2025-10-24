# 工程日志 · 2025-10-24

**项目**：OrderFlow-V6
**主题**：ATAS DLL bar_vpo_* 导出问题根因诊断与修复
**作者**：系统记录

---

## 一、问题背景回顾（来自 2025-10-23 日志）
- `SimplifiedDataExporter v6.2` 导出数据中 `bar_vpo_price/bar_vpo_vol/bar_vpo_loc/bar_vpo_side` 字段始终为 `null`；
- 先前诊断认为 ATAS SDK 未向自定义指标暴露 Cluster/Footprint 对象或相关属性，导致无法获取单 bar 内的价阶信息（`TryGetVolumeAtPrice` 始终未命中）。

---

## 二、今日进展：根因诊断与修复
1. **假设修正与文档验证**
   - 依据 AI 协作伙伴建议重新审查 ATAS SDK 对 Cluster/Footprint 数据的访问方式；
   - 查阅官方文档（`IndicatorCandle` 参考）与示例代码，确认 SDK 提供 `candle.MaxVolumePriceInfo` 等公共属性以访问单 bar 最大量价阶。

2. **关键发现**
   - v6.2 版本采用的反射（`GetProperty`）尝试访问可能不存在的内部属性（如 `Clusters`、`Footprint`），属于错误数据路径；
   - 正确做法是直接使用 SDK 暴露的公共成员属性。

3. **代码修复（SimplifiedDataExporter v6.3）**
   - **版本升级**：调整 `SimplifiedDataExporter.cs` 与 `.csproj` 中的命名空间、类名、常量、程序集名称和版本号，将所有标识由 v6.2 更新为 v6.3，以强制 ATAS 加载新 DLL 并规避缓存；
   - **逻辑修正**：在 `OnCalculate` 中移除基于反射及 `TryGetVolumeAtPrice` 的 VPO 计算逻辑，改用 `candle.MaxVolumePriceInfo` 直接获取最大量价阶，同时直接访问 `candle.Low`、`candle.High`；
   - **代码清理**：删除失效的 `TryGetVolumeAtPrice`、`SafeConvertToDouble` 辅助函数及 `System.Reflection` 引用；
   - **部署验证**：编译生成 `SimplifiedDataExporter.V63.dll`，部署至 ATAS 指标目录，并在回放/实时数据下验证 `latest.json` 与 `bar_YYYYMMDD.jsonl` 输出。

---

## 三、结果确认
- 导出的 JSON 数据中，`exporter_version = 6.3.0.0`、`schema_version = v6.3`；
- `bar_vpo_price/bar_vpo_vol/bar_vpo_loc/bar_vpo_side` 字段均填充非空值；
- 示例：`"bar_vpo_price": 110490.0, "bar_vpo_vol": 7.853, "bar_vpo_loc": 0.0, "bar_vpo_side": "bear"`。

---

## 四、结论
- 10 月 23 日认为 “ATAS API 访问权限限制” 导致 bar_vpo_* 导出失败的结论不成立；
- 根因在于 v6.2 代码采用错误的数据访问方式（反射猜测内部属性），未直接使用 `candle.MaxVolumePriceInfo` 等公共属性；
- 通过修正访问路径并升级 DLL 后，bar_vpo_* 数据导出功能恢复正常。

---

**状态小结**
> DLL 导出 bar_vpo_* 数据的功能已恢复正常，项目可继续推进下游数据处理与特征工程。
