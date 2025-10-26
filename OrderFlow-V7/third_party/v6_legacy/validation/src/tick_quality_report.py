"""Tick quality report with arrival statistics."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from v6_legacy.core.seeding import seed_all

RESULT_PATH = Path("output/qa/tick_quality_report.md")


@dataclass
class TickMetrics:
    coverage: float
    continuity_ratio: float
    cv: float
    p99: float
    median: float

    def gate_passed(self) -> bool:
        return (
            self.continuity_ratio >= 0.999
            and self.cv <= 1.5
            and self.p99 <= 3 * self.median
        )


def load_ticks(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def compute_metrics(df: pd.DataFrame) -> TickMetrics:
    if df.empty:
        return TickMetrics(0.0, 0.0, float("inf"), float("inf"), float("inf"))

    expected = int((df["timestamp"].max() - df["timestamp"].min()).total_seconds()) + 1
    continuity_ratio = len(df) / max(expected, 1)

    diffs = df["timestamp"].diff().dropna().dt.total_seconds()
    if diffs.empty:
        cv = 0.0
        p99 = 0.0
        median = 0.0
    else:
        median = float(diffs.median())
        std = float(diffs.std(ddof=0))
        mean = float(diffs.mean())
        cv = std / mean if mean else float("inf")
        p99 = float(diffs.quantile(0.99))

    coverage = df.notna().mean().mean()
    return TickMetrics(coverage, continuity_ratio, cv, p99, median)


def render_markdown(metrics: TickMetrics, output: Path) -> None:
    status = "PASS" if metrics.gate_passed() else "FAIL"
    lines = [
        "# Tick Quality Report",
        f"Status: **{status}**",
        "",
        "| metric | value | threshold |",
        "| --- | --- | --- |",
        f"| Coverage | {metrics.coverage:.4f} | - |",
        f"| Continuity | {metrics.continuity_ratio:.4f} | >= 0.999 |",
        f"| CV | {metrics.cv:.4f} | <= 1.5 |",
        f"| p99 | {metrics.p99:.4f}s | <= 3×median |",
        f"| median | {metrics.median:.4f}s | - |",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def save_json(metrics: TickMetrics, path: Path) -> None:
    payload = {
        "coverage": metrics.coverage,
        "continuity_ratio": metrics.continuity_ratio,
        "cv": metrics.cv,
        "p99": metrics.p99,
        "median": metrics.median,
        "status": "PASS" if metrics.gate_passed() else "FAIL",
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate tick quality report")
    parser.add_argument("--input", type=Path, default=Path("data/raw/atas/tick/example_symbol.parquet"))
    parser.add_argument("--output", type=Path, default=RESULT_PATH)
    parser.add_argument("--json", type=Path, default=Path("output/qa/tick_quality_report.json"))
    args = parser.parse_args(list(argv) if argv is not None else None)

    seed_all()
    df = load_ticks(args.input)
    metrics = compute_metrics(df)
    render_markdown(metrics, args.output)
    save_json(metrics, args.json)
    return 0 if metrics.gate_passed() else 1


if __name__ == "__main__":
    raise SystemExit(main())

