param([Parameter(Mandatory)][string]$RunDirectory, [Parameter(Mandatory)][psobject]$Model,
      [Parameter(Mandatory)][psobject]$Settings,
      [Parameter(Mandatory)][string]$ExpectedOutputSha256,
      [ValidateRange(1,200)][int]$Iterations = 30)
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
if ($result.tuning_variant -ne $Settings.variant -or $result.qnn_profiling_level -ne $Settings.qnn_profile -or
    $result.performance_mode -ne $Settings.performance -or $result.shared_memory -ne $Settings.shared -or
    $result.reused_bound_output -ne $Settings.reuse -or $result.ort_profiling_enabled -ne $true) { throw 'Unexpected tuning settings' }
$expectedMemory = if ($Settings.shared) { 'QnnHtpShared' } else { 'Cpu' }
if ($result.input_memory -ne $expectedMemory -or $result.output_memory -ne $expectedMemory) { throw 'Unexpected tensor memory allocator' }
if ($Settings.shared) {
    if ($result.rpc_library -ne $Settings.rpc_library) { throw 'Unexpected RPC library' }
} elseif ($result.rpc_library) { throw 'Unexpected RPC library for host-only case' }
if (@($result.run_samples_ms).Count -ne $Iterations) { throw 'Missing chronological samples' }
foreach ($sample in $result.run_samples_ms) {
    if (-not [double]::IsFinite([double]$sample) -or $sample -le 0) { throw 'Invalid sample' }
}
if ([Math]::Abs(($result.run_samples_ms | Measure-Object -Average).Average - $result.run_mean_ms) -gt 0.000001) { throw 'Mean does not match samples' }
$outputHash = (Get-FileHash -LiteralPath (Join-Path $RunDirectory 'output.bin') -Algorithm SHA256).Hash.ToLowerInvariant()
if ($outputHash -ne $ExpectedOutputSha256) { throw ('Output differs from the verified U8NHWC reference: ' + $outputHash) }
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
$metrics = @()
if ($Settings.qnn_profile -eq 'detailed') {
  $csv = @(Import-Csv -LiteralPath (Join-Path $RunDirectory 'qnn-profile.csv'))
  $metrics = foreach ($name in @('Accelerator (execute excluding wait) time','Accelerator (execute) time','QNN accelerator (execute) time','RPC (execute) time','QNN (execute) time')) {
    $samples = @($csv | Where-Object { $_.'Event Identifier' -eq $name -and $_.'Event Level' -eq 'ROOT' -and $_.'Unit of Measurement' -eq 'US' })
    if ($samples.Count -eq (4 + $Iterations)) {
        $measured = @($samples | Select-Object -Skip 4 | ForEach-Object { [double]::Parse($_.Time,[Globalization.CultureInfo]::InvariantCulture)/1000.0 })
        [pscustomobject]@{name=$name;mean_ms=($measured | Measure-Object -Average).Average;samples=$measured.Count}
    } else { throw ('Incomplete detailed QNN metric: ' + $name) }
  }
}
[pscustomobject]@{status='HTP_TUNING_VARIANT_VERIFIED';variant=$Settings.variant;settings=$Settings;
    run_mean_ms=$result.run_mean_ms;run_p50_ms=$result.run_p50_ms;run_p95_ms=$result.run_p95_ms;run_min_ms=$result.run_min_ms;run_max_ms=$result.run_max_ms;run_samples_ms=$result.run_samples_ms;
    input_shape=$Model.input_shape;output_shape=$Model.output_shape;host_dtype=$Model.host_dtype;layout=$Model.layout;
    profile_evidence=$providerEvidence;accelerator_metrics=@($metrics);metrics_overlap_do_not_add=$true;timing_scope=$result.timing_scope;
    output_sha256=$outputHash;reference_output_identical=$true;
    external_conversion_costs_measured=$false;game_quality_validated=$false}
