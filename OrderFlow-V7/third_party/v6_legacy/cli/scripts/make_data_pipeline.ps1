param(
  [string]$AtasDir = "$env:USERPROFILE\Documents\ATAS\Exports",
  [string]$Symbol  = "BTC/USDT",
  [string]$Since   = "2020-01-01",
  [string]$Until   = (Get-Date).ToString("yyyy-MM-dd")
)
Write-Host "=== 104: fetch klines ==="
poetry run python preprocessing/fetch_kline.py --symbol $Symbol --since $Since --until $Until --exchange binance
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== 106: gen sessions ==="
poetry run python preprocessing/gen_sessions.py $Since $Until UTC --output data/meta/sessions.csv
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== 107: merge features ==="
$symFlat = [regex]::Replace($Symbol, "[^0-9A-Za-z]", "")
poetry run python preprocessing/merge_to_features.py --symbol $symFlat --atas-dir $AtasDir --kline data/exchange/$symFlat/kline_1m.parquet --output data/processed/features.parquet
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== 108: QC report ==="
poetry run python validation/src/qc_report.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "=== DONE ==="
