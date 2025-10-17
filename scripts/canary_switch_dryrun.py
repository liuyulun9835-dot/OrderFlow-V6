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
    strata = profile.get("strata", [])
    if not strata:
        return {"max_ece": float("inf"), "max_psi": float("inf")}
    return {
        "max_ece": max(item.get("ece", 0.0) for item in strata),
        "max_psi": max(item.get("psi", 0.0) for item in strata),
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


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate canary switch policy without executing")
    parser.add_argument("--policy", type=Path, default=Path("execution/switch_policy.yaml"))
    parser.add_argument("--bar", type=Path, default=Path("results/bar_continuity_report.json"))
    parser.add_argument("--tick", type=Path, default=Path("results/tick_quality_report.json"))
    parser.add_argument("--calibration", type=Path, default=Path("calibration_profile.json"))
    parser.add_argument("--costs", type=Path, default=Path("results/precheck_costs_report.json"))
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(list(argv) if argv is not None else None)

    seed_all()
    policy = yaml.safe_load(args.policy.read_text(encoding="utf-8"))
    bar_metrics = load_json(args.bar)
    tick_metrics = load_json(args.tick)
    calibration_profile = load_json(args.calibration)
    cost_metrics = load_json(args.costs)
    calibration_summary = summarise_calibration(calibration_profile)

    requirements = policy.get("preconditions", {})
    results = {
        "bar_continuity": bar_metrics,
        "tick_quality": tick_metrics,
        "calibration": calibration_summary,
        "cost_gate": cost_metrics.get("status"),
    }

    render_report(results, policy, args.output)

    bar_ok = bar_metrics.get("continuity_ratio", 0.0) >= requirements.get("bar_continuity_min", 0.0)
    tick_ok = tick_metrics.get("continuity_ratio", 0.0) >= requirements.get("tick_continuity_min", 0.0)
    ece_ok = calibration_summary.get("max_ece", float("inf")) <= requirements.get("ece_max", float("inf"))
    cost_ok = cost_metrics.get("status") == "PASS" if requirements.get("cost_gate_required", False) else True

    psi_ok = calibration_summary.get("max_psi", float("inf")) <= requirements.get("psi_max", float("inf"))

    ready = bar_ok and tick_ok and ece_ok and cost_ok and psi_ok
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())

