"""Univariate statistical utilities with FDR control and effect sizes."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Sequence

import numpy as np


@dataclass
class UnivariateTestResult:
    name: str
    p_value: float
    effect_size: float
    rejected: bool


def _summary_stats(sample: Sequence[float]) -> dict[str, float]:
    array = np.asarray(sample, dtype=float)
    if array.size == 0:
        return {"n": 0, "mean": float("nan"), "std": float("nan")}
    return {
        "n": int(array.size),
        "mean": float(np.nanmean(array)),
        "std": float(np.nanstd(array)),
    }


def directional_breakdown(bull_sample: Sequence[float], bear_sample: Sequence[float]) -> dict[str, dict[str, float]]:
    """Compute bull/bear descriptive statistics for validator reporting.

    WHY: README and governance documents require directionally stratified validation.
    This helper keeps the logic close to other univariate utilities.
    """

    return {"bull": _summary_stats(bull_sample), "bear": _summary_stats(bear_sample)}


def cohen_d(sample_a: Sequence[float], sample_b: Sequence[float]) -> float:
    a = np.asarray(sample_a, dtype=float)
    b = np.asarray(sample_b, dtype=float)
    mean_diff = a.mean() - b.mean()
    pooled = math.sqrt(((a.size - 1) * a.var(ddof=1) + (b.size - 1) * b.var(ddof=1)) / (a.size + b.size - 2))
    return mean_diff / pooled if pooled else 0.0


def fdr_bh(p_values: Iterable[float], alpha: float = 0.05) -> List[bool]:
    values = np.asarray(list(p_values), dtype=float)
    order = values.argsort()
    ranked = values[order]
    threshold = alpha * (np.arange(len(ranked)) + 1) / len(ranked)
    passed = ranked <= threshold
    rejected = np.zeros_like(passed, dtype=bool)
    if passed.any():
        max_idx = np.where(passed)[0].max()
        rejected[: max_idx + 1] = True
    result = np.zeros_like(rejected)
    result[order] = rejected
    return result.tolist()


def evaluate_tests(names: Sequence[str], p_values: Sequence[float], effects: Sequence[float], alpha: float = 0.05) -> List[UnivariateTestResult]:
    rejected = fdr_bh(p_values, alpha)
    return [
        UnivariateTestResult(name=name, p_value=p, effect_size=effect, rejected=rej)
        for name, p, effect, rej in zip(names, p_values, effects, rejected)
    ]


__all__ = ["UnivariateTestResult", "cohen_d", "fdr_bh", "evaluate_tests", "directional_breakdown"]

