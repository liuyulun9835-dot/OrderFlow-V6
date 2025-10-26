# hmm_tvtp_adaptive

V7 自适应 TVTP-HSMM：

- **驱动**：macro_factor 慢锚、clusterer_dynamic 漂移、决策 clarity；
- **目标**：提供 transition(A→B/B→A) 概率、阈值 τ，并产出门控用的校准指标；
- **输出**：`tvtp_artifacts.json`（包含 transition_summary、calibration 指标）。

请结合 `config.yaml` 配置数据入口，并在 `train.py` 中写入漂移/ECE/Brier/abstain 汇总以供验证层读取。
