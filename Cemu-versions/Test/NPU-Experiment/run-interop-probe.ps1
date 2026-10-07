param([switch]$Run)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$manifestPath = Join-Path $PSScriptRoot 'evidence/interop-probe-manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
foreach ($file in $manifest.files) {
    $path = Join-Path $PSScriptRoot $file.path
    if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
        (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) { throw ('Missing or changed file: ' + $file.path) }
}
$baseline = & (Join-Path $PSScriptRoot 'run-tuning-probe.ps1') -Variant SharedBalanced
if ($baseline.status -ne 'FILES_VERIFIED_NOT_EXECUTED') { throw 'Original runtime/driver preflight failed' }
$driverBefore = Get-ItemProperty -LiteralPath $manifest.driver.registry_key
if ($driverBefore.DriverVersion -ne $manifest.driver.version -or $driverBefore.InfPath -ne $manifest.driver.inf) { throw 'NPU driver changed' }
$graphicsBefore = Get-ItemProperty -LiteralPath $manifest.graphics.registry_key
if ($graphicsBefore.DriverVersion -ne $manifest.graphics.version -or $graphicsBefore.InfPath -ne $manifest.graphics.inf) { throw 'GPU driver changed; refresh the experiment evidence before running' }
if (-not $Run) {
    [pscustomobject]@{status='FILES_VERIFIED_NOT_EXECUTED';device_loaded=$false;model=$manifest.model.path;
        npu_driver=$driverBefore.DriverVersion;gpu_driver=$graphicsBefore.DriverVersion;
        next='Requires a new user-approved GPU/NPU time slot. Capability gate precedes QNN loading.'}
    return
}
if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne 'Arm64') { throw 'Native ARM64 required' }
$runName = 'vulkan-qnn-interop-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$directory = Join-Path $PSScriptRoot ('evidence/' + $runName)
$console = Join-Path $PSScriptRoot ('evidence/' + $runName + '-console.log')
$record = [ordered]@{status='FAILED';started_at=(Get-Date).ToString('o');ended_at=$null;closed=$false;exit_code=$null;
    npu_driver_before=$driverBefore.DriverVersion;npu_driver_after=$null;gpu_driver_before=$graphicsBefore.DriverVersion;gpu_driver_after=$null;
    manifest_sha256=(Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant();
    probe_sha256=$manifest.probe_sha256;model_sha256=$manifest.model.sha256;run_directory=$directory;console_log=$console;result=$null;error=$null}
$arguments = @('--run-devices','--model',('../' + $manifest.model.path),'--out',('../evidence/' + $runName),'--rpc-library',$manifest.driver.rpc_library)
Push-Location (Join-Path $PSScriptRoot 'runtime')
try {
    & './npu-vulkan-interop-probe.exe' @arguments *> $console
    $record.exit_code = $LASTEXITCODE
    $record.npu_driver_after = (Get-ItemProperty -LiteralPath $manifest.driver.registry_key).DriverVersion
    $record.gpu_driver_after = (Get-ItemProperty -LiteralPath $manifest.graphics.registry_key).DriverVersion
    if ($record.npu_driver_after -ne $record.npu_driver_before -or $record.gpu_driver_after -ne $record.gpu_driver_before) { throw 'Driver changed during execution' }
    $record.result = & (Join-Path $PSScriptRoot 'scripts/read-interop-result.ps1') -RunDirectory $directory -Manifest $manifest -ExitCode $record.exit_code
    $record.status = $record.result.status
} catch {
    $record.error = $_.Exception.Message
} finally {
    Pop-Location
    $record.ended_at = (Get-Date).ToString('o'); $record.closed = $true
    $record | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath (Join-Path $PSScriptRoot ('evidence/' + $runName + '-run.json')) -Encoding utf8
}
$record | ConvertTo-Json -Depth 16
if ($record.status -notin @('INTEROP_ROUNDTRIP_VERIFIED','INTEROP_UNSUPPORTED')) { throw ('Interop probe failed: ' + $record.error) }
