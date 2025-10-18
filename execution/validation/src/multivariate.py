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


__all__ = ["MultivariateTestResult", "max_t_threshold", "evaluate_max_t"]

