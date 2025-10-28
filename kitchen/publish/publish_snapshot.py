import argparse, pathlib, shutil, datetime as dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepared", default="data/prepared")
    ap.add_argument("--snapshots", default="snapshots")
    ap.add_argument("--date", default=None)
    args = ap.parse_args()
    date = args.date or dt.datetime.utcnow().date().isoformat()
    src = pathlib.Path(args.prepared)
    dst_root = pathlib.Path(args.snapshots)
    staging = dst_root / f"_staging_{date}"
    final   = dst_root / date
    staging.mkdir(parents=True, exist_ok=True)
    for name in ["bars_1m.parquet","features_micro.parquet","macro_slow.parquet","dataset_manifest.json","signatures.json","qc/calibration_report.md"]:
        sp = src / name
        if sp.exists():
            fp = staging / name
            fp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sp, fp)
    if final.exists():
        shutil.rmtree(final)
    staging.rename(final)
    with open(dst_root/"LATEST","w",encoding="utf-8") as f:
        f.write(date+"\n")


if __name__ == "__main__":
    main()
