"""hmm_tvtp_adaptive.train

自适应 TVTP-HSMM 训练脚本：
- 驱动因子包含 macro_factor 慢锚与 clusterer_dynamic 漂移指标；
- 结合 clarity 与 abstain 门控输出状态转移概率；
- 在 V7 中与决策引擎共享 drift/ECE/Brier 校准信息。
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable

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
except ImportError:  # pragma: no cover
    def seed_everything(seed: int) -> None:
        np.random.seed(seed)


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    x = x - x.max(axis=axis, keepdims=True)
    exp = np.exp(x)
    return exp / exp.sum(axis=axis, keepdims=True)


@dataclass
class AdaptiveConfig:
    hidden_states: int = 2
    max_iter: int = 50
    tol: float = 1e-4
    output_dir: Path = Path("output/results/hmm_tvtp_adaptive")
    calibration_targets: Dict[str, float] | None = None


class AdaptiveTVTP:
    """占位 HMM，真实实现需替换为生产库。"""

    def __init__(self, n_states: int) -> None:
        self.n_states = n_states
        self.transition_logits = np.zeros((n_states, n_states))

    def fit(self, emissions: np.ndarray, drivers: np.ndarray, max_iter: int, tol: float) -> None:
        # 占位实现：根据 drivers 的均值调整 logit
        driver_mean = drivers.mean(axis=0)
        base = np.tile(driver_mean.mean(), (self.n_states, self.n_states))
        self.transition_logits = base

    def predict_transition(self, drivers: np.ndarray) -> np.ndarray:
        logits = np.tile(self.transition_logits, (drivers.shape[0], 1, 1))
        return softmax(logits, axis=2)


def load_inputs(emission_dir: Path, driver_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    emissions = np.load(emission_dir / "emissions.npy")
    drivers = np.load(driver_dir / "drivers.npy")
    return emissions, drivers


def compute_calibration(transitions: np.ndarray) -> Dict[str, float]:
    ece = float(np.abs(transitions.mean() - 0.5))
    brier = float(((transitions - 0.5) ** 2).mean())
    abstain_rate = float((transitions.max(axis=2) < 0.55).mean())
    prototype_drift = float(np.abs(transitions[..., 0].mean() - transitions[..., 1].mean()))
    return {
        "ece": ece,
        "brier": brier,
        "abstain_rate": abstain_rate,
        "prototype_drift": prototype_drift,
    }


def train(config: AdaptiveConfig) -> Path:
    seed_everything(2025)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    emissions_dir = Path("data/processed/hmm/emissions")
    drivers_dir = Path("data/processed/hmm/drivers")
    emissions, drivers = load_inputs(emissions_dir, drivers_dir)

    model = AdaptiveTVTP(config.hidden_states)
    model.fit(emissions, drivers, config.max_iter, config.tol)
    transitions = model.predict_transition(drivers)
    calibration = compute_calibration(transitions)

    artifacts = {
        "config": asdict(config),
        "calibration": calibration,
        "transition_summary": transitions.mean(axis=0).tolist(),
    }
    artifact_path = config.output_dir / "tvtp_artifacts.json"
    artifact_path.write_text(json.dumps(artifacts, indent=2, ensure_ascii=False), encoding="utf-8")
    return artifact_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the adaptive TVTP-HSMM")
    parser.add_argument("--hidden-states", type=int, default=2)
    parser.add_argument("--max-iter", type=int, default=50)
    parser.add_argument("--tol", type=float, default=1e-4)
    parser.add_argument("--output-dir", type=Path, default=AdaptiveConfig.output_dir)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = AdaptiveConfig(
        hidden_states=args.hidden_states,
        max_iter=args.max_iter,
        tol=args.tol,
        output_dir=args.output_dir,
        calibration_targets={
            "prototype_drift": 0.15,
            "ece": 0.08,
            "brier": 0.18,
            "abstain_rate_low": 0.10,
            "abstain_rate_high": 0.25,
        },
    )
    artifact_path = train(config)
    print(f"artifacts saved to {artifact_path}")


if __name__ == "__main__":
    main()
