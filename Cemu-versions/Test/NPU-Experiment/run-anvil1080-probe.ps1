param([switch]$Run)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$manifestPath = Join-Path $PSScriptRoot 'evidence/anvil1080-probe-manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
foreach ($file in $manifest.files) {
    $path = Join-Path $PSScriptRoot $file.path
    if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
        (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) { throw ('Missing or changed file: ' + $file.path) }
}
$prior = & (Join-Path $PSScriptRoot 'run-interop-probe.ps1')
if ($prior.status -ne 'FILES_VERIFIED_NOT_EXECUTED') { throw 'Original pinned runtime/driver preflight failed' }
$driverBefore = Get-ItemProperty -LiteralPath $manifest.driver.registry_key
$gpuBefore = Get-ItemProperty -LiteralPath $manifest.graphics.registry_key
if ($driverBefore.DriverVersion -ne $manifest.driver.version -or $driverBefore.InfPath -ne $manifest.driver.inf -or
    $gpuBefore.DriverVersion -ne $manifest.graphics.version -or $gpuBefore.InfPath -ne $manifest.graphics.inf) { throw 'Driver identity changed' }
if (-not (Test-Path -LiteralPath $manifest.python.path -PathType Leaf) -or
    (Get-FileHash -LiteralPath $manifest.python.path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.python.sha256) { throw 'CPU-only evidence reader Python changed' }
if (-not $Run) {
    [pscustomobject]@{status='FILES_VERIFIED_NOT_EXECUTED';device_loaded=$false;model=$manifest.model.model;
        npu_driver=$driverBefore.DriverVersion;gpu_driver=$gpuBefore.DriverVersion;
        next='Requires a new approved GPU/NPU time slot. Runs correctness gate before timing; no Cemu or display operations.'}
    return
}
if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne 'Arm64') { throw 'Native ARM64 required' }
$sessionName = 'anvil1080-session-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$sessionPath = Join-Path $PSScriptRoot ('evidence/' + $sessionName + '.json')
$session = [ordered]@{status='STARTED';started_at=(Get-Date).ToString('o');ended_at=$null;closed=$false;
    manifest_sha256=(Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant();
    probe_sha256=$manifest.probe_sha256;model_sha256=$manifest.model.sha256;runs=@();error=$null}
$verificationDirectory = $null
try {
    foreach ($mode in @('Verify','Measure')) {
        $name = 'anvil1080-' + $mode.ToLowerInvariant() + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
        $directory = Join-Path $PSScriptRoot ('evidence/' + $name)
        $console = Join-Path $PSScriptRoot ('evidence/' + $name + '-console.log')
        $record = [ordered]@{mode=$mode;status='FAILED';started_at=(Get-Date).ToString('o');ended_at=$null;closed=$false;exit_code=$null;
            manifest_sha256=$session.manifest_sha256;probe_sha256=$manifest.probe_sha256;model_sha256=$manifest.model.sha256;
            run_directory=$directory;console_log=$console;npu_driver_before=$driverBefore.DriverVersion;gpu_driver_before=$gpuBefore.DriverVersion;
            npu_driver_after=$null;gpu_driver_after=$null;result=$null;error=$null}
        try {
            $arguments = @('--run-devices','--mode',$mode,'--model',('../' + $manifest.model.model),'--out',('../evidence/' + $name),
                '--rpc-library',$manifest.driver.rpc_library,'--shaders','../shaders')
            Push-Location (Join-Path $PSScriptRoot 'runtime')
            try { & './anvil1080-pipeline-probe.exe' @arguments *> $console; $record.exit_code = $LASTEXITCODE }
            finally { Pop-Location }
            $driverAfter = Get-ItemProperty -LiteralPath $manifest.driver.registry_key
            $gpuAfter = Get-ItemProperty -LiteralPath $manifest.graphics.registry_key
            $record.npu_driver_after=$driverAfter.DriverVersion; $record.gpu_driver_after=$gpuAfter.DriverVersion
            if ($driverAfter.DriverVersion -ne $driverBefore.DriverVersion -or $driverAfter.InfPath -ne $driverBefore.InfPath -or
                $gpuAfter.DriverVersion -ne $gpuBefore.DriverVersion -or $gpuAfter.InfPath -ne $gpuBefore.InfPath) { throw 'Driver changed during run' }
            if ($record.exit_code -ne 0) { throw ('Native probe failed with exit ' + $record.exit_code + '; inspect result.json and console log. Measurement gate stays closed.') }
            $readerArgs = @((Join-Path $PSScriptRoot 'scripts/read_anvil1080_result.py'),'--run-directory',$directory,'--manifest',$manifestPath,'--exit-code',([string]$record.exit_code))
            if ($mode -eq 'Measure') { $readerArgs += @('--verification-directory',$verificationDirectory) }
            $readerOutput = & $manifest.python.path @readerArgs 2>&1
            $readerExit = $LASTEXITCODE
            $readerOutput | Set-Content -LiteralPath (Join-Path $directory 'reader-console.log') -Encoding utf8
            if ($readerExit -ne 0) { throw 'Independent evidence verification failed; inspect reader-console.log. Measurement gate stays closed.' }
            $record.result = Get-Content -LiteralPath (Join-Path $directory 'verification.json') -Raw | ConvertFrom-Json
            if ($record.result.status -ne 'ANVIL1080_PIPELINE_VERIFIED') { throw 'Unexpected reader result' }
            $record.status = $record.result.status
            if ($mode -eq 'Verify') { $verificationDirectory = $directory }
        } catch { $record.error = $_.Exception.Message }
        finally {
            $record.ended_at=(Get-Date).ToString('o'); $record.closed=$true
            $record | ConvertTo-Json -Depth 24 | Set-Content -LiteralPath (Join-Path $PSScriptRoot ('evidence/' + $name + '-run.json')) -Encoding utf8
            $session.runs += $record
            $session | ConvertTo-Json -Depth 26 | Set-Content -LiteralPath $sessionPath -Encoding utf8
        }
        if ($record.status -ne 'ANVIL1080_PIPELINE_VERIFIED') { throw $record.error }
    }
    $session.status='ANVIL1080_SESSION_VERIFIED'
} catch { $session.status='FAILED'; $session.error=$_.Exception.Message }
finally {
    $session.ended_at=(Get-Date).ToString('o'); $session.closed=$true
    $session | ConvertTo-Json -Depth 26 | Set-Content -LiteralPath $sessionPath -Encoding utf8
}
[pscustomobject]@{status=$session.status;session=$sessionPath;closed=$session.closed;started_at=$session.started_at;ended_at=$session.ended_at;
    error=$session.error;runs=@($session.runs | ForEach-Object { [pscustomobject]@{mode=$_.mode;status=$_.status;exit_code=$_.exit_code;directory=$_.run_directory;timing=$_.result.timing} })} | ConvertTo-Json -Depth 12
if ($session.status -ne 'ANVIL1080_SESSION_VERIFIED') { throw ('1080p probe failed: ' + $session.error) }
