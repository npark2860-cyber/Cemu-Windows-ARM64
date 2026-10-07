param([Parameter(Mandatory)][string]$RunDirectory, [Parameter(Mandatory)][psobject]$Manifest,
      [Parameter(Mandatory)][int]$ExitCode)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$value = Get-Content -LiteralPath (Join-Path $RunDirectory 'result.json') -Raw | ConvertFrom-Json
if ($value.model -ne ('../' + $Manifest.model.path) -or $value.rpc_library -ne $Manifest.driver.rpc_library -or
    $value.cemu_executed -ne $false -or $value.full_framegen_validated -ne $false) { throw 'Unexpected experiment identity or scope' }
if ($ExitCode -eq 2 -and $value.status -eq 'UNSUPPORTED') {
    if (-not $value.reason -or $value.application_copy_free_gpu_npu_handoff -ne $false) { throw 'Invalid unsupported result' }
    return [pscustomobject]@{status='INTEROP_UNSUPPORTED';reason=$value.reason;stage=$value.stage;
        gpu_name=$value.gpu_name;external_memory_host=$value.external_memory_host;
        external_memory_win32=$value.external_memory_win32;external_semaphore_win32=$value.external_semaphore_win32;
        qnn_initialized=$value.qnn_initialized;completed_rounds=$value.completed_rounds;zero_copy_proven=$false}
}
if ($ExitCode -ne 0 -or $value.status -ne 'INTEROP_ROUNDTRIP_COMPLETED_PROFILE_VERIFICATION_PENDING') { throw ('Probe did not complete: ' + $value.reason) }
if ($value.backend -ne 'QnnHtp.dll' -or $value.cpu_fallback_disabled -ne $true -or $value.qnn_initialized -ne $true -or
    $value.ort_version -ne '1.24.4' -or $value.external_memory_host -ne $true -or
    $value.application_copy_free_gpu_npu_handoff -ne $true -or $value.application_cpu_writes_to_shared_payload -ne $false -or
    $value.diagnostic_gpu_readback_used -ne $true -or $value.completed_rounds -ne 5 -or @($value.rounds).Count -ne 5 -or
    $value.input_allocator -ne 'QnnHtpShared' -or $value.output_allocator -ne 'QnnHtpShared' -or
    $value.import_handle_type -ne 'HOST_ALLOCATION_BIT_EXT') { throw 'Incomplete import/backend evidence' }
# Require HOST_VISIBLE (0x2) + HOST_COHERENT (0x4), as used by this bounded probe.
foreach ($flags in @($value.input_memory_flags,$value.output_memory_flags)) {
    if (([uint32]$flags -band 6) -ne 6) { throw 'Unexpected non-coherent or non-host-visible memory' }
}
$profilePath = [IO.Path]::GetFullPath((Join-Path (Join-Path $root 'runtime') $value.ort_profile))
if ([IO.Path]::GetDirectoryName($profilePath) -ne [IO.Path]::GetFullPath($RunDirectory).TrimEnd('\','/')) { throw 'Profile escaped the run directory' }
$provider = & (Join-Path $PSScriptRoot 'read-qnn-profile.ps1') -Path $profilePath
if (-not $provider.verified_qnn_only) { throw 'QNN-only execution not verified' }
$profile = Get-Content -LiteralPath $profilePath -Raw | ConvertFrom-Json -Depth 64
$kernels = @($profile | Where-Object { $_.cat -eq 'Node' -and $_.name -like '*kernel_time' })
if ($kernels.Count -ne 5) { throw 'Expected five complete fused-graph calls' }
foreach ($kernel in $kernels) {
    if (($kernel.args.input_type_shape[0].uint8 -join ',') -ne '1,6,32,32' -or
        @($kernel.args.output_type_shape).Count -ne 1 -or ($kernel.args.output_type_shape[0].uint8 -join ',') -ne '1,3,32,32') { throw 'Unexpected graph I/O shape or type' }
}
$checks = @()
$priorOutput = $null
for ($round = 0; $round -lt 5; $round++) {
    $native = $value.rounds[$round]
    if ($native.round -ne $round) { throw 'Unexpected round sequence' }
    foreach ($name in @('gpu_write_and_fence_ms','npu_run_ms','gpu_diagnostic_readback_ms')) {
        if ($null -eq $native.$name -or -not [double]::IsFinite([double]$native.$name) -or $native.$name -le 0) { throw 'Invalid round timing' }
    }
    $path = Join-Path $RunDirectory ('gpu-readback-round-' + $round + '.bin')
    $bytes = [IO.File]::ReadAllBytes($path)
    if ($bytes.Length -ne 9216) { throw 'Unexpected diagnostic buffer size' }
    for ($index = 0; $index -lt 6144; $index++) {
        $channel = [int][Math]::Floor($index / 1024)
        $lane = $index % 4
        $expected = 8 + (($channel * 29 + $lane * 7 + $round * 41) % 224)
        if ($bytes[$index] -ne $expected) { throw 'GPU input audit failed' }
    }
    $maximumError = 0.0
    for ($index = 0; $index -lt 3072; $index++) {
        $channel = [int][Math]::Floor($index / 1024)
        $lane = $index % 4
        $a = 8 + (($channel * 29 + $lane * 7 + $round * 41) % 224)
        $b = 8 + ((($channel + 3) * 29 + $lane * 7 + $round * 41) % 224)
        $errorValue = [Math]::Abs([double]$bytes[6144 + $index] - (($a + $b)/2.0))
        $maximumError = [Math]::Max($maximumError,$errorValue)
        if ($errorValue -gt 1) { throw 'GPU-read output arithmetic oracle failed' }
    }
    $currentOutput = [byte[]]$bytes[6144..9215]
    if ($null -ne $priorOutput -and [Convert]::ToBase64String($currentOutput) -eq [Convert]::ToBase64String($priorOutput)) { throw 'Output remained stale' }
    $priorOutput = $currentOutput
    if ($maximumError -ne $native.max_oracle_error) { throw 'Native oracle report differs from independent check' }
    $checks += [pscustomobject]@{round=$round;max_oracle_error=$maximumError;readback_sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant();
        gpu_write_and_fence_ms=$native.gpu_write_and_fence_ms;npu_run_ms=$native.npu_run_ms;gpu_diagnostic_readback_ms=$native.gpu_diagnostic_readback_ms}
}
[pscustomobject]@{status='INTEROP_ROUNDTRIP_VERIFIED';gpu_name=$value.gpu_name;profile=$provider;rounds=$checks;
    application_copy_free_gpu_npu_handoff=$true;diagnostic_readback_used=$true;
    physical_zero_copy_proven=$false;full_framegen_validated=$false;
    limitation='Verifies application-level handoff through the same imported RPC allocations with changing small GPU patterns; does not prove no internal driver copies, 1080p image/compute interoperability, performance, or complete frame generation.'}
