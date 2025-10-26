param(
  # 固定项目路径（按你的要求）
  [string]$Project = (Join-Path (Split-Path -Parent $PSScriptRoot) "..\integrations\atas\indicators\SimplifiedDataExporter.csproj"),
  # 是否部署到 ATAS 自定义指标目录
  [bool]$Deploy = $true,
  # 目标 DLL 路径（ATAS 设置里可查看实际目录）
  [string]$Dest = "$env:USERPROFILE\Documents\ATAS\Indicators\SimplifiedDataExporter.dll",
  # 构建配置
  [string]$Configuration = "Release"
)
$ErrorActionPreference = "Stop"

$Project = [System.IO.Path]::GetFullPath($Project)

if (!(Test-Path $Project)) {
  Write-Error "项目文件不存在：$Project"
  exit 1
}

Write-Host "==> dotnet restore $Project" -ForegroundColor Cyan
dotnet restore $Project

Write-Host "==> dotnet build $Project -c $Configuration" -ForegroundColor Cyan
dotnet build $Project -c $Configuration

$projDir = Split-Path $Project
$bin = Join-Path $projDir "bin\$Configuration"
$dll = Get-ChildItem $bin -Recurse -Filter SimplifiedDataExporter.dll |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1

if (-not $dll) {
  Write-Error "未找到构建产物 SimplifiedDataExporter.dll 于 $bin"
  exit 1
}

Write-Host "==> Build OK: $($dll.FullName)" -ForegroundColor Green

if ($Deploy) {
  $destDir = Split-Path $Dest
  if (!(Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir | Out-Null }
  if (Test-Path $Dest) {
    Copy-Item $Dest "$Dest.bak_$(Get-Date -f yyyyMMddHHmmss)" -ErrorAction SilentlyContinue
  }
  Copy-Item $dll.FullName $Dest -Force
  Write-Host "==> Deployed: $Dest" -ForegroundColor Green
  Get-Item $Dest | Select-Object FullName, LastWriteTime | Format-List
}

Write-Host "`n提示：在 ATAS 中加载 SimplifiedDataExporter 指标，设置：SessionMode=rolling:60, WriteOnBarCloseOnly=true, OutputTimezone=UTC, Backfill=true (回放时)。" -ForegroundColor Yellow
