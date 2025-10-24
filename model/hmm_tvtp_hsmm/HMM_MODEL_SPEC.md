## 🧠 OrderFlow V6 — HMM 模型说明书（稳定版 v2.0）

**文件路径：** `model/hmm_tvtp_hsmm/HMM_MODEL_SPEC.md`
**版本：** v2.0
**日期：** 2025-10-24
**作者：** OrderFlow-V6 Core Team

---

### 1. 模型定位与目标

* **核心目标**：以隐马尔可夫模型（HMM）为框架，基于 1m 粒度订单流元数据提取的二级特征，识别市场的两种结构状态——

  * 平衡（Balance / Rotation）
  * 失衡（Imbalance / Trend）
    并量化它们之间的**相变概率**。
* **应用目标**：为上层的**决策引擎与方向性判断器**提供状态概率与转移信号，支撑 15-60 min 时间尺度的策略逻辑。

---

### 2. 模型形式（Two-State TVTP-HMM）

模型参数：(\lambda = {\pi, A_t, B})

| 元素             | 定义                                       | 实现说明                                      |                                 |
| -------------- | ---------------------------------------- | ----------------------------------------- | ------------------------------- |
| **隐藏状态 (S)**   | ([S_1=\text{balance},,S_2=\text{trend}]) | 二元结构态；“相变”不独立成态。                          |                                 |
| **转移矩阵 (A_t)** | (P(q_{t+1}=S_j                           | q_t=S_i,Z_t)=\sigma(\beta_{ij}^\top Z_t)) | TVTP（时变转移）；(Z_t) 为微观与宏观驱动。      |
| **发射分布 (B)**   | (P(O_t                                   | q_t=S_j))                                 | 对角高斯 / t 分布；会话内 z-score 标准化后建模。 |
| **初始概率 (\pi)** | (P(q_1=S_i))                             | 默认 (\pi=[0.9,0.1])，可在每会话重置。               |                                 |

---

### 3. 驱动与观测

#### 3.1 驱动变量 (Z_t)

* **微观层**：`cvd_z`, `cvd_diff`, `bar_vpo_loc`, `absorption_flag`, `volume_z`, `range_z`
* **宏观层**：`close/MA200`, `rv_1h_pctl`

> 所有特征均右闭窗口（仅用到 t 及之前数据）。

#### 3.2 观测序列 (O_t)

```
O_t = [ret_1m, range_z, volume_z,
       cvd_z, bar_vpo_loc, absorption_flag, rv_1h_pctl]
```

* 标准化：会话内 z-score + winsorize (p1,p99)
* 缺失处理：显式 NaN mask，禁止 ffill 补零。

---

### 4. 学习与推断

#### 4.1 学习（Baum-Welch / EM）

* 多起点 + AIC/BIC 筛选
* 切分：Purged K-Fold (k=5, embargo=5 bars)
* 校验：跨期 PSI / KS 稳定性 > 0.8 方可发布

#### 4.2 推断输出

| 输出                                                   | 含义        | 用途             |      |
| ---------------------------------------------------- | --------- | -------------- | ---- |
| (\gamma_t=P(q_t=S_2                                  | O_{1:t})) | 当前处于 trend 概率  | 状态标签 |
| (\tau_t=P(q_{t+1}=S_2                                | q_t,Z_t)) | 下一步转入 trend 概率 | 相变前兆 |
| (\text{state}_t=\arg\max_j\gamma_t)                  | 最可能状态     | 可视化 / 回测       |      |
| (\text{trigger}): (\tau_t>\theta) 且 (\dot\gamma_t>0) | 相变候选事件    | 驱动方向判断器        |      |

---

### 5. 方向性判断器接口

当触发 (\tau_t>\theta) 时调用：

```
directional_classifier(O_{t-k:t})
 → {label: bull/bear, confidence: 0–1}
```

写入 `logs/decision_log.jsonl` 字段：

```
{"trigger": {"prob":0.86,"threshold":0.80},
"directional_classifier":{"label":"bullish","confidence":0.91}}
```

---

### 6. 模型产出与元数据

| 文件                                        | 说明                                                                          |
| ----------------------------------------- | --------------------------------------------------------------------------- |
| `model/artifacts/hmm_tvtp.pkl`            | 模型权重                                                                        |
| `model/artifacts/hmm_meta.json`           | 参数摘要 + 四键签名（schema_version, build_id, data_manifest_hash, calibration_hash） |
| `model/hmm_tvtp_hsmm/state_inference.py`  | 推断接口                                                                        |
| `output/results/hmm_validation_report.md` | 训练与稳定性报告                                                                    |

---

### 7. 解释与评估

* **停留分布** ：衡量状态黏性与平均持续时间
* **翻转率 / 滞后分布** ：评估抖动与反应速度
* **方向误判率 + ECE** ：验证方向判断器一致性
* **跨年份 PSI / KS** ：漂移检测

---

### 8. 门控与合规

* 数据来源需附 manifest 哈希；缺失或不一致 → 拒训
* 成本/可达性 Gate (卡 118) 必须通过
* 所有制品需写入 `release.yml` 并签名绑定

---

### 9. 未来扩展

* **HSMM 黏性约束** ：添加最小停留时间 ≥ k bars
* **Regime-switch AR 混合** ：扩展状态自回归层
* **贝叶斯 TVTP-HMM** ：在样本稀疏区估计转移先验

---

### 10. 附录 A 示例配置片段

```
states: [balance, trend]
tvtp:
  enabled: true
  drivers: [cvd_z, bar_vpo_loc, close_ma200]
  link: logit
macro_factor_used: true
signatures:
  schema_version: v2.0
  build_id: 20251024
  data_manifest_hash: "<sha256>"
  calibration_hash: "<sha256>"
```

---

## 🧩 Codex 指令

```
# 在 Git 仓库的 model 目录中创建并提交 HMM 说明书
codex write-file --path "model/hmm_tvtp_hsmm/HMM_MODEL_SPEC.md" --from-template "HMM说明书v2.0"
git add model/hmm_tvtp_hsmm/HMM_MODEL_SPEC.md
git commit -m "docs(model): add stable HMM_MODEL_SPEC v2.0 under model/hmm_tvtp_hsmm/"
git push origin main
```

---

执行后，AI 开发代理就能在调用 `model/` 时读取并遵循该说明文件，确保后续自动生成的 `train_tvtp.py` 和 `state_inference.py` 与此文档定义严格一致。
