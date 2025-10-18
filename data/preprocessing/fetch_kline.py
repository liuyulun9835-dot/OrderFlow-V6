#!/usr/bin/env python3
"""Fetch minute-level OHLCV data using CCXT and store it as parquet."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import ccxt  # type: ignore
import pandas as pd

from orderflow_v6.seeding import seed_all

def parse_timeframe(value: str) -> timedelta:
    value = value.strip().lower()
    units = {
        "m": 60,
        "h": 60 * 60,
        "d": 60 * 60 * 24,
    }
    for suffix, seconds in units.items():
        if value.endswith(suffix):
            amount = int(value[:-1])
            return timedelta(seconds=amount * seconds)
    if value.isdigit():
        return timedelta(minutes=int(value))
    raise ValueError(f"Unsupported timeframe: {value}")


def parse_date(label: str, raw: Optional[str]) -> Optional[datetime]:
    if raw is None:
        return None
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError as exc:  # noqa: TRY003
            raise ValueError(f"Invalid {label} format: {raw}") from exc
    return dt.replace(tzinfo=timezone.utc)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch OHLCV klines and persist as parquet")
    parser.add_argument("--symbol", required=True, help="Trading pair symbol, e.g. BTC/USDT")
    parser.add_argument("--since", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--until", help="End date inclusive (YYYY-MM-DD)")
    parser.add_argument("--exchange", default="binance", help="CCXT exchange id (default: binance)")
    parser.add_argument("--tf", default="1m", help="Timeframe (default: 1m)")
    parser.add_argument(
        "--output",
        help="Optional parquet output path. Defaults to data/exchange/<symbol>/kline_<tf>.parquet",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing parquet (auto-continue from the last timestamp + timeframe)",
    )
    args = parser.parse_args()

    timeframe = parse_timeframe(args.tf)
    since_dt = parse_date("since", args.since)
    until_dt = parse_date("until", args.until)

    if not args.append and (since_dt is None or until_dt is None):
        parser.error("--since and --until are required unless --append with existing file")

    args.timeframe = timeframe
    args.since_dt = since_dt
    args.until_dt = until_dt
    return args


def sanitise_symbol(symbol: str) -> str:
    return "".join(ch for ch in symbol if ch.isalnum())


def compute_fetch_bounds(args: argparse.Namespace, existing: Optional[pd.DataFrame]) -> tuple[int, int]:
    timeframe_ms = int(args.timeframe.total_seconds() * 1000)

    if args.append and existing is not None and not existing.empty:
        last_ts = existing["timestamp"].max()
        start_dt = (last_ts + args.timeframe).to_pydatetime()
        since_ms = int(start_dt.timestamp() * 1000)
    else:
        if args.since_dt is None:
            raise ValueError("--since is required when no existing data is present")
        since_ms = int(args.since_dt.timestamp() * 1000)

    end_dt = args.until_dt
    if end_dt is None:
        end_dt = datetime.now(tz=timezone.utc)
    end_exclusive = end_dt + timedelta(days=1)
    until_ms = int(end_exclusive.timestamp() * 1000) - timeframe_ms
    return since_ms, until_ms


def fetch_ohlcv(exchange: ccxt.Exchange, symbol: str, timeframe: str, since: int, until: int) -> List[List[float]]:
    limit = 1000
    candles: List[List[float]] = []
    fetch_since = since

    while fetch_since <= until:
        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=fetch_since, limit=limit)
        if not batch:
            break
        candles.extend(batch)
        last_timestamp = batch[-1][0]
        if last_timestamp >= until:
            break
        fetch_since = last_timestamp + 1

    return candles


def build_frame(candles: List[List[float]]) -> pd.DataFrame:
    if not candles:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.drop_duplicates(subset="timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)
    return df


def ensure_timestamp_column(frame: pd.DataFrame) -> pd.DataFrame:
    if "timestamp" not in frame.columns:
        if isinstance(frame.index, pd.DatetimeIndex):
            frame = frame.reset_index().rename(columns={frame.index.name or "index": "timestamp"})
        elif "ts" in frame.columns:
            frame = frame.rename(columns={"ts": "timestamp"})
        else:
            raise ValueError("Expected a 'timestamp' column in parquet")
    frame = frame.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["timestamp"])
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    return frame


def save_parquet(df: pd.DataFrame, output_path: Path, append: bool) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if append and output_path.exists():
        existing = ensure_timestamp_column(pd.read_parquet(output_path))
        combined = pd.concat([existing, df], ignore_index=True)
        combined = combined.drop_duplicates(subset="timestamp", keep="last")
        combined = combined.sort_values("timestamp").reset_index(drop=True)
        combined.to_parquet(output_path, engine="pyarrow", index=False)
        print(f"Saved (append+dedupe): {output_path}")
        print(f"Rows total: {len(combined)} | Range: {combined['timestamp'].min()} → {combined['timestamp'].max()}")
        return

    df.to_parquet(output_path, engine="pyarrow", index=False)
    if df.empty:
        print(f"Saved empty dataset: {output_path}")
    else:
        print(f"Saved: {output_path}")
        print(f"Rows total: {len(df)} | Range: {df['timestamp'].min()} → {df['timestamp'].max()}")


def main() -> None:
    seed = seed_all()
    print(f"Seed initialised: {seed}")
    args = parse_arguments()

    repo_root = Path(__file__).resolve().parents[1]
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
    else:
        output_dir = repo_root / "data" / "exchange" / sanitise_symbol(args.symbol)
        output_path = output_dir / f"kline_{args.tf}.parquet"

    existing_df: Optional[pd.DataFrame] = None
    if args.append and output_path.exists():
        existing_df = ensure_timestamp_column(pd.read_parquet(output_path))

    since_ms, until_ms = compute_fetch_bounds(args, existing_df)

    exchange_class = getattr(ccxt, args.exchange)
    exchange = exchange_class({"enableRateLimit": True})

    candles = fetch_ohlcv(exchange, args.symbol, args.tf, since_ms, until_ms)
    fetched_df = build_frame(candles)

    if existing_df is not None and not existing_df.empty:
        fetched_df = pd.concat([existing_df, fetched_df], ignore_index=True)
        fetched_df = fetched_df.drop_duplicates(subset="timestamp", keep="last")
        fetched_df = fetched_df.sort_values("timestamp").reset_index(drop=True)

    save_parquet(fetched_df, output_path, append=False)

    if not fetched_df.empty:
        print(f"Final rows: {len(fetched_df)}")
        print(f"Final range: {fetched_df['timestamp'].min()} → {fetched_df['timestamp'].max()}")
    else:
        print("No data fetched for the requested range.")


if __name__ == "__main__":
    main()
