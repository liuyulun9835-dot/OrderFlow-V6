$paths = @(
    "data/atas",
    "data/exchange",
    "data/meta",
    "data/processed",
    "logs",
    "results"
)

foreach ($path in $paths) {
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    New-Item -ItemType File -Path (Join-Path $path ".gitkeep") -Force | Out-Null
}

Write-Host "Initialized: $($paths -join ' ')"
