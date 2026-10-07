param([ValidateRange(1,200)][int]$Iterations = 10, [switch]$Run)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'evidence/int8-probe-manifest.json') -Raw | ConvertFrom-Json
foreach ($file in $manifest.files) {
    $path = Join-Path $PSScriptRoot $file.path
    if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
        (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) {
        throw ('Missing or changed experiment file: ' + $file.path)
    }
}
$baseline = & (Join-Path $PSScriptRoot 'run-probe.ps1')
if ($baseline.status -ne 'FILES_VERIFIED_NOT_EXECUTED') { throw 'Original probe preflight failed' }
$prep = Get-Content -LiteralPath (Join-Path $PSScriptRoot $manifest.preparation) -Raw | ConvertFrom-Json
if ($prep.status -ne 'SYNTHETIC_INT8_PREPARED_NOT_NPU_TESTED' -or
    ($prep.input_shape -join ',') -ne '1,6,1080,1920' -or ($prep.output_shape -join ',') -ne '1,3,1080,1920' -or
    $prep.weight_bits -ne 8 -or $prep.activation_bits -ne 8 -or $prep.quality_validated -ne $false) {
    throw 'Unexpected experiment metadata'
}
if (-not $Run) {
    [pscustomobject]@{status='FILES_VERIFIED_NOT_EXECUTED';resolution='1080p';model=$prep.model;model_sha256=$prep.sha256;device_loaded=$false;precision='Synthetic U8 weights + U8 activations; FLOAT32 host I/O';quality_validated=$false}
    return
}
if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne 'Arm64') { throw 'Native Windows ARM64 required' }
$runName = 'htp-int8-1080p-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$runDirectory = Join-Path $PSScriptRoot ('evidence/' + $runName)
$consoleLog = Join-Path $PSScriptRoot ('evidence/' + $runName + '-console.log')
$arguments = @('--run-htp','--model',('../' + $prep.model),'--out',('../evidence/' + $runName),'--runs',[string]$Iterations,'--warmup','3')
$record = [ordered]@{status='FAILED';started_at=(Get-Date).ToString('o');ended_at=$null;exit_code=$null;model_sha256=$prep.sha256;model=$prep.model;precision='U8/U8 QDQ';host_io='FLOAT32';calibration='Synthetic 136x240 proxy ranges reused at 1080p';settings='Original ARM64 probe, balanced, detailed profiling';console_log=$consoleLog;result=$null;error=$null;quality_validated=$false;gpu_transfers_measured=$false}
Push-Location (Join-Path $PSScriptRoot 'runtime')
try {
    & './npu-probe.exe' @arguments *> $consoleLog
    $record.exit_code = $LASTEXITCODE
    if ($record.exit_code -ne 0) { throw ('Probe exited with ' + $record.exit_code) }
    $result = Get-Content -LiteralPath (Join-Path $runDirectory 'result.json') -Raw | ConvertFrom-Json
    if ($result.status -ne 'inference_completed_profile_verification_pending' -or $result.backend -ne 'QnnHtp.dll' -or
        $result.cpu_fallback_disabled -ne $true -or $result.ort_version -ne '1.24.4' -or
        $result.model -ne ('../' + $prep.model) -or $result.measured_runs -ne $Iterations -or $result.warmup_runs -ne 3 -or
        $result.input_bytes -ne $prep.input_bytes -or $result.output_bytes -ne $prep.output_bytes -or
        (Get-Item -LiteralPath (Join-Path $runDirectory 'output.bin')).Length -ne $prep.output_bytes) {
        throw 'Result does not match the prepared 1080p INT8 experiment'
    }
    $profilePath = [IO.Path]::GetFullPath((Join-Path (Join-Path $PSScriptRoot 'runtime') $result.profile))
    if ([IO.Path]::GetDirectoryName($profilePath) -ne [IO.Path]::GetFullPath($runDirectory)) { throw 'Unexpected profile path' }
    $providerEvidence = & (Join-Path $PSScriptRoot 'scripts/read-qnn-profile.ps1') -Path $profilePath
    if (-not $providerEvidence.verified_qnn_only) { throw 'QNN-only execution not verified' }
    $events = @(Get-Content -LiteralPath $profilePath -Raw | ConvertFrom-Json -Depth 64)
    $kernels = @($events | Where-Object { $_.cat -eq 'Node' -and $_.name -like '*kernel_time' })
    if ($kernels.Count -ne (4 + $Iterations)) { throw 'Expected one fused QNN graph per inference; inspect partitions' }
    foreach ($kernel in $kernels) {
        if (($kernel.args.input_type_shape[0].float -join ',') -ne '1,6,1080,1920' -or
            @($kernel.args.output_type_shape).Count -ne 1 -or ($kernel.args.output_type_shape[0].float -join ',') -ne '1,3,1080,1920') {
            throw 'Runtime shape or I/O precision differs from the prepared experiment'
        }
    }
    foreach ($name in @('run_mean_ms','run_p95_ms','run_min_ms','run_max_ms')) {
        if ($null -eq $result.$name -or -not [double]::IsFinite([double]$result.$name) -or $result.$name -le 0) { throw ('Invalid timing: ' + $name) }
    }
    $csv = @(Import-Csv -LiteralPath (Join-Path $runDirectory 'qnn-profile.csv'))
    $metrics = foreach ($name in @('Accelerator (execute excluding wait) time','Accelerator (execute) time','QNN accelerator (execute) time','RPC (execute) time','QNN (execute) time')) {
        $samples = @($csv | Where-Object { $_.'Event Identifier' -eq $name -and $_.'Event Level' -eq 'ROOT' -and $_.'Unit of Measurement' -eq 'US' })
        if ($samples.Count -eq (4 + $Iterations)) {
            $measured = @($samples | Select-Object -Skip 4 | ForEach-Object { [double]::Parse($_.Time,[Globalization.CultureInfo]::InvariantCulture)/1000.0 })
            [pscustomobject]@{name=$name;mean_ms=($measured | Measure-Object -Average).Average;samples=$measured.Count}
        }
    }
    $record.result = [pscustomobject]@{run_mean_ms=$result.run_mean_ms;run_p50_ms=$result.run_p50_ms;run_p95_ms=$result.run_p95_ms;profile_evidence=$providerEvidence;accelerator_metrics=@($metrics);metrics_overlap_do_not_add=$true;timing_scope=$result.timing_scope}
    $record.status = 'HTP_SYNTHETIC_INT8_1080P_VERIFIED'
} catch {
    $record.error = $_.Exception.Message
} finally {
    Pop-Location
    $record.ended_at = (Get-Date).ToString('o')
    $record | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $PSScriptRoot ('evidence/' + $runName + '-run.json')) -Encoding utf8
}
$record | ConvertTo-Json -Depth 12
if ($record.status -ne 'HTP_SYNTHETIC_INT8_1080P_VERIFIED') { throw ('INT8 validation failed: ' + $record.error) }
