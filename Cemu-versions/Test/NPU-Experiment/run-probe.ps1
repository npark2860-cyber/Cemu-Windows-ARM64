param(
    [ValidateSet('SmokeQuantized','SmokeFp16','Anvil')][string]$Stage = 'SmokeQuantized',
    [ValidateRange(1,200)][int]$Iterations = 20,
    [switch]$Run
)
$ErrorActionPreference = 'Stop'
$manifestPath = Join-Path $PSScriptRoot 'evidence/probe-build-manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
foreach ($file in $manifest.files) {
    $path = Join-Path $PSScriptRoot $file.path
    if (-not (Test-Path -LiteralPath $path)) { throw ('Required file missing: ' + $file.path) }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) {
        throw ('Hash mismatch: ' + $file.path)
    }
}
if (-not $Run) {
    [pscustomobject]@{status='FILES_VERIFIED_NOT_EXECUTED';stage=$Stage;architecture='ARM64';runtime='ORT QNN 1.24.4 / QAIRT 2.42';device_loaded=$false;next='Add -Run only when ready for NPU use. Agents must first obtain the user time slot.'}
    return
}
if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne 'Arm64') { throw 'Native Windows ARM64 host required' }
$models = @{SmokeQuantized='smoke-average-qdq-u8.onnx'; SmokeFp16='smoke-average-fp32.onnx'; Anvil='anvil-small-1080p-fp32.onnx'}
$runName = 'htp-' + $Stage.ToLowerInvariant() + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$runRelative = '../evidence/' + $runName
$arguments = @('--run-htp','--model',('../models/' + $models[$Stage]),'--out',$runRelative,'--runs',[string]$Iterations,'--warmup','3')
if ($Stage -ne 'Anvil') { $arguments += '--expect-average' }
$consoleLog = Join-Path $PSScriptRoot ('evidence/' + $runName + '-console.log')
$startedAt = Get-Date
$runExit = $null
Push-Location (Join-Path $PSScriptRoot 'runtime')
try {
    # Synchronous invocation only. No watchdog, UI control, game launch or forced termination.
    & './npu-probe.exe' @arguments *> $consoleLog
    $runExit = $LASTEXITCODE
    $resultPath = Join-Path $runRelative 'result.json'
    $status = 'FAILED'
    $evidence = $null
    if ($runExit -eq 0 -and (Test-Path -LiteralPath $resultPath)) {
        $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
        $evidence = & (Join-Path $PSScriptRoot 'scripts/read-qnn-profile.ps1') -Path $result.profile
        if ($evidence.verified_qnn_only -and $result.backend -eq 'QnnHtp.dll' -and $result.cpu_fallback_disabled) { $status = 'HTP_EXECUTION_VERIFIED' }
        else { $status = 'EXECUTION_PROVIDER_UNVERIFIED' }
    }
    $record = [pscustomobject]@{status=$status;stage=$Stage;started_at=$startedAt.ToString('o');ended_at=(Get-Date).ToString('o');exit_code=$runExit;profile_evidence=$evidence;console_log=$consoleLog;synthetic_input=$true;game_quality_verified=$false;gpu_transfers_measured=$false}
    $record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $PSScriptRoot ('evidence/' + $runName + '-run.json')) -Encoding utf8
    Get-Content -LiteralPath $consoleLog -Tail 12
    $record | ConvertTo-Json -Depth 8
    if ($status -ne 'HTP_EXECUTION_VERIFIED') { throw ('NPU validation did not pass: ' + $status) }
} finally { Pop-Location }
