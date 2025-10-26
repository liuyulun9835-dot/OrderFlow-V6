# [MIGRATED_FROM_V6] 2025-10-26: 原路径 v6_legacy/validation/src/validate_outputs.py；本文件在 V7 中保持向后兼容
"""Validate output artifacts contain schema signatures."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

def _ensure_v6_legacy() -> Path | None:
    import sys

    root = next((p for p in Path(__file__).resolve().parents if (p / "third_party").exists()), None)
    if root and str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from third_party.legacy_bootstrap import ensure_v6_legacy

    return ensure_v6_legacy()


_LEGACY_ROOT = _ensure_v6_legacy()

from v6_legacy.core.seeding import seed_all

REQUIRED_KEYS = {"schema_version", "build_id", "data_manifest_hash", "calibration_hash"}


@dataclass
class ValidationResult:
    path: Path
    metadata: dict

    def is_valid(self) -> bool:
        return REQUIRED_KEYS.issubset(self.metadata.keys())


def load_metadata(path: Path) -> dict | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def check_artifact(artifact: Path) -> ValidationResult | None:
    metadata_path = artifact.with_suffix(artifact.suffix + ".meta.json")
    metadata = load_metadata(metadata_path)
    if metadata is None:
        return None
    return ValidationResult(path=metadata_path, metadata=metadata)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate output signatures")
    parser.add_argument(
        "--artifacts",
        nargs="*",
        type=Path,
        default=[
            Path("output/results/OF_V6_stats.xlsx"),
            Path("output/results/combo_matrix.parquet"),
            Path("output/results/white_black_list.json"),
            Path("output/results/report.md"),
        ],
    )
    parser.add_argument("--log", type=Path, default=Path("output/results/validate_outputs.log"))
    args = parser.parse_args(list(argv) if argv is not None else None)

    seed_all()
    all_valid = True
    log_lines = []
    for artifact in args.artifacts:
        result = check_artifact(artifact)
        if result is None or not result.is_valid():
            print(f"Missing or invalid signature for {artifact}")
            log_lines.append(f"{artifact}: FAIL")
            all_valid = False
        else:
            print(f"Signature OK: {artifact} -> {result.metadata}")
            log_lines.append(f"{artifact}: PASS")

    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text("\n".join(log_lines), encoding="utf-8")

    return 0 if all_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

