param([ValidateSet('FloatNCHW','U8NCHW','U8NHWC')][string]$Variant = 'FloatNCHW',
      [ValidateRange(1,200)][int]$Iterations = 10, [switch]$Run)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'evidence/io-probe-manifest.json') -Raw | ConvertFrom-Json
foreach ($file in $manifest.files) {
    $path = Join-Path $PSScriptRoot $file.path
    if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
        (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) { throw ('Missing or changed file: ' + $file.path) }
}
$baseline = & (Join-Path $PSScriptRoot 'run-int8-probe.ps1')
if ($baseline.status -ne 'FILES_VERIFIED_NOT_EXECUTED') { throw 'Original INT8 preflight failed' }
$models = @($manifest.models | Where-Object variant -eq $Variant)
if ($models.Count -ne 1) { throw 'Variant missing or ambiguous' }
$model = $models[0]
if (-not $Run) {
    [pscustomobject]@{status='FILES_VERIFIED_NOT_EXECUTED';variant=$Variant;model=$model.model;model_sha256=$model.sha256;
        layout=$model.layout;host_dtype=$model.host_dtype;device_loaded=$false;next='Requires a new user-approved NPU time slot.'}
    return
}
if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne 'Arm64') { throw 'Native ARM64 required' }
$runName = 'htp-io-' + $Variant.ToLowerInvariant() + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$runDirectory = Join-Path $PSScriptRoot ('evidence/' + $runName)
$consoleLog = Join-Path $PSScriptRoot ('evidence/' + $runName + '-console.log')
$arguments = @('--run-htp','--model',('../' + $model.model),'--out',('../evidence/' + $runName),'--runs',[string]$Iterations,'--warmup','3')
if ($model.layout -eq 'NHWC') { $arguments += '--input-nhwc' }
$record = [ordered]@{status='FAILED';variant=$Variant;started_at=(Get-Date).ToString('o');ended_at=$null;exit_code=$null;model=$model.model;
    model_sha256=$model.sha256;probe_sha256=$manifest.probe_sha256;settings='balanced, detailed profiling, same logical synthetic image';console_log=$consoleLog;
    result=$null;error=$null;quality_validated=$false;external_conversion_costs_measured=$false}
Push-Location (Join-Path $PSScriptRoot 'runtime')
try {
    & './npu-io-probe.exe' @arguments *> $consoleLog
    $record.exit_code = $LASTEXITCODE
    if ($record.exit_code -ne 0) { throw ('Probe exited with ' + $record.exit_code) }
    $record.result = & (Join-Path $PSScriptRoot 'scripts/read-io-result.ps1') -RunDirectory $runDirectory -Model $model -Iterations $Iterations
    $record.status = $record.result.status
} catch {
    $record.error = $_.Exception.Message
} finally {
    Pop-Location
    $record.ended_at = (Get-Date).ToString('o')
    $record | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $PSScriptRoot ('evidence/' + $runName + '-run.json')) -Encoding utf8
}
$record | ConvertTo-Json -Depth 12
if ($record.status -ne 'HTP_IO_VARIANT_VERIFIED') { throw ('I/O variant validation failed: ' + $record.error) }
