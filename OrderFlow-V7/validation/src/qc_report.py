#!/usr/bin/env python3
# [MIGRATED_FROM_V6] 2025-10-26: 原路径 v6_legacy/validation/src/qc_report.py；本文件在 V7 中保持向后兼容
"""Generate a markdown quality-control report for processed feature data."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import pandas as pd


def _ensure_v6_legacy() -> Path | None:
    import sys

    root = next((p for p in Path(__file__).resolve().parents if (p / "third_party").exists()), None)
    if root and str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from third_party.legacy_bootstrap import ensure_v6_legacy

    return ensure_v6_legacy()


_LEGACY_ROOT = _ensure_v6_legacy()

from v6_legacy.core.seeding import seed_all


DEFAULT_FEATURES_PATH = Path("data/processed/features.parquet")
DEFAULT_REPORT_PATH = Path("output/qa/data_qc_report.md")
EXPECTED_FREQ = pd.Timedelta(minutes=1)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate QC report for features.parquet")
    parser.add_argument("--input", type=Path, default=DEFAULT_FEATURES_PATH, help="Path to features parquet file")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH, help="Output markdown report path")
    return parser.parse_args()


def _load_features(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Features parquet not found: {path}")
    df = pd.read_parquet(path)
    if "timestamp" not in df.columns:
        raise ValueError("Features parquet must include a 'timestamp' column")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def _missing_stats(df: pd.DataFrame) -> pd.DataFrame:
    missing_pct = df.isna().mean() * 100
    return missing_pct.to_frame(name="missing_pct").round(4)


def _outlier_stats(df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = df.select_dtypes(include=["number"]).columns
    rows: List[dict] = []
    for col in numeric_cols:
        series = df[col].dropna()
        if series.empty:
            rows.append({"feature": col, "count": 0})
            continue
        mean = series.mean()
        std = series.std(ddof=0)
        if std == 0:
            rows.append({"feature": col, "count": 0})
            continue
        mask = (series > mean + 3 * std) | (series < mean - 3 * std)
        rows.append({"feature": col, "count": int(mask.sum())})
    return pd.DataFrame(rows)


def _time_jump_stats(df: pd.DataFrame) -> pd.DataFrame:
    timestamps = df["timestamp"].dropna().sort_values()
    diffs = timestamps.diff().dropna()
    jumps = diffs[diffs > EXPECTED_FREQ]
    if jumps.empty:
        return pd.DataFrame([[0, 0]], columns=["jump_events", "missing_minutes"])
    missing_minutes = (jumps / EXPECTED_FREQ - 1).round().astype(int)
    return pd.DataFrame([[len(jumps), int(missing_minutes.sum())]], columns=["jump_events", "missing_minutes"])


def _duplicate_stats(df: pd.DataFrame) -> pd.DataFrame:
    duplicate_rows = int(df.duplicated().sum())
    duplicate_timestamps = int(df["timestamp"].duplicated().sum())
    return pd.DataFrame(
        [[duplicate_rows, duplicate_timestamps]],
        columns=["duplicate_rows", "duplicate_timestamps"],
    )


def _to_markdown_safe(df: pd.DataFrame, **kwargs) -> str:
    try:
        return df.to_markdown(**kwargs)
    except Exception:
        return "```\n" + df.to_string(**kwargs) + "\n```"


def main() -> None:
    args = _parse_args()
    df = _load_features(args.input)

    missing_df = _missing_stats(df)
    outlier_df = _outlier_stats(df)
    jumps_df = _time_jump_stats(df)
    duplicate_df = _duplicate_stats(df)

    report_lines: List[str] = ["# Data Quality Report", ""]

    report_lines.extend(["## Missing Values", _to_markdown_safe(missing_df), ""])
    report_lines.extend(["## 3σ Outliers", _to_markdown_safe(outlier_df, index=False), ""])
    report_lines.extend(["## Time Continuity", _to_markdown_safe(jumps_df, index=False), ""])
    report_lines.extend(["## Duplicate Checks", _to_markdown_safe(duplicate_df, index=False), ""])

    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(report_lines))


if __name__ == "__main__":
    main()
