from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from data.preprocessing import fetch_kline


def test_parse_date_supports_iso() -> None:
    dt_plain = fetch_kline.parse_date("since", "2024-01-02")
    dt_iso = fetch_kline.parse_date("since", "2024-01-02T12:00:00+00:00")
    assert dt_plain.tzinfo == timezone.utc
    assert dt_iso.tzinfo == timezone.utc
    assert dt_iso.hour == 12


def test_save_parquet_deduplicates(tmp_path: Path) -> None:
    base = pd.DataFrame(
        {
            "timestamp": [datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc), datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc)],
            "open": [10, 11],
            "high": [11, 12],
            "low": [9, 10],
            "close": [10.5, 11.5],
            "volume": [100, 120],
        }
    )

    path = tmp_path / "kline.parquet"
    fetch_kline.save_parquet(base, path, append=False)

    overlap = pd.DataFrame(
        {
            "timestamp": [datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, 0, 2, tzinfo=timezone.utc)],
            "open": [11.1, 12],
            "high": [12, 13],
            "low": [10.8, 11.9],
            "close": [11.2, 12.5],
            "volume": [130, 140],
        }
    )

    fetch_kline.save_parquet(overlap, path, append=True)

    combined = fetch_kline.ensure_timestamp_column(pd.read_parquet(path))
    assert len(combined) == 3
    assert combined["timestamp"].is_monotonic_increasing
    assert combined.loc[2, "close"] == 12.5
