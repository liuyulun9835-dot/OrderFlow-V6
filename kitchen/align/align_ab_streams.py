"""
Minimal AB alignment script.
- Input: ATAS JSONL(.gz) + Binance CSV/Parquet (1m)
- Normalize timezone to UTC; enforce right-closed [minute_open, minute_close)
- Align on Binance minute_close; compute QC metrics; write prepared bars and QC report
"""

import argparse, json, gzip, sys, pathlib, datetime as dt
import pandas as pd


def _read_atas(path: pathlib.Path) -> pd.DataFrame:
    # supports .jsonl or .jsonl.gz
    opener = gzip.open if path.suffix.endswith("gz") else open
    rows = []
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    df = pd.DataFrame(rows)
    # normalize timestamps to UTC aware -> naive UTC
    for col in ["timestamp","minute_open","minute_close","timestamp_utc"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True).dt.tz_convert(None)
    # rename baseline cols (keep original too if needed)
    if "timestamp" in df.columns:
        df["ts"] = df["timestamp"]
    return df


def _read_binance(path: pathlib.Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        # try parquet (optional dependency). fall back to csv if needed.
        try:
            df = pd.read_parquet(path)
        except Exception:
            raise RuntimeError(f"Parquet not available; provide CSV: {path}")
    # normalize times
    for col in ["timestamp","minute_open","minute_close"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True).dt.tz_convert(None)
    if "timestamp" in df.columns:
        df["ts"] = df["timestamp"]
    return df


def _qc_metrics(df_align: pd.DataFrame) -> dict:
    out = {}
    # coverage rate (both sources present)
    both = df_align["src_span_ok"].mean() if "src_span_ok" in df_align else float("nan")
    out["coverage_rate"] = float(both) if pd.notnull(both) else 0.0
    # median abs pct diff on OHLC
    for c in ["open","high","low","close"]:
        a = df_align[f"atas_{c}"]
        b = df_align[f"bin_{c}"]
        m = (abs(a-b)/b).median() if (a.notna() & b.notna()).any() else float("nan")
        out[f"median_abs_pct_diff_{c}"] = float(m) if pd.notnull(m) else 1.0
    # time skew (ms) between sources' minute_close if both provided
    if "minute_close_atas" in df_align and "minute_close" in df_align:
        skew = (df_align["minute_close_atas"] - df_align["minute_close"]).dt.total_seconds().abs().median()
        out["time_skew_ms"] = float(skew*1000) if pd.notnull(skew) else 0.0
    else:
        out["time_skew_ms"] = 0.0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atas", required=True)
    ap.add_argument("--binance", required=True)
    ap.add_argument("--out", default="data/prepared/bars_1m.parquet")
    ap.add_argument("--qc_report", default="data/prepared/qc/calibration_report.md")
    ap.add_argument("--manifest", default="data/prepared/dataset_manifest.json")
    args = ap.parse_args()

    p_atas = pathlib.Path(args.atas); p_bin = pathlib.Path(args.binance)
    df_a = _read_atas(p_atas)
    df_b = _read_binance(p_bin)

    # select minimal columns
    need = ["ts","open","high","low","close","volume","minute_open","minute_close"]
    # For ATAS, we derive closes; minute boundaries may exist as window_convention
    # rename to prefixed cols to avoid collisions
    a = pd.DataFrame({
        "ts": df_a.get("ts", df_a.get("timestamp")),
        "minute_open_atas": df_a.get("minute_open"),
        "minute_close_atas": df_a.get("minute_close"),
        "atas_open": df_a.get("open"),
        "atas_high": df_a.get("high"),
        "atas_low": df_a.get("low"),
        "atas_close": df_a.get("close"),
        "atas_volume": df_a.get("volume"),
        "bar_vpo_price": df_a.get("bar_vpo_price"),
        "bar_vpo_vol": df_a.get("bar_vpo_vol"),
        "bar_vpo_loc": df_a.get("bar_vpo_loc"),
        "bar_vpo_side": df_a.get("bar_vpo_side"),
        "cvd": df_a.get("cvd"),
    })

    b = pd.DataFrame({
        "ts": df_b.get("ts", df_b.get("timestamp")),
        "minute_open": df_b.get("minute_open"),
        "minute_close": df_b.get("minute_close"),
        "bin_open": df_b.get("open"),
        "bin_high": df_b.get("high"),
        "bin_low": df_b.get("low"),
        "bin_close": df_b.get("close"),
        "bin_volume": df_b.get("volume"),
    })

    # Align using Binance minute_close (right-closed)
    key = ["minute_close"]
    df = pd.merge(b, a, left_on="minute_close", right_on="minute_close_atas", how="left")

    # unified baseline columns
    df["ts"] = df["minute_close"]  # baseline timestamp
    df["open"] = df["bin_open"]
    df["high"] = df["bin_high"]
    df["low"]  = df["bin_low"]
    df["close"] = df["bin_close"]
    df["volume"] = df["bin_volume"]
    df["src_span_ok"] = df["atas_close"].notna()

    # QC
    qc = _qc_metrics(df)

    # write baseline bars
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df_out = df[["ts","open","high","low","close","volume","minute_open","minute_close","src_span_ok",
                     "bar_vpo_price","bar_vpo_vol","bar_vpo_loc","bar_vpo_side","cvd"]]
    except Exception:
        df_out = df[["ts","open","high","low","close","volume","minute_open","minute_close","src_span_ok"]]
    df_out.to_parquet(out_path, index=False)

    # QC report
    rp = pathlib.Path(args.qc_report)
    rp.parent.mkdir(parents=True, exist_ok=True)
    with open(rp, "w", encoding="utf-8") as f:
        f.write("# Calibration Report (AB alignment)\n\n")
        for k,v in qc.items():
            f.write(f"- {k}: {v}\n")

    # manifest (append or create)
    mp = pathlib.Path(args.manifest)
    meta = {"generated_at_utc": dt.datetime.utcnow().isoformat()+"Z",
            "schema_version":"v7.0",
            "files":{"bars_1m.parquet": {"rows": int(len(df_out))}},
            "quality": qc}
    mp.parent.mkdir(parents=True, exist_ok=True)
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
