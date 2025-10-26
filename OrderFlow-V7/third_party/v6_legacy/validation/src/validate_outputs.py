"""Validate output artifacts contain schema signatures."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

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

