import argparse, pathlib, pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/prepared/macro_slow.parquet")
    args = ap.parse_args()
    # placeholder: empty table
    pd.DataFrame({"ts":[]}).to_parquet(args.out, index=False)


if __name__ == "__main__":
    main()
