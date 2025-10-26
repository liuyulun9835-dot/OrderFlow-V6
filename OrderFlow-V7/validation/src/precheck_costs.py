# [MIGRATED_FROM_V6] 2025-10-26: 原路径 orderflow_v_6/validation/src/precheck_costs.py；本文件在 V7 中保持向后兼容
"""Cost robustness gate prior to validator execution."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from orderflow_v_6.core.seeding import seed_all

RESULT_PATH = Path("output/qa/cost_sensitivity.md")
JSON_PATH = Path("output/qa/precheck_costs_report.json")


@dataclass
class ScenarioResult:
    name: str
    revenue: float
    cost: float

    @property
    def net(self) -> float:
        return self.revenue - self.cost


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def evaluate(config: dict) -> list[ScenarioResult]:
    scenarios = []
    for name, payload in config.get("scenarios", {}).items():
        scenarios.append(
            ScenarioResult(
                name=name,
                revenue=float(payload.get("expected_revenue", 0.0)),
                cost=float(payload.get("estimated_cost", 0.0)),
            )
        )
    return scenarios


def render_report(scenarios: list[ScenarioResult], output: Path) -> None:
    lines = [
        "# Cost Precheck",
        "",
        "| scenario | revenue | cost | net |",
        "| --- | --- | --- | --- |",
    ]
    for scenario in scenarios:
        lines.append(
            f"| {scenario.name} | {scenario.revenue:.4f} | {scenario.cost:.4f} | {scenario.net:.4f} |"
        )

    base = next((s for s in scenarios if s.name == "base"), None)
    if base is not None:
        sensitivity = base.net - 1.5 * base.cost
        lines.append("")
        lines.append(f"Base margin - 1.5×cost: {sensitivity:.4f}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def gate_passed(scenarios: list[ScenarioResult]) -> bool:
    if not scenarios:
        return False
    for scenario in scenarios:
        if scenario.net < 0:
            return False
    base = next((s for s in scenarios if s.name == "base"), None)
    if base is None:
        return False
    return base.net >= 1.5 * base.cost


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cost precheck gate")
    parser.add_argument("--config", type=Path, default=Path("orderflow_v_6/validation/configs/costs.yaml"))
    parser.add_argument("--output", type=Path, default=RESULT_PATH)
    parser.add_argument("--json", type=Path, default=JSON_PATH)
    args = parser.parse_args(list(argv) if argv is not None else None)

    seed_all()
    config = load_config(args.config)
    scenarios = evaluate(config)
    render_report(scenarios, args.output)
    args.json.write_text(
        json.dumps(
            {
                "scenarios": [
                    {"name": s.name, "revenue": s.revenue, "cost": s.cost, "net": s.net}
                    for s in scenarios
                ],
                "status": "PASS" if gate_passed(scenarios) else "FAIL",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0 if gate_passed(scenarios) else 1


if __name__ == "__main__":
    raise SystemExit(main())

