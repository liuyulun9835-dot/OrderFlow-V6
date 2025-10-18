from __future__ import annotations

import pandas as pd

from preprocessing import calibration


def _make_features(scale: float) -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-01", periods=20, freq="min", tz="UTC")
    df = pd.DataFrame({
        "timestamp": timestamps,
        "close": pd.Series(range(20), dtype=float) * scale + 1,
        "volume": pd.Series(range(1, 21), dtype=float) * scale,
    })
    return calibration.stratify(df)


def test_stratified_metrics_fail_when_distributions_diverge() -> None:
    reference = _make_features(1.0)
    target = _make_features(10.0)

    metrics = calibration.evaluate_strata(reference, target)
    assert metrics, "Expected metrics to be generated"
    assert any(metric.status() == "FAIL" for metric in metrics)
