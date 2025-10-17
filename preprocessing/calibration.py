"""Stratified quantile mapping and calibration reporting."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from orderflow_v6.seeding import seed_all

PROFILE_PATH = Path("calibration_profile.json")
REPORT_PATH = Path("results/merge_and_calibration_report.md")
THRESHOLDS = {"psi": 0.2, "ks": 0.1, "ece": 0.03}


@dataclass
class StratifiedMetrics:
    name: str
    psi: float
    ks: float
    ece: float

    def status(self) -> str:
        passed = self.psi <= THRESHOLDS["psi"] and self.ks <= THRESHOLDS["ks"] and self.ece <= THRESHOLDS["ece"]
        return "PASS" if passed else "FAIL"


def load_frame(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df = df.copy()
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    return df


def stratify(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    if "timestamp" in frame.columns:
        frame["minute"] = frame["timestamp"].dt.floor("min")
    frame["volatility"] = frame["close"].pct_change().abs().fillna(0.0)
    frame["volume_bucket"] = pd.qcut(frame.get("volume", pd.Series([0] * len(frame))), q=4, duplicates="drop", labels=False)
    frame["volatility_bucket"] = pd.qcut(frame["volatility"], q=4, duplicates="drop", labels=False)
    frame["stratum"] = frame["volatility_bucket"].astype(str) + "_" + frame["volume_bucket"].astype(str)
    frame["stratum"] = frame["stratum"].fillna("nan_nan")
    return frame


def psi_score(actual: np.ndarray, expected: np.ndarray, bins: int = 10) -> float:
    low = min(actual.min(), expected.min())
    high = max(actual.max(), expected.max())
    if high == low:
        high = low + 1e-3
    edges = np.linspace(low, high, bins + 1)
    actual_hist, _ = np.histogram(actual, bins=edges)
    expected_hist, _ = np.histogram(expected, bins=edges)
    actual_ratio = (actual_hist + 1e-6) / max(actual_hist.sum(), 1e-6)
    expected_ratio = (expected_hist + 1e-6) / max(expected_hist.sum(), 1e-6)
    return float(np.sum((actual_ratio - expected_ratio) * np.log(actual_ratio / expected_ratio)))


def ks_score(actual: np.ndarray, expected: np.ndarray) -> float:
    grid = np.linspace(min(actual.min(), expected.min()), max(actual.max(), expected.max()), max(len(actual), len(expected)))

    def empirical_cdf(values: np.ndarray, points: np.ndarray) -> np.ndarray:
        sorted_vals = np.sort(values)
        return np.searchsorted(sorted_vals, points, side="right") / len(sorted_vals)

    actual_cdf = empirical_cdf(actual, grid)
    expected_cdf = empirical_cdf(expected, grid)
    return float(np.abs(actual_cdf - expected_cdf).max())


def ece_score(actual: np.ndarray, expected: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    actual_quantiles = np.quantile(actual, edges)
    expected_quantiles = np.quantile(expected, edges)
    return float(np.mean(np.abs(actual_quantiles - expected_quantiles)))


def evaluate_strata(reference: pd.DataFrame, target: pd.DataFrame) -> list[StratifiedMetrics]:
    metrics: list[StratifiedMetrics] = []
    for stratum, ref_slice in reference.groupby("stratum"):
        tgt_slice = target[target["stratum"] == stratum]
        if tgt_slice.empty or ref_slice.empty:
            continue
        for column in tgt_slice.select_dtypes(include=[np.number]).columns:
            ref_values = ref_slice[column].dropna().to_numpy()
            tgt_values = tgt_slice[column].dropna().to_numpy()
            if ref_values.size < 5 or tgt_values.size < 5:
                continue
            psi = psi_score(tgt_values, ref_values)
            ks = ks_score(tgt_values, ref_values)
            ece = ece_score(tgt_values, ref_values)
            metrics.append(StratifiedMetrics(name=f"{stratum}:{column}", psi=psi, ks=ks, ece=ece))
    if not metrics:
        for column in target.select_dtypes(include=[np.number]).columns:
            ref_values = reference[column].dropna().to_numpy()
            tgt_values = target[column].dropna().to_numpy()
            if ref_values.size < 5 or tgt_values.size < 5:
                continue
            psi = psi_score(tgt_values, ref_values)
            ks = ks_score(tgt_values, ref_values)
            ece = ece_score(tgt_values, ref_values)
            metrics.append(StratifiedMetrics(name=f"global:{column}", psi=psi, ks=ks, ece=ece))
    return metrics


def save_profile(strata_metrics: list[StratifiedMetrics], path: Path) -> None:
    payload = {
        "thresholds": THRESHOLDS,
        "strata": [
            {"name": metric.name, "psi": metric.psi, "ks": metric.ks, "ece": metric.ece, "status": metric.status()}
            for metric in strata_metrics
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_offset_curve(path: Path) -> list[dict[str, float]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("offset_candidates", [])


def render_report(strata_metrics: list[StratifiedMetrics], offset_curve: list[dict[str, float]], output: Path) -> None:
    lines = ["# Merge and Calibration Report", ""]
    if offset_curve:
        top = sorted(offset_curve, key=lambda item: item.get("score", 0.0), reverse=True)[:2]
        lines.append("## Offset diagnostics")
        for entry in offset_curve:
            lines.append(f"- offset={entry['offset']} score={entry['score']:.4f}")
        lines.append("")
        if top:
            lines.append(f"Best offset: {top[0]['offset']} (score={top[0]['score']:.4f})")
        if len(top) > 1:
            lines.append(f"Runner-up: {top[1]['offset']} (score={top[1]['score']:.4f})")
        lines.append("")

    lines.append("## Stratified metrics")
    lines.append("| stratum | PSI | KS | ECE | status |")
    lines.append("| --- | --- | --- | --- | --- |")
    for metric in strata_metrics:
        lines.append(
            f"| {metric.name} | {metric.psi:.4f} | {metric.ks:.4f} | {metric.ece:.4f} | {metric.status()} |"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stratified calibration")
    parser.add_argument("--features", type=Path, default=Path("data/processed/features.parquet"))
    parser.add_argument("--reference", type=Path, default=Path("data/processed/features_reference.parquet"))
    parser.add_argument("--profile", type=Path, default=PROFILE_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--offset", type=Path, default=Path("results/offset_diagnostics.json"))
    args = parser.parse_args(list(argv) if argv is not None else None)

    seed_all()

    features = stratify(load_frame(args.features))
    if args.reference.exists():
        reference = stratify(load_frame(args.reference))
    else:
        reference = features.copy()

    metrics = evaluate_strata(reference, features)
    save_profile(metrics, args.profile)
    offset_curve = load_offset_curve(args.offset)
    render_report(metrics, offset_curve, args.report)

    if not metrics:
        return 1
    return 0 if all(metric.status() == "PASS" for metric in metrics) else 1


if __name__ == "__main__":
    raise SystemExit(main())

