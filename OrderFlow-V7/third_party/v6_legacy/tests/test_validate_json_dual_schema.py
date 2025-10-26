from __future__ import annotations

import json
from pathlib import Path

import jsonschema


SCHEMA_PATH = Path("data/preprocessing/schemas/atas_schema.json")


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_accepts_flattened_absorption() -> None:
    schema = _load_schema()
    payload = {
        "timestamp": "2024-01-01T00:00:00Z",
        "open": 1.0,
        "high": 1.1,
        "low": 0.9,
        "close": 1.05,
        "volume": 100,
        "absorption_detected": True,
        "absorption_strength": 0.3,
        "absorption_side": "buy",
    }
    jsonschema.validate(payload, schema)


def test_schema_accepts_nested_absorption() -> None:
    schema = _load_schema()
    payload = {
        "timestamp": "2024-01-01T00:00:00Z",
        "open": 1.0,
        "high": 1.1,
        "low": 0.9,
        "close": 1.05,
        "volume": 100,
        "absorption": {"detected": True, "strength": 0.5, "side": "sell"},
        "window_id": "2024-01-01T00:00:00Z",
        "flush_seq": 1,
    }
    jsonschema.validate(payload, schema)
