#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
拉取 Binance 1m K线（UTC 自然日分区），落盘 Parquet：
  python scripts/fetch_binance_1m.py --symbol BTC/USDT --date 2025-10-24 --out data/exchange/BTCUSDT
"""
import ccxt
import argparse
import pathlib
import pandas as pd
from datetime import datetime, timezone, timedelta
from tenacity import retry, wait_exponential, stop_after_attempt

def to_ms(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)

@retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(5))
def fetch_ohlcv_page(ex, symbol, timeframe, since_ms, limit=1000):
    """
    返回列表：[[t, o, h, l, c, v], ...]，t 为 int 毫秒
    """
    return ex.fetch_ohlcv(symbol=symbol, timeframe=timeframe, since=since_ms, limit=limit)

def fetch_range(symbol: str, day: datetime, outdir: pathlib.Path):
    # ccxt 统一接口（现货）；如需合约可换成 ccxt.binanceusdm()
    ex = ccxt.binance({"enableRateLimit": True})
    timeframe = "1m"

    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    end   = start + timedelta(days=1)
    start_ms, end_ms = to_ms(start), to_ms(end)

    rows = []
    since = start_ms
    while since < end_ms:
        page = fetch_ohlcv_page(ex, symbol, timeframe, since, limit=1000)
        if not page:
            break
        for t, o, h, l, c, v in page:
            if t >= end_ms:
                break
            rows.append((t, o, h, l, c, v))
        # 前进：最后一根的开盘时间 + 60_000ms
        last_t = int(page[-1][0])
        since = last_t + 60_000
        # 安全阀：防止死循环
        if len(page) < 1000:
            # 已经到尾部
            if since >= end_ms:
                break

    if not rows:
        raise RuntimeError("No klines returned. Check symbol/time or network.")

    df = pd.DataFrame(rows, columns=["open_time_ms","open","high","low","close","volume"]).drop_duplicates(subset=["open_time_ms"])
    df["timestamp"]   = pd.to_datetime(df["open_time_ms"], unit="ms", utc=True)
    df["minute_open"] = df["timestamp"].dt.floor("min")
    df["minute_close"]= df["minute_open"] + pd.Timedelta(minutes=1)

    # 期望全天应为 1440 根；个别日子会少几根（交易所偶发缺口）
    df = df.sort_values("minute_open")
    partdir = outdir / f"date={start.strftime('%Y-%m-%d')}"
    partdir.mkdir(parents=True, exist_ok=True)
    csv_path = partdir / "kline_1m.csv"
    df.to_csv(csv_path, index=False, float_format="%.8f")
    print(f"saved {len(df)} rows to {csv_path}")
    return df

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTC/USDT", help="ccxt 符号，例如 BTC/USDT（现货）")
    ap.add_argument("--date", required=True, help="UTC 日期，如 2025-10-24")
    ap.add_argument("--out",  default="data/exchange/BTCUSDT")
    args = ap.parse_args()

    day = datetime.fromisoformat(args.date).replace(tzinfo=timezone.utc)
    outdir = pathlib.Path(args.out)
    fetch_range(args.symbol, day, outdir)
