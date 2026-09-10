$ErrorActionPreference = 'Stop'
$artifactRoot = Split-Path -Parent $PSScriptRoot
$outDir = Join-Path $artifactRoot 'cpu-profiles'
$etl = Get-ChildItem -Path $outDir -Filter 'CPU_*_BOTW_BASELINE.etl' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $etl) { throw 'No CPU profile ETL was found. Run CPU_PROFILE_BOTW.cmd first.' }

$wpa = (Get-Command wpa.exe -ErrorAction SilentlyContinue).Source
if (-not $wpa) {
    $candidates = @(
        "$env:ProgramFiles(x86)\Windows Kits\10\Windows Performance Toolkit\wpa.exe",
        "$env:ProgramFiles\Windows Kits\10\Windows Performance Toolkit\wpa.exe"
    )
    $wpa = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $wpa) {
    Write-Host "Trace: $($etl.FullName)"
    Write-Host 'Windows Performance Analyzer was not found. Install the Windows Performance Toolkit, then open the ETL manually.'
    Read-Host 'Press Enter to close'
    exit 1
}

$symbolCache = Join-Path $artifactRoot 'symbol-cache'
New-Item -ItemType Directory -Force -Path $symbolCache | Out-Null
$localSymbols = $PSScriptRoot
$env:_NT_SYMBOL_PATH = "$localSymbols;srv*$symbolCache*https://msdl.microsoft.com/download/symbols"

Write-Host "Opening: $($etl.FullName)"
Write-Host "Local Cemu symbols: $localSymbols"
Start-Process -FilePath $wpa -ArgumentList @('-i', $etl.FullName)
