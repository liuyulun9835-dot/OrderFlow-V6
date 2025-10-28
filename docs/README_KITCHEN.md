# Central Data Kitchen

This branch focuses solely on the data acquisition and preparation stack that feeds the OrderFlow research workflow. It standardizes raw vendor exports (ATAS JSONL, Binance 1m bars), aligns the feeds in UTC, and publishes verified datasets for downstream consumers.

## Layout Overview

```
configs/            # runtime configuration (paths, symbols, thresholds)
data/
  raw/             # vendor-native payloads (ATAS JSONL, Binance CSV/Parquet)
  prepared/        # normalized minute bars + engineered features
  samples/         # curated subsets for sanity checks / demos
  prepared/qc/     # quality-control reports and diagnostics
kitchen/
  align/           # cross-feed calibration scripts
  features/        # micro/macro feature generation
  publish/         # manifest/signature generation & atomic snapshot publish
  daemon/          # lightweight looped runner for unattended operation
scripts/            # orchestration glue (watchdogs, runners, launchers)
snapshots/          # published artifacts (dated directories + LATEST pointer)
```

## Core Pipelines

1. **Alignment** — `python -m kitchen.align.align_ab_streams --atas ... --binance ...`
   * Produces `data/prepared/bars_1m.parquet`
   * Emits QC report (`data/prepared/qc/calibration_report.md`) and manifest stub
2. **Feature Engineering** — `make data.features`
   * `kitchen/features/make_features_micro.py` enriches bars with OHLC/ATAS metrics
   * `kitchen/features/make_features_macro.py` currently ships an empty placeholder table
3. **Publishing** — `make data.manifest` & `make data.snapshot`
   * Builds dataset manifest + MD5 signatures
   * Copies artifacts into `snapshots/<ISO_DATE>/` and updates `snapshots/LATEST`

## Operations Toolkit

- `scripts/binance_runner.py` wraps the user-supplied `scripts/fetch_binance_1m.py` to collect rolling T-1/T bars.
- `scripts/watchdog_atas.py` monitors the ATAS heartbeat file for freshness.
- `scripts/launcher.py` supervises the local runners (auto-restarts on exit).
- `kitchen/daemon/kitchen_daemon.py` provides a minimal sequential scheduler; enable via the launcher if desired.

## Governance Contracts

Reference thresholds and schemas live under `governance/`:

- `SCHEMA_data.json` — canonical minute bar schema (baseline attributes + QC flag)
- `SCHEMA_features.json` — enumerates micro/macro feature families
- `CONTROL_kitchen.yaml` — minimum coverage and skew tolerances enforced post-alignment

## Getting Started

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt  # or use poetry if preferred
make data.align   # align one day of ATAS vs Binance data
make data.features
make data.manifest
make data.snapshot
```

> **Note:** Ensure `scripts/fetch_binance_1m.py` dependencies and credentials are configured as per vendor guidance.
