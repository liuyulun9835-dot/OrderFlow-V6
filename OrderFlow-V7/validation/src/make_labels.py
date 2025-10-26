# [MIGRATED_FROM_V6] 2025-10-26: 原路径 v6_legacy/validation/src/make_labels.py；本文件在 V7 中保持向后兼容
"""Generate labels with right-closed windows and downgrade logic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml


def _ensure_v6_legacy() -> Path | None:
    import sys

    root = next((p for p in Path(__file__).resolve().parents if (p / "third_party").exists()), None)
    if root and str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from third_party.legacy_bootstrap import ensure_v6_legacy

    return ensure_v6_legacy()


_LEGACY_ROOT = _ensure_v6_legacy()
LEGACY_CONFIG_ROOT = (
    Path(_LEGACY_ROOT)
    if _LEGACY_ROOT is not None
    else Path(__file__).resolve().parents[2] / "third_party" / "v6_legacy"
)

from v6_legacy.core.seeding import seed_all


def load_features(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").set_index("timestamp")
    return df


def compute_labels(features: pd.DataFrame, lookahead: int) -> pd.DataFrame:
    forward = features["close"].shift(-lookahead)
    returns = (forward - features["close"]) / features["close"]
    labels = pd.DataFrame({"label": returns})
    labels = labels.dropna().reset_index()
    labels.rename(columns={"index": "timestamp"}, inplace=True)
    return labels


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def determine_priority(features: pd.DataFrame, config: dict) -> tuple[str, dict]:
    sources = config.get("sources", [])
    if not sources:
        return "unknown", {}
    primary = sources[0]
    degrade_target = primary.get("degrade_to", primary.get("fallback", "bar"))
    rules = primary.get("degrade_rules", {})

    tick_volume = features.get("tick_volume")
    missing_rate = float(tick_volume.isna().mean()) if tick_volume is not None else 1.0
    threshold = float(rules.get("tick_gap_threshold", 0.05))
    calibration_flag = bool(features.get("calibration_breach", pd.Series([False] * len(features))).any())

    degrade = missing_rate > threshold or calibration_flag
    priority = degrade_target if degrade else primary["name"]
    audit = {
        "primary": primary["name"],
        "degrade": degrade,
        "missing_rate": missing_rate,
        "threshold": threshold,
        "calibration_breach": calibration_flag,
        "embargo_bars": primary.get("embargo_bars", 0),
        "purge_kfold": primary.get("purge_kfold", 0),
        "fallback": degrade_target,
    }
    return priority, audit


def write_metadata(labels: pd.DataFrame, path: Path, metadata: dict) -> None:
    table = pa.Table.from_pandas(labels, preserve_index=False)
    existing = table.schema.metadata or {}
    merged = {**existing, **{key.encode(): json.dumps(value).encode() for key, value in metadata.items()}}
    table = table.replace_schema_metadata(merged)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def log_downgrade(audit: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit) + "\n")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate labels with downgrade logic")
    parser.add_argument("--features", type=Path, default=Path("data/processed/features.parquet"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/labels.parquet"))
    parser.add_argument(
        "--config",
        type=Path,
        default=LEGACY_CONFIG_ROOT / "validation" / "configs" / "priority_downgrade.yaml",
    )
    parser.add_argument("--lookahead", type=int, default=1)
    parser.add_argument("--label-lag", type=int, default=1)
    parser.add_argument("--log", type=Path, default=Path("logs/priority_downgrade.log"))
    args = parser.parse_args(list(argv) if argv is not None else None)

    seed_all()

    features = load_features(args.features)
    labels = compute_labels(features, args.lookahead)
    config = load_config(args.config)
    priority_source, audit = determine_priority(features, config)

    metadata = {
        "label_lag": args.label_lag,
        "lookahead": args.lookahead,
        "priority_source": priority_source,
        "embargo_bars": audit.get("embargo_bars", 0),
        "purge_kfold": audit.get("purge_kfold", 0),
    }

    write_metadata(labels, args.output, metadata)
    audit.update({"priority_source": priority_source})
    log_downgrade(audit, args.log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

