工程日志 · 2025-10-24

项目：OrderFlow-V6
主题：ATAS DLL bar_vpo_* 导出问题根因诊断与修复
作者：系统记录

一、问题背景回顾 (来自 2025-10-23 日志)

SimplifiedDataExporter v6.2 导出数据中，bar_vpo_price, bar_vpo_vol, bar_vpo_loc, bar_vpo_side 字段始终为 null。

初步诊断（基于 v6.2 代码中的反射尝试 TryGetVolumeAtPrice 未命中任何价阶容器）认为：ATAS SDK 未向自定义指标暴露 Cluster/Footprint 对象或相关属性，导致无法获取单 bar 内的价阶信息。

二、今日进展：根因诊断与修复

假设修正与文档验证：

根据 AI 协作伙伴的建议，重新审查了 ATAS SDK 访问 Cluster/Footprint 数据的方式。

通过查阅 ATAS 官方 SDK 文档 (IndicatorCandle 类参考) 并结合代码示例，确认 SDK 提供了直接访问 bar 内最大量价阶信息的公共属性，例如 candle.MaxVolumePriceInfo。

关键发现： v6.2 版本中采用的反射 (GetProperty) 方式试图访问可能不存在的内部属性（如 "Clusters", "Footprint"），这是错误的数据访问路径。正确的路径是直接调用 SDK 提供的公共成员。

代码修复 (SimplifiedDataExporter v6.3)：

版本升级： 修改 SimplifiedDataExporter.cs 和 SimplifiedDataExporter.csproj 文件，将所有版本标识符从 v6.2 更新为 v6.3 (包括命名空间、类名、常量、程序集名称和版本号)，以强制 ATAS 加载新 DLL，避免缓存问题。

逻辑修正：

在 OnCalculate 方法中，移除了原先基于反射和 TryGetVolumeAtPrice 函数的 VPO 计算逻辑。

替换为直接调用 candle.MaxVolumePriceInfo 属性来获取最大量价阶信息。

同样，对 candle.Low 和 candle.High 的访问也改为直接调用，移除了不必要的反射。

代码清理： 删除了已失效且不再需要的 TryGetVolumeAtPrice 和 SafeConvertToDouble 辅助函数，以及相关的 System.Reflection 引用。

部署与验证：

编译生成 SimplifiedDataExporter.V63.dll。

部署新 DLL 至 ATAS 指标目录。

运行 ATAS 回放或实时数据，观察导出器输出的 latest.json 和 bar_YYYYMMDD.jsonl 文件。

三、结果确认

导出的 JSON 数据中，exporter_version 确认为 6.3.0.0，schema_version 为 v6.3。

关键字段 bar_vpo_price, bar_vpo_vol, bar_vpo_loc, bar_vpo_side 已成功填充非 null 数据，与预期一致。

例如："bar_vpo_price": 110490.0, "bar_vpo_vol": 7.853, "bar_vpo_loc": 0.0, "bar_vpo_side": "bear"

四、结论

10 月 23 日关于 bar_vpo_* 导出失败的根因判断（“ATAS API 访问权限限制”）不准确。

实际根因是 v6.2 代码中采用了错误的数据访问方法（通过反射猜测内部属性名），而非直接使用 SDK 提供的公共属性 (candle.MaxVolumePriceInfo)。

通过修正代码逻辑为直接 SDK 调用，并升级 DLL 版本后，bar_vpo_* 数据导出问题已成功解决。

状态小结

DLL 导出 bar_vpo_* 数据的功能已恢复正常。项目可继续按计划进行下游数据处理与特征工程。
