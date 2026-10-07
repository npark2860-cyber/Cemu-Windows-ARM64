param([ValidateSet('Baseline','NoQnnProfile','ReuseHost','SharedBalanced','SharedSustained')][string]$Variant = 'Baseline',
      [ValidateRange(1,200)][int]$Iterations = 30, [switch]$Run)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'evidence/tuning-probe-manifest.json') -Raw | ConvertFrom-Json
foreach ($file in $manifest.files) {
    $path = Join-Path $PSScriptRoot $file.path
    if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
        (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) { throw ('Missing or changed file: ' + $file.path) }
}
$original = & (Join-Path $PSScriptRoot 'run-io-probe.ps1') -Variant U8NHWC
if ($original.status -ne 'FILES_VERIFIED_NOT_EXECUTED') { throw 'Original I/O runtime/model preflight failed' }
$cases = @($manifest.variants | Where-Object variant -eq $Variant)
if ($cases.Count -ne 1) { throw 'Variant missing or ambiguous' }
$settings = $cases[0]
$model = $manifest.model
$currentDriver = Get-ItemProperty -LiteralPath $manifest.driver.registry_key
if ($currentDriver.DriverVersion -ne $manifest.driver.version -or $currentDriver.InfPath -ne $manifest.driver.inf) {
    throw 'Active NPU driver changed; refresh the evidence and planned comparison before running.'
}
if ($settings.shared) {
    $settings | Add-Member -NotePropertyName rpc_library -NotePropertyValue $manifest.driver.rpc_library -Force
    if ((Get-FileHash -LiteralPath $settings.rpc_library -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.driver.rpc_sha256) {
        throw 'RPC library changed'
    }
}
if (-not $Run) {
    [pscustomobject]@{status='FILES_VERIFIED_NOT_EXECUTED';variant=$Variant;settings=$settings;model=$model.model;
        driver=$currentDriver.DriverVersion;device_loaded=$false;next='Requires a new user-approved NPU time slot.'}
    return
}
if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne 'Arm64') { throw 'Native ARM64 required' }
$runName = 'htp-tuning-' + $Variant.ToLowerInvariant() + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$runDirectory = Join-Path $PSScriptRoot ('evidence/' + $runName)
$consoleLog = Join-Path $PSScriptRoot ('evidence/' + $runName + '-console.log')
$arguments = @('--run-htp','--input-nhwc','--variant',$Variant,'--model',('../' + $model.model),
    '--out',('../evidence/' + $runName),'--runs',[string]$Iterations,'--warmup','3')
if ($settings.shared) { $arguments += @('--rpc-library',$settings.rpc_library) }
$record = [ordered]@{status='FAILED';variant=$Variant;started_at=(Get-Date).ToString('o');ended_at=$null;exit_code=$null;
    driver_before=$currentDriver.DriverVersion;driver_after=$null;model=$model.model;model_sha256=$model.sha256;
    probe_sha256=$manifest.probe_sha256;manifest_sha256=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'evidence/tuning-probe-manifest.json') -Algorithm SHA256).Hash.ToLowerInvariant();
    settings=$settings;console_log=$consoleLog;run_directory=$runDirectory;result=$null;error=$null;
    quality_validated=$false;external_conversion_costs_measured=$false}
Push-Location (Join-Path $PSScriptRoot 'runtime')
try {
    & './npu-tuning-probe.exe' @arguments *> $consoleLog
    $record.exit_code = $LASTEXITCODE
    if ($record.exit_code -ne 0) { throw ('Probe exited with ' + $record.exit_code) }
    $record.driver_after = (Get-ItemProperty -LiteralPath $manifest.driver.registry_key).DriverVersion
    if ($record.driver_after -ne $record.driver_before) { throw 'Driver changed during measurement' }
    $record.result = & (Join-Path $PSScriptRoot 'scripts/read-tuning-result.ps1') -RunDirectory $runDirectory -Model $model -Settings $settings -Iterations $Iterations -ExpectedOutputSha256 $manifest.reference_output_sha256
    $record.status = $record.result.status
} catch {
    $record.error = $_.Exception.Message
} finally {
    Pop-Location
    $record.ended_at = (Get-Date).ToString('o')
    $record | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $PSScriptRoot ('evidence/' + $runName + '-run.json')) -Encoding utf8
}
$record | ConvertTo-Json -Depth 12
if ($record.status -ne 'HTP_TUNING_VARIANT_VERIFIED') { throw ('Tuning validation failed: ' + $record.error) }
