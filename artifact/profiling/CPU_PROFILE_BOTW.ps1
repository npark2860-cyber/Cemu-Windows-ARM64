$ErrorActionPreference = 'Stop'

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdministrator)) {
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $PSCommandPath))
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $argList | Out-Null
    exit
}

$artifactRoot = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $artifactRoot 'Cemu-CPUProfile.exe'
if (-not (Test-Path $exe)) {
    throw "Cemu-CPUProfile.exe was not found next to the profiling folder."
}

$wpr = (Get-Command wpr.exe -ErrorAction SilentlyContinue).Source
if (-not $wpr) {
    throw 'wpr.exe was not found. Windows Performance Recorder is required.'
}

$outDir = Join-Path $artifactRoot 'cpu-profiles'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$etlPath = Join-Path $outDir ("CPU_{0}_BOTW_BASELINE.etl" -f $runId)

$env:CEMU_EXPERIMENTS = 'perf-log'
$env:CEMU_PERF_PRESET = 'CPU_PROFILE_BASELINE'
$env:CEMU_PERF_RUN_ID = $runId
$env:CEMU_PERF_BRANCH = 'runtime-experiments-arm64'

Write-Host '============================================================'
Write-Host ' Cemu ARM64 CPU Hotspot Capture'
Write-Host '============================================================'
Write-Host '1. Cemu will start in BASELINE mode.'
Write-Host '2. Load the same BOTW save/location/camera/weather scene.'
Write-Host '3. When the scene is fully stable, come back here and press Enter.'
Write-Host '4. The script will warm up for 60 seconds, then capture CPU samples for 300 seconds.'
Write-Host '5. Do not move the camera or interact during capture.'
Write-Host '============================================================'
Write-Host

$proc = Start-Process -FilePath $exe -WorkingDirectory $artifactRoot -PassThru
Read-Host 'When the BOTW scene is stable, press Enter to begin the 60 second warm-up'

for ($remaining = 60; $remaining -gt 0; $remaining--) {
    $proc.Refresh()
    if ($proc.HasExited) { throw 'Cemu exited during warm-up.' }
    Write-Progress -Activity 'BOTW warm-up' -Status "$remaining seconds remaining" -PercentComplete ((60-$remaining)/60*100)
    Start-Sleep -Seconds 1
}
Write-Progress -Activity 'BOTW warm-up' -Completed

# Windows 11 ARM64 systems have occasionally retained a bad sampled-profile interval.
# Reset it before capture, then use the verbose CPU profile because CPU.light can
# omit SampledProfile stack walking and produce Stack=n/a in WPA.
& $wpr -resetprofint | Out-Host
if ($LASTEXITCODE -ne 0) { throw "wpr -resetprofint failed with exit code $LASTEXITCODE" }

& $wpr -start CPU -filemode | Out-Host
if ($LASTEXITCODE -ne 0) { throw "WPR CPU sampling could not start (exit code $LASTEXITCODE)." }

$capturing = $true
try {
    & $wpr -marker CEMU_CPU_PROFILE_BEGIN | Out-Null
    for ($remaining = 300; $remaining -gt 0; $remaining--) {
        $proc.Refresh()
        if ($proc.HasExited) {
            Write-Warning 'Cemu exited before the 300 second capture completed.'
            break
        }
        Write-Progress -Activity 'CPU sampling capture' -Status "$remaining seconds remaining" -PercentComplete ((300-$remaining)/300*100)
        Start-Sleep -Seconds 1
    }
    Write-Progress -Activity 'CPU sampling capture' -Completed
    & $wpr -marker CEMU_CPU_PROFILE_END | Out-Null
    & $wpr -stop $etlPath ("Cemu ARM64 BOTW CPU profile {0}" -f $runId) -compress | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "WPR stop failed with exit code $LASTEXITCODE" }
    $capturing = $false
}
finally {
    if ($capturing) {
        & $wpr -cancel | Out-Null
    }
}

Write-Host
Write-Host '============================================================'
Write-Host ' CPU capture complete'
Write-Host '============================================================'
Write-Host "ETL : $etlPath"
Write-Host "PDB : $(Join-Path $PSScriptRoot 'Cemu-CPUProfile.pdb')"
Write-Host
Write-Host 'Open CPU_PROFILE_OPEN_LAST.cmd to inspect the trace in WPA.'
Write-Host 'Use: CPU Usage (Sampled) -> Utilization by Process, Stack'
Write-Host 'Filter Process to Cemu-CPUProfile.exe and export or screenshot the top stacks.'
Write-Host '============================================================'
Read-Host 'Press Enter to close this window'
