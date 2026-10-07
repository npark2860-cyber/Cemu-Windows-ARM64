param(
    [Parameter(Mandatory)][string]$RunDirectory,
    [Parameter(Mandatory)][ValidateSet('1080p','720p','540p')][string]$Resolution,
    [ValidateRange(1,200)][int]$Iterations = 10
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$metadata = Get-Content -LiteralPath (Join-Path $root 'evidence/resolution-models.json') -Raw | ConvertFrom-Json
$model = @($metadata.models | Where-Object resolution -eq $Resolution)[0]
$result = Get-Content -LiteralPath (Join-Path $RunDirectory 'result.json') -Raw | ConvertFrom-Json
if ($result.status -ne 'inference_completed_profile_verification_pending' -or
    $result.backend -ne 'QnnHtp.dll' -or $result.cpu_fallback_disabled -ne $true -or
    $result.ort_version -ne '1.24.4' -or $result.model -ne ('../' + $model.path)) {
    throw 'Unexpected model, backend, runtime or unsuccessful inference'
}
if ($result.input_bytes -ne $model.input_bytes -or $result.output_bytes -ne $model.output_bytes -or
    (Get-Item -LiteralPath (Join-Path $RunDirectory 'output.bin')).Length -ne $model.output_bytes) {
    throw 'Tensor byte count does not match the selected resolution'
}
if ($result.measured_runs -ne $Iterations -or $result.warmup_runs -ne 3) { throw 'Unexpected iteration counts' }
foreach ($name in @('run_mean_ms','run_p50_ms','run_p95_ms','run_min_ms','run_max_ms')) {
    $value = $result.$name
    if ($null -eq $value -or -not [double]::IsFinite([double]$value) -or $value -le 0) { throw ('Invalid timing: ' + $name) }
}
$profilePath = [IO.Path]::GetFullPath((Join-Path (Join-Path $root 'runtime') $result.profile))
if ([IO.Path]::GetDirectoryName($profilePath) -ne [IO.Path]::GetFullPath($RunDirectory).TrimEnd('\','/')) {
    throw 'Profile does not belong to the selected run'
}
$providerEvidence = & (Join-Path $PSScriptRoot 'read-qnn-profile.ps1') -Path $profilePath
if (-not $providerEvidence.verified_qnn_only) { throw 'QNN-only execution not verified' }
$events = @(Get-Content -LiteralPath $profilePath -Raw | ConvertFrom-Json -Depth 64)
$kernels = @($events | Where-Object { $_.cat -eq 'Node' -and $_.name -like '*kernel_time' })
# The baseline is one fused QNN graph. Require matching, complete I/O shape evidence for every run.
if ($kernels.Count -ne (1 + 3 + $Iterations)) { throw 'Expected one complete QNN graph per inference; inspect partitioning' }
foreach ($kernel in $kernels) {
    $inputShapes = @($kernel.args.input_type_shape)
    $outputShapes = @($kernel.args.output_type_shape)
    if ($inputShapes.Count -lt 1 -or $outputShapes.Count -ne 1 -or
        ($inputShapes[0].float -join ',') -ne ($model.input_shape -join ',') -or
        ($outputShapes[0].float -join ',') -ne ($model.output_shape -join ',')) {
        throw 'Runtime tensor shape does not match the selected resolution'
    }
}
$csv = @(Import-Csv -LiteralPath (Join-Path $RunDirectory 'qnn-profile.csv'))
$acceleratorMetrics = foreach ($eventName in @('Accelerator (execute excluding wait) time','Accelerator (execute) time','QNN accelerator (execute) time','RPC (execute) time','QNN (execute) time')) {
    $samples = @($csv | Where-Object { $_.'Event Identifier' -eq $eventName -and $_.'Event Level' -eq 'ROOT' -and $_.'Unit of Measurement' -eq 'US' })
    if ($samples.Count -eq (4 + $Iterations)) {
        $measured = @($samples | Select-Object -Skip 4 | ForEach-Object { [double]::Parse($_.Time, [Globalization.CultureInfo]::InvariantCulture) / 1000.0 })
        [pscustomobject]@{name=$eventName;mean_ms=($measured | Measure-Object -Average).Average;samples=$measured.Count}
    }
}
[pscustomobject]@{
    status='HTP_RESOLUTION_VERIFIED';resolution=$Resolution;model_sha256=$model.sha256
    run_mean_ms=$result.run_mean_ms;run_p50_ms=$result.run_p50_ms;run_p95_ms=$result.run_p95_ms
    input_shape=$model.input_shape;output_shape=$model.output_shape;profile_evidence=$providerEvidence
    accelerator_metrics=@($acceleratorMetrics);metrics_overlap_do_not_add=$true
    synthetic_input=$true;game_quality_verified=$false;gpu_transfers_measured=$false
    timing_scope=$result.timing_scope
}
