import argparse, pathlib, pandas as pd, numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", default="data/prepared/bars_1m.parquet")
    ap.add_argument("--out",  default="data/prepared/features_micro.parquet")
    args = ap.parse_args()

    p = pathlib.Path(args.bars)
    df = pd.read_parquet(p)

    # OHLC-derived
    df["range1m"]   = df["high"] - df["low"]
    df["real_body"] = (df["close"] - df["open"]).abs()
    df["upper_wick"]= df["high"] - df[["open","close"]].max(axis=1)
    df["lower_wick"]= df[["open","close"]].min(axis=1) - df["low"]
    df["hlc3"]      = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, np.nan)
    df["ohlc_vol_norm"] = df["real_body"] / vol

    # ATAS-derived already aligned (may be null)
    for c in ["bar_vpo_price","bar_vpo_vol","bar_vpo_loc","bar_vpo_side","cvd"]:
        if c not in df.columns:
            df[c] = np.nan

    # impute flag (we keep NA; just flag)
    df["impute_flag"] = df[["bar_vpo_price","bar_vpo_vol","bar_vpo_loc"]].isna().any(axis=1).astype(int)

    out = pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)


if __name__ == "__main__":
    main()
