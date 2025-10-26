# clusterer_dynamic

V7 在线聚类器，负责将微结构与慢锚特征映射到双状态标签：

- **算法**：指数加权 GMM (K=2, λ≈0.97, 滑窗 30d, 步长 1d)；
- **输入**：`data/processed/microflow/*.npy` 与 `data/processed/macro_factor/*.npy`；
- **输出**：`labels_wt.npy`（权重标签）、`cluster_artifacts.json`（漂移与健康度）；
- **漂移监测**：记录 prototype_drift、clarity、macro_factor_used 供治理层签名。

训练脚本：`train.py`；配置：`config.yaml`。
