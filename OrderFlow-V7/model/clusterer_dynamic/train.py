"""clusterer_dynamic.train

V7 版本的在线聚类训练脚本：
- 使用指数加权增量 GMM（K=2, lambda≈0.97, 滑窗≈30d, 步长Δ=1d）；
- 特征输入包含微结构流与 macro_factor 慢锚；
- 输出最新标签分布与漂移指标，供决策 clarity/abstain 门控使用。
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Tuple

import numpy as np

def _ensure_v6_legacy() -> Path | None:
    import sys

    root = next((p for p in Path(__file__).resolve().parents if (p / "third_party").exists()), None)
    if root and str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from third_party.legacy_bootstrap import ensure_v6_legacy

    return ensure_v6_legacy()


_LEGACY_ROOT = _ensure_v6_legacy()

try:
    from v6_legacy.utils.seed import seed_everything
except ImportError:  # pragma: no cover - V7 将提供新的工具实现
    def seed_everything(seed: int) -> None:
        np.random.seed(seed)


@dataclass
class ClustererConfig:
    window_days: int = 30
    step_days: int = 1
    lambda_: float = 0.97
    n_components: int = 2
    min_samples: int = 5_000
    drift_metric: str = "psi"
    output_dir: Path = Path("output/results/clusterer_dynamic")


class OnlineGMM:
    """极简在线 GMM 框架，后续可替换为 prod 实现。"""

    def __init__(self, n_components: int, lambda_: float) -> None:
        self.n_components = n_components
        self.lambda_ = lambda_
        self.means: np.ndarray | None = None
        self.covs: np.ndarray | None = None
        self.weights: np.ndarray | None = None

    def partial_fit(self, batch: np.ndarray) -> None:
        if batch.size == 0:
            return
        if self.means is None:
            self.means = batch.mean(axis=0, keepdims=True).repeat(self.n_components, axis=0)
            self.covs = np.stack([np.cov(batch, rowvar=False)] * self.n_components)
            self.weights = np.ones(self.n_components) / self.n_components
            return
        momentum = 1.0 - self.lambda_
        batch_mean = batch.mean(axis=0)
        self.means = (1 - momentum) * self.means + momentum * batch_mean
        # 占位：真正实现需要增量协方差/权重更新

    def predict_proba(self, batch: np.ndarray) -> np.ndarray:
        if self.means is None or self.covs is None or self.weights is None:
            raise RuntimeError("Model not fitted")
        # 占位实现：平均分布
        return np.ones((batch.shape[0], self.n_components)) / self.n_components


def load_training_windows(feature_paths: Iterable[Path]) -> Iterable[np.ndarray]:
    for path in feature_paths:
        data = np.load(path)
        yield data


def compute_prototype_drift(previous: np.ndarray, current: np.ndarray) -> float:
    if previous.size == 0 or current.size == 0:
        return 0.0
    eps = 1e-8
    previous = previous / (previous.sum() + eps)
    current = current / (current.sum() + eps)
    return float(((current - previous) * np.log((current + eps) / (previous + eps))).sum())


def train(config: ClustererConfig) -> Tuple[Path, Path]:
    seed_everything(2025)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    model = OnlineGMM(config.n_components, config.lambda_)
    prototype_history = []
    labels_path = config.output_dir / "labels_wt.npy"
    drift_path = config.output_dir / "cluster_artifacts.json"

    feature_dir = Path("data/processed/clusterer_dynamic")
    feature_paths = sorted(feature_dir.glob("*.npy"))
    last_proto = np.array([])
    for window in load_training_windows(feature_paths):
        model.partial_fit(window)
        probs = model.predict_proba(window)
        proto = probs.mean(axis=0)
        drift = compute_prototype_drift(last_proto, proto) if last_proto.size else 0.0
        prototype_history.append({"prototype": proto.tolist(), "drift": drift})
        last_proto = proto

    if prototype_history:
        np.save(labels_path, np.array([p["prototype"] for p in prototype_history]))
        drift_summary = {
            "history": prototype_history,
            "drift_health": max(p["drift"] for p in prototype_history),
            "config": asdict(config),
        }
        drift_path.write_text(json.dumps(drift_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return labels_path, drift_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the V7 dynamic clusterer")
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--step-days", type=int, default=1)
    parser.add_argument("--lambda", dest="lambda_", type=float, default=0.97)
    parser.add_argument("--n-components", type=int, default=2)
    parser.add_argument("--min-samples", type=int, default=5_000)
    parser.add_argument("--output-dir", type=Path, default=ClustererConfig.output_dir)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = ClustererConfig(
        window_days=args.window_days,
        step_days=args.step_days,
        lambda_=args.lambda_,
        n_components=args.n_components,
        min_samples=args.min_samples,
        output_dir=args.output_dir,
    )
    labels_path, drift_path = train(config)
    print(f"labels saved to {labels_path}")
    print(f"artifacts saved to {drift_path}")


if __name__ == "__main__":
    main()
