import argparse, json, pathlib, hashlib


def md5sum(path: pathlib.Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepared", default="data/prepared")
    ap.add_argument("--out", default="data/prepared/signatures.json")
    args = ap.parse_args()
    p = pathlib.Path(args.prepared)
    out = {}
    for name in ["bars_1m.parquet","features_micro.parquet","macro_slow.parquet","dataset_manifest.json"]:
        fp = p / name
        if fp.exists():
            out[name] = {"md5": md5sum(fp)}
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out,"w",encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
