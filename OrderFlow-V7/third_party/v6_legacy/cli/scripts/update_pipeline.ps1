param(
    [Parameter(Mandatory = $true)][string]$Symbol,
    [Parameter(Mandatory = $true)][string]$Since,
    [Parameter(Mandatory = $true)][string]$Until,
    [string]$Exchange = "binance",
    [string]$Timeframe = "1m",
    [string]$AtasDir = "data/raw/atas/bar",
    [string]$KlinePath = "",
    [string]$OutputPath = "data/processed/features.parquet",
    [string]$AtasTz = "UTC",
    [int]$ToleranceSeconds = 10,
    [Nullable[int]]$OffsetMinutes = $null
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = "python"

function Get-FullPath([string]$PathValue) {
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return $null
    }
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $repoRoot $PathValue))
}

$fetchScript = Join-Path $repoRoot "preprocessing/fetch_kline.py"
$mergeScript = Join-Path $repoRoot "preprocessing/merge_to_features.py"

$atasDirFull = Get-FullPath $AtasDir
if (-not (Test-Path -Path $atasDirFull)) {
    throw "ATAS directory not found: $atasDirFull"
}

if ([string]::IsNullOrWhiteSpace($KlinePath)) {
    $sanitised = ($Symbol -replace '[^0-9A-Za-z]', '')
    $KlinePath = Join-Path $repoRoot "data/exchange/$sanitised/kline_$Timeframe.parquet"
} else {
    $KlinePath = Get-FullPath $KlinePath
}

$outputFull = Get-FullPath $OutputPath
$klineFull = Get-FullPath $KlinePath
$atasDirFull = Get-FullPath $AtasDir

# Seed initialisation for reproducibility
$seed = (& $python -c "from v6_legacy.core.seeding import seed_all; print(seed_all())").Trim()
if (-not [string]::IsNullOrWhiteSpace($seed)) {
    $env:PYTHONHASHSEED = $seed
    Write-Host "Seed initialised: $seed"
}

# Step 1: Fetch/append kline data
$fetchArgs = @(
    "--symbol", $Symbol,
    "--since", $Since,
    "--until", $Until,
    "--exchange", $Exchange,
    "--tf", $Timeframe,
    "--output", $klineFull,
    "--append"
)

& $python $fetchScript @fetchArgs
if ($LASTEXITCODE -ne 0) {
    throw "fetch_kline.py failed with exit code $LASTEXITCODE"
}

# Step 2: Merge ATAS + Kline streams
$mergeArgs = @(
    "--symbol", $Symbol,
    "--atas-dir", $atasDirFull,
    "--kline", $klineFull,
    "--output", $outputFull,
    "--atas-tz", $AtasTz,
    "--tolerance-seconds", $ToleranceSeconds
)
if ($OffsetMinutes -ne $null) {
    $mergeArgs += @("--offset-minutes", $OffsetMinutes)
}

& $python $mergeScript @mergeArgs
if ($LASTEXITCODE -ne 0) {
    throw "merge_to_features.py failed with exit code $LASTEXITCODE"
}

# Step 3: Generate QC report
$qcScript = @"
import sys
from pathlib import Path
import pandas as pd

def main(parquet_path: str, output_path: str) -> None:
    parquet_file = Path(parquet_path)
    report_file = Path(output_path)
    if not parquet_file.exists():
        raise FileNotFoundError(f"Parquet file not found: {parquet_file}")
    df = pd.read_parquet(parquet_file)
    lines = ["# Data QC Report", f"Source: `{parquet_file}`", f"Rows: {len(df)}"]
    if not df.empty:
        lines.append(f"Time range: {df['timestamp'].min()} → {df['timestamp'].max()}")
        lines.append("")
        lines.append("| column | coverage |")
        lines.append("| --- | --- |")
        for column in df.columns:
            if column == "timestamp":
                continue
            coverage = df[column].replace({"": pd.NA}).notna().mean()
            lines.append(f"| {column} | {coverage:.2%} |")
    else:
        lines.append("")
        lines.append("No data available.")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text("\n".join(lines), encoding="utf-8")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
"@

$tempQcPath = Join-Path ([System.IO.Path]::GetTempPath()) ("qc_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Path $tempQcPath -Value $qcScript -Encoding UTF8

$reportPath = Join-Path $repoRoot "results/data_qc_report.md"
& $python $tempQcPath $outputFull $reportPath
$qcExit = $LASTEXITCODE
Remove-Item -Path $tempQcPath -ErrorAction SilentlyContinue
if ($qcExit -ne 0) {
    throw "QC report generation failed with exit code $qcExit"
}

Write-Host "Pipeline completed successfully."
Write-Host "Features parquet: $outputFull"
Write-Host "QC report: $reportPath"

$schemaPath = Join-Path $repoRoot "preprocessing/schemas/atas_schema.json"
$schemaSignature = (Get-FileHash -Path $schemaPath -Algorithm SHA256).Hash
$exporterVersionLine = (Select-String -Path (Join-Path $repoRoot "atas_integration/indicators/SimplifiedDataExporter.cs") -Pattern "SchemaVersion" -SimpleMatch).Line
$exporterVersion = ($exporterVersionLine -split '"')[1]
$dataManifestHash = if (Test-Path $outputFull) { (Get-FileHash -Path $outputFull -Algorithm SHA256).Hash } else { "N/A" }

$summaryPath = Join-Path $repoRoot "results/qc_summary.md"
$summaryLines = @(
    "# QC Summary",
    "Seed: $seed",
    "Data manifest hash: $dataManifestHash",
    "Exporter version: $exporterVersion",
    "Schema signature: $schemaSignature"
)
$summaryLines | Set-Content -Path $summaryPath -Encoding UTF8
