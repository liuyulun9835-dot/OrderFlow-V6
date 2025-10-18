from __future__ import annotations

from pathlib import Path

import yaml

from validation.src import precheck_costs


def test_gate_rejects_negative_net(tmp_path: Path) -> None:
    config_path = tmp_path / "costs.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "scenarios": {
                    "base": {"expected_revenue": 1.0, "estimated_cost": 1.0},
                    "plus_50": {"expected_revenue": 1.2, "estimated_cost": 1.5},
                    "times_2": {"expected_revenue": 2.0, "estimated_cost": 2.5},
                }
            }
        ),
        encoding="utf-8",
    )

    config = precheck_costs.load_config(config_path)
    scenarios = precheck_costs.evaluate(config)
    assert not precheck_costs.gate_passed(scenarios)
