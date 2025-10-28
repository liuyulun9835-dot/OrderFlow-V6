import argparse, json, pathlib, pandas as pd, hashlib


def md5sum(path: pathlib.Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepared", default="data/prepared")
    ap.add_argument("--out", default="data/prepared/dataset_manifest.json")
    args = ap.parse_args()
    p = pathlib.Path(args.prepared)
    files = {}
    for name in ["bars_1m.parquet","features_micro.parquet","macro_slow.parquet"]:
        fp = p / name
        if fp.exists():
            try:
                df = pd.read_parquet(fp, engine="pyarrow")
                rows = len(df)
                cols = list(df.columns)
            except Exception:
                rows, cols = None, []
            files[name] = {"md5": md5sum(fp), "rows": rows, "columns": cols}
    with open(p/"qc/calibration_report.md","r",encoding="utf-8") as f:
        calib = f.read()[:4000]
    out = {
      "schema_version": "v7.0",
      "files": files,
      "notes": {"calibration_excerpt": calib}
    }
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out,"w",encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
