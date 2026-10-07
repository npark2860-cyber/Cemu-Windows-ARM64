param(
    [ValidateSet('1080p','720p','540p')][string]$Resolution = '720p',
    [ValidateRange(1,200)][int]$Iterations = 10,
    [switch]$Run
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$manifestPath = Join-Path $PSScriptRoot 'evidence/resolution-probe-manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
foreach ($file in $manifest.files) {
    $path = Join-Path $PSScriptRoot $file.path
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw ('Required file missing: ' + $file.path) }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) {
        throw ('Hash mismatch: ' + $file.path)
    }
}
# Preserve and verify the complete original runtime/source/model manifest as well.
$baseline = & (Join-Path $PSScriptRoot 'run-probe.ps1')
if ($baseline.status -ne 'FILES_VERIFIED_NOT_EXECUTED') { throw 'Baseline preflight failed' }
$metadata = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'evidence/resolution-models.json') -Raw | ConvertFrom-Json
$model = @($metadata.models | Where-Object resolution -eq $Resolution)[0]
if (-not $Run) {
    [pscustomobject]@{status='FILES_VERIFIED_NOT_EXECUTED';resolution=$Resolution;model=$model.path;model_sha256=$model.sha256;device_loaded=$false;settings='HTP FP16, balanced, detailed profiling, 3 warmups';next='Add -Run only after the user agrees to a new NPU time slot.'}
    return
}
if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne 'Arm64') { throw 'Native Windows ARM64 host required' }
$runName = 'htp-resolution-' + $Resolution + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$runDirectory = Join-Path $PSScriptRoot ('evidence/' + $runName)
$consoleLog = Join-Path $PSScriptRoot ('evidence/' + $runName + '-console.log')
$arguments = @('--run-htp','--model',('../' + $model.path),'--out',('../evidence/' + $runName),'--runs',[string]$Iterations,'--warmup','3')
$record = [ordered]@{status='FAILED';resolution=$Resolution;started_at=(Get-Date).ToString('o');ended_at=$null;exit_code=$null;model_sha256=$model.sha256;probe_sha256='59517848f33dfbe26a9fe0f5208c41a227471949d2f7981c0f867bcb992602d9';settings='HTP FP16, balanced, detailed profiling';console_log=$consoleLog;result=$null;error=$null}
Push-Location (Join-Path $PSScriptRoot 'runtime')
try {
    # Synchronous invocation; no game/UI control, watchdog, fallback or forced termination.
    & './npu-probe.exe' @arguments *> $consoleLog
    $record.exit_code = $LASTEXITCODE
    if ($record.exit_code -ne 0) { throw ('Probe exited with ' + $record.exit_code) }
    $record.result = & (Join-Path $PSScriptRoot 'scripts/read-resolution-result.ps1') -RunDirectory $runDirectory -Resolution $Resolution -Iterations $Iterations
    $record.status = $record.result.status
} catch {
    $record.error = $_.Exception.Message
} finally {
    Pop-Location
    $record.ended_at = (Get-Date).ToString('o')
    $record | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $PSScriptRoot ('evidence/' + $runName + '-run.json')) -Encoding utf8
}
$record | ConvertTo-Json -Depth 12
if ($record.status -ne 'HTP_RESOLUTION_VERIFIED') { throw ('Resolution validation failed: ' + $record.error) }
