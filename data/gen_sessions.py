#!/usr/bin/env python3
"""Generate trading sessions calendar."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Set

import pandas as pd

try:  # Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - fallback
    from backports.zoneinfo import ZoneInfo  # type: ignore


ASIA_END = 8  # 00:00-07:59
EU_END = 16   # 08:00-15:59


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a sessions.csv file.")
    parser.add_argument("start", nargs="?", help="Start datetime (e.g. 2023-01-01 or 2023-01-01T00:00:00)")
    parser.add_argument("end", nargs="?", help="End datetime inclusive (same format as start)")
    parser.add_argument("timezone", nargs="?", help="Exchange timezone, e.g. UTC or Asia/Shanghai")
    parser.add_argument(
        "--market",
        choices=["crypto", "stock"],
        help="Market preset. crypto -> UTC timezone & ignore holidays",
    )
    parser.add_argument(
        "--holidays",
        help="Optional path to a holiday calendar file (csv/json/txt) containing dates to exclude.",
    )
    parser.add_argument(
        "--output",
        default="data/meta/sessions.csv",
        help="Where to save the generated CSV (default: data/meta/sessions.csv)",
    )
    args = parser.parse_args()

    if not args.start or not args.end:
        parser.error("start and end are required")

    timezone = args.timezone
    if args.market == "crypto":
        timezone = "UTC"
        args.holidays = None
    elif timezone is None:
        parser.error("timezone is required unless --market=crypto")

    args.timezone = timezone
    return args


def _ensure_timezone(ts: pd.Timestamp, tz: ZoneInfo) -> pd.Timestamp:
    if ts.tzinfo is None:
        return ts.tz_localize(tz)
    return ts.tz_convert(tz)


def _load_holidays(path: Path) -> Set[pd.Timestamp]:
    if not path.exists():
        raise FileNotFoundError(f"Holiday file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            dates = data.values()
        else:
            dates = data
        holiday_dates = {pd.to_datetime(d).normalize() for d in dates}
    elif suffix in {".csv", ".txt", ".dat"}:
        df = pd.read_csv(path)
        if df.empty:
            return set()
        if "date" in df.columns:
            dates_iter: Iterable = df["date"].tolist()
        else:
            dates_iter = df.iloc[:, 0].tolist()
        holiday_dates = {pd.to_datetime(d).normalize() for d in dates_iter}
    else:  # generic fallback
        dates_iter = [line.strip() for line in path.read_text().splitlines() if line.strip()]
        holiday_dates = {pd.to_datetime(d).normalize() for d in dates_iter}
    return holiday_dates


def _label_session(ts_utc: pd.Timestamp, tz: ZoneInfo) -> str:
    ts_local = ts_utc.tz_convert(tz)
    hour = ts_local.hour
    if hour < ASIA_END:
        return "asia"
    if hour < EU_END:
        return "eu"
    return "us"


def main() -> None:
    args = _parse_args()
    tz = ZoneInfo(args.timezone)

    start_ts = pd.Timestamp(args.start)
    end_ts = pd.Timestamp(args.end)
    if end_ts < start_ts:
        raise ValueError("End datetime must be after start datetime")

    start_local = _ensure_timezone(start_ts, tz)
    end_local = _ensure_timezone(end_ts, tz)

    idx = pd.date_range(start=start_local.tz_convert("UTC"), end=end_local.tz_convert("UTC"), freq="min")

    holidays: Set[pd.Timestamp] = set()
    if args.holidays:
        holidays = _load_holidays(Path(args.holidays))

    df = pd.DataFrame(index=idx)
    df.index.name = "timestamp"

    if holidays:
        local_index = df.index.tz_convert(tz)
        mask = ~local_index.normalize().isin(holidays)
        df = df.loc[mask]

    df["session_id"] = [
        _label_session(ts_utc, tz) for ts_utc in df.index
    ]

    df.reset_index(inplace=True)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)


if __name__ == "__main__":
    main()
