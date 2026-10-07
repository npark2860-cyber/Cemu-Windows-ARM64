param([Parameter(Mandatory)][string]$RunDirectory, [Parameter(Mandatory)][psobject]$Model,
      [ValidateRange(1,200)][int]$Iterations = 10)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$result = Get-Content -LiteralPath (Join-Path $RunDirectory 'result.json') -Raw | ConvertFrom-Json
if ($result.status -ne 'inference_completed_profile_verification_pending' -or
    $result.backend -ne 'QnnHtp.dll' -or $result.cpu_fallback_disabled -ne $true -or
    $result.ort_version -ne '1.24.4' -or $result.model -ne ('../' + $Model.model)) { throw 'Unexpected model or backend' }
if ($result.input_layout -ne $Model.layout -or $result.input_dtype -ne $Model.host_dtype -or $result.output_dtype -ne $Model.host_dtype -or
    ($result.input_shape -join ',') -ne ($Model.input_shape -join ',') -or ($result.output_shape -join ',') -ne ($Model.output_shape -join ',') -or
    $result.input_bytes -ne $Model.input_bytes -or $result.output_bytes -ne $Model.output_bytes -or
    (Get-Item -LiteralPath (Join-Path $RunDirectory 'output.bin')).Length -ne $Model.output_bytes) { throw 'Unexpected runtime I/O' }
if ($result.measured_runs -ne $Iterations -or $result.warmup_runs -ne 3) { throw 'Unexpected iteration count' }
foreach ($field in @('run_mean_ms','run_p50_ms','run_p95_ms','run_min_ms','run_max_ms')) {
    if ($null -eq $result.$field -or -not [double]::IsFinite([double]$result.$field) -or $result.$field -le 0) { throw 'Invalid timing' }
}
$profile = [IO.Path]::GetFullPath((Join-Path (Join-Path $root 'runtime') $result.profile))
if ([IO.Path]::GetDirectoryName($profile) -ne [IO.Path]::GetFullPath($RunDirectory).TrimEnd('\','/')) { throw 'Unexpected profile directory' }
$providerEvidence = & (Join-Path $PSScriptRoot 'read-qnn-profile.ps1') -Path $profile
if (-not $providerEvidence.verified_qnn_only) { throw 'QNN-only execution not verified' }
$events = @(Get-Content -LiteralPath $profile -Raw | ConvertFrom-Json -Depth 64)
$kernels = @($events | Where-Object { $_.cat -eq 'Node' -and $_.name -like '*kernel_time' })
if ($kernels.Count -ne (4 + $Iterations)) { throw 'Expected one fused QNN graph per inference; inspect partitions' }
$dtype = $Model.host_dtype
foreach ($kernel in $kernels) {
    $inputs = @($kernel.args.input_type_shape)
    $outputs = @($kernel.args.output_type_shape)
    if ($inputs.Count -lt 1 -or $outputs.Count -ne 1 -or
        ($inputs[0].$dtype -join ',') -ne ($Model.input_shape -join ',') -or
        ($outputs[0].$dtype -join ',') -ne ($Model.output_shape -join ',')) { throw 'Profile does not confirm complete I/O shape/type' }
}
$csv = @(Import-Csv -LiteralPath (Join-Path $RunDirectory 'qnn-profile.csv'))
$metrics = foreach ($name in @('Accelerator (execute excluding wait) time','Accelerator (execute) time','QNN accelerator (execute) time','RPC (execute) time','QNN (execute) time')) {
    $samples = @($csv | Where-Object { $_.'Event Identifier' -eq $name -and $_.'Event Level' -eq 'ROOT' -and $_.'Unit of Measurement' -eq 'US' })
    if ($samples.Count -eq (4 + $Iterations)) {
        $measured = @($samples | Select-Object -Skip 4 | ForEach-Object { [double]::Parse($_.Time,[Globalization.CultureInfo]::InvariantCulture)/1000.0 })
        [pscustomobject]@{name=$name;mean_ms=($measured | Measure-Object -Average).Average;samples=$measured.Count}
    }
}
[pscustomobject]@{status='HTP_IO_VARIANT_VERIFIED';variant=$Model.variant;run_mean_ms=$result.run_mean_ms;run_p50_ms=$result.run_p50_ms;run_p95_ms=$result.run_p95_ms;
    input_shape=$Model.input_shape;output_shape=$Model.output_shape;host_dtype=$Model.host_dtype;layout=$Model.layout;
    profile_evidence=$providerEvidence;accelerator_metrics=@($metrics);metrics_overlap_do_not_add=$true;timing_scope=$result.timing_scope;
    external_conversion_costs_measured=$false;game_quality_validated=$false}
