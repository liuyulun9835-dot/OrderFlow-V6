# SimplifiedDataExporter (OrderFlow V6)
## Build & Deploy
- Build: Release|AnyCPU → 输出 DLL
- Deploy: 将 DLL 放入 ATAS 自定义指标目录（参见 ATAS 文档），重启 ATAS 后加载 "SimplifiedDataExporter"
## Params
- SessionMode: rolling:60 / session
- WriteOnBarCloseOnly: true
- OutputTimezone: UTC
- Backfill: false
- ExportDir: %USERPROFILE%\Documents\ATAS\Exports
## Output Files
- latest.json（覆盖）
- market_data_yyyyMMdd.jsonl（追加）
## Fields
- timestamp (UTC), open, high, low, close, volume,
  poc, vah, val, cvd,
  absorption_detected, absorption_strength, absorption_side,
  exporter_version, schema_version
## Notes
- 回放三个月历史时，保持“每分钟唯一写”。
- schema_version 变更须发版；下游 QC 将校验。
