"""Dry-run canary switch evaluation based on policy constraints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import yaml

from orderflow_v6.seeding import seed_all

DEFAULT_REPORT = Path("results/canary_switch_dryrun.md")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def summarise_calibration(profile: dict) -> dict:
    if not profile:
        return {"max_ece": None, "max_psi": None, "max_ks_stat": None}

    psi_values: list[float] = []
    ks_values: list[float] = []
    ece_values: list[float] = []

    for key, bucket in (
        ("psi_max_observed", psi_values),
        ("ks_stat_max_observed", ks_values),
        ("ece_max_observed", ece_values),
    ):
        value = profile.get(key)
        if isinstance(value, (int, float)):
            bucket.append(float(value))

    layers = profile.get("layers", [])
    for layer in layers:
        summaries = layer.get("metric_summaries", {})
        psi = summaries.get("psi")
        if isinstance(psi, (int, float)):
            psi_values.append(float(psi))
        ks_stat = summaries.get("ks_stat")
        if isinstance(ks_stat, (int, float)):
            ks_values.append(float(ks_stat))
        ece = summaries.get("ece")
        if isinstance(ece, (int, float)):
            ece_values.append(float(ece))

        for segment in layer.get("segments", []):
            psi = segment.get("psi")
            if isinstance(psi, (int, float)):
                psi_values.append(float(psi))
            ks_stat = segment.get("ks_stat")
            if isinstance(ks_stat, (int, float)):
                ks_values.append(float(ks_stat))
            ece = segment.get("ece")
            if isinstance(ece, (int, float)):
                ece_values.append(float(ece))

    return {
        "max_ece": max(ece_values) if ece_values else None,
        "max_psi": max(psi_values) if psi_values else None,
        "max_ks_stat": max(ks_values) if ks_values else None,
    }


def render_report(results: dict, policy: dict, output: Path) -> None:
    lines = ["# Canary Switch Dry Run", ""]
    for key, value in results.items():
        lines.append(f"## {key}")
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                lines.append(f"- {sub_key}: {sub_value}")
        else:
            lines.append(f"- {value}")
        lines.append("")
    lines.append("## Policy Snapshot")
    lines.append("```yaml")
    lines.append(yaml.safe_dump(policy, sort_keys=False))
    lines.append("```")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def pf(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate canary switch policy without executing")
    parser.add_argument("--policy", type=Path, default=Path("execution/switch_policy.yaml"))
    parser.add_argument("--bar", type=Path, default=Path("results/bar_continuity_report.json"))
    parser.add_argument("--tick", type=Path, default=Path("results/tick_quality_report.json"))
    parser.add_argument("--calibration", type=Path, default=Path("results/calibration_profile.json"))
    parser.add_argument("--costs", type=Path, default=Path("results/precheck_costs_report.json"))
    parser.add_argument("--merge-metrics", type=Path, default=Path("results/merge_metrics.json"))
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(list(argv) if argv is not None else None)

    seed_all()
    policy = yaml.safe_load(args.policy.read_text(encoding="utf-8"))
    bar_metrics = load_json(args.bar)
    tick_metrics = load_json(args.tick)
    calibration_profile = load_json(args.calibration)
    if not calibration_profile and args.calibration != Path("calibration_profile.json"):
        legacy_profile = Path("calibration_profile.json")
        if legacy_profile.exists():
            calibration_profile = load_json(legacy_profile)
    cost_metrics = load_json(args.costs)
    merge_metrics = load_json(args.merge_metrics)
    calibration_summary = summarise_calibration(calibration_profile)

    requirements = policy.get("preconditions", {})
    results = {
        "bar_continuity": bar_metrics,
        "tick_quality": tick_metrics,
        "calibration": calibration_summary,
        "cost_gate": cost_metrics.get("status"),
        "merge_metrics": merge_metrics,
    }

    render_report(results, policy, args.output)

    bar_ok = bar_metrics.get("continuity_ratio", 0.0) >= requirements.get("bar_continuity_min", 0.0)
    tick_ok = tick_metrics.get("continuity_ratio", 0.0) >= requirements.get("tick_continuity_min", 0.0)
    ece_limit = requirements.get("ece_max")
    ece_observed = calibration_summary.get("max_ece")
    ece_ok = (ece_observed is not None) and (ece_limit is None or ece_observed <= ece_limit)
    cost_ok = cost_metrics.get("status") == "PASS" if requirements.get("cost_gate_required", False) else True

    psi_limit = requirements.get("psi_max")
    psi_observed = calibration_summary.get("max_psi")
    psi_ok = (psi_observed is not None) and (psi_limit is None or psi_observed <= psi_limit)

    mmr_limit = requirements.get("mismatch_rate_max")
    mmr_observed = merge_metrics.get("mismatch_rate") if merge_metrics else None
    mmr_ok = (mmr_observed is not None) and (mmr_limit is None or mmr_observed < mmr_limit)

    print(f"[Preconditions] PSI={psi_observed}  ≤ {psi_limit}  → {pf(psi_ok)}")
    print(f"[Preconditions] mismatch_rate={mmr_observed}  < {mmr_limit}  → {pf(mmr_ok)}")

    ready = bar_ok and tick_ok and ece_ok and cost_ok and psi_ok and mmr_ok
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())

