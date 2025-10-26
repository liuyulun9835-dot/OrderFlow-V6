# [MIGRATED_FROM_V6] 2025-10-26: 原路径 v6_legacy/validation/src/multivariate.py；本文件在 V7 中保持向后兼容
"""Multivariate test helpers with max-T style correction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

import numpy as np


@dataclass
class MultivariateTestResult:
    name: str
    statistic: float
    threshold: float
    rejected: bool


def directional_covariance(bull_vectors: Sequence[Sequence[float]], bear_vectors: Sequence[Sequence[float]]) -> dict[str, list[list[float]]]:
    """Compute covariance matrices for bull/bear segments.

    WHY: Governance requires reporting multivariate dispersion conditioned on direction.
    """

    def cov(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
        arr = np.asarray(matrix, dtype=float)
        if arr.size == 0:
            return []
        return np.cov(arr, rowvar=False).tolist()

    return {"bull": cov(bull_vectors), "bear": cov(bear_vectors)}


def max_t_threshold(statistics: Sequence[float], simulations: Iterable[Sequence[float]], alpha: float = 0.05) -> float:
    maxima = []
    for sample in simulations:
        maxima.append(np.max(np.abs(sample)))
    if not maxima:
        return float("inf")
    return float(np.quantile(maxima, 1 - alpha))


def evaluate_max_t(names: Sequence[str], statistics: Sequence[float], simulations: Iterable[Sequence[float]], alpha: float = 0.05) -> List[MultivariateTestResult]:
    threshold = max_t_threshold(statistics, simulations, alpha)
    results = []
    for name, stat in zip(names, statistics):
        results.append(
            MultivariateTestResult(
                name=name,
                statistic=float(stat),
                threshold=threshold,
                rejected=abs(stat) > threshold,
            )
        )
    return results


__all__ = ["MultivariateTestResult", "max_t_threshold", "evaluate_max_t", "directional_covariance"]

