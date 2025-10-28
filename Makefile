.PHONY: data.prepare data.align data.features data.manifest data.snapshot kitchen.run

data.prepare:
@echo "Normalize raw (UTC typing, compression) - placeholder"

data.align:
python -m kitchen.align.align_ab_streams --atas data/raw/atas/bar_20251024.jsonl.gz --binance data/raw/binance/kline_1m.csv --out data/prepared/bars_1m.parquet

data.features:
python -m kitchen.features.make_features_micro --bars data/prepared/bars_1m.parquet --out data/prepared/features_micro.parquet
python -m kitchen.features.make_features_macro --out data/prepared/macro_slow.parquet

data.manifest:
python -m kitchen.publish.make_manifest --prepared data/prepared --out data/prepared/dataset_manifest.json
python -m kitchen.publish.make_signatures --prepared data/prepared --out data/prepared/signatures.json

data.snapshot:
python -m kitchen.publish.publish_snapshot --prepared data/prepared --snapshots snapshots

kitchen.run:
python scripts/launcher.py
