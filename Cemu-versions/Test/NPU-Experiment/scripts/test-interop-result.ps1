# Pure CPU fixtures for the result reader. No native probe, Vulkan or QNN session is started.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$manifest = Get-Content -LiteralPath (Join-Path $root 'evidence/interop-probe-manifest.json') -Raw | ConvertFrom-Json
$name = 'interop-reader-fixture-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$directory = Join-Path $root ('evidence/' + $name)
if (Test-Path -LiteralPath $directory) { throw 'Preserve existing fixture' }
New-Item -ItemType Directory -Path $directory | Out-Null
$tests = [Collections.Generic.List[object]]::new()
function Save-Value($v) { $v | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath (Join-Path $directory 'result.json') -Encoding utf8 }
function Read-Value([int]$exitCode = 0) { & (Join-Path $PSScriptRoot 'read-interop-result.ps1') -RunDirectory $directory -Manifest $manifest -ExitCode $exitCode }
function Reject([string]$label, [scriptblock]$action) {
    $reason = $null
    try { & $action | Out-Null } catch { $reason = $_.Exception.Message }
    if (-not $reason) { throw ('Incorrectly accepted ' + $label) }
    $tests.Add([pscustomobject]@{name=$label;passed=$true;reason=$reason})
}
$value = [pscustomobject]@{status='UNSUPPORTED';stage='vulkan_capabilities';reason='Synthetic extension-unavailable fixture';
    model=('../' + $manifest.model.path);rpc_library=$manifest.driver.rpc_library;cemu_executed=$false;full_framegen_validated=$false;
    application_copy_free_gpu_npu_handoff=$false;qnn_initialized=$false;completed_rounds=0;gpu_name='SYNTHETIC FIXTURE';external_memory_host=$false}
Save-Value $value
if ((Read-Value 2).status -ne 'INTEROP_UNSUPPORTED') { throw 'Valid unsupported fixture rejected' }
$tests.Add([pscustomobject]@{name='accept_explicit_unsupported_without_qnn';passed=$true})
Reject 'reject_unsupported_with_wrong_exit_code' { Read-Value 0 }

$roundRecords = @()
for ($round = 0; $round -lt 5; $round++) {
    $bytes = [byte[]]::new(9216)
    for ($i = 0; $i -lt 6144; $i++) {
        $channel = [int][Math]::Floor($i/1024); $lane = $i % 4
        $bytes[$i] = [byte](8 + (($channel*29 + $lane*7 + $round*41) % 224))
    }
    $maxError = 0.0
    for ($i = 0; $i -lt 3072; $i++) {
        $expected = ([int]$bytes[$i] + [int]$bytes[$i+3072])/2.0
        $bytes[$i+6144] = [byte][Math]::Round($expected)
        $maxError = [Math]::Max($maxError,[Math]::Abs([double]$bytes[$i+6144]-$expected))
    }
    [IO.File]::WriteAllBytes((Join-Path $directory ('gpu-readback-round-' + $round + '.bin')),$bytes)
    $roundRecords += [pscustomobject]@{round=$round;gpu_write_and_fence_ms=1.0;npu_run_ms=1.0;gpu_diagnostic_readback_ms=1.0;max_oracle_error=$maxError}
}
$profile = @(1..5 | ForEach-Object { [pscustomobject]@{cat='Node';name='SYNTHETIC_QNN_kernel_time';args=[pscustomobject]@{
    provider='QNNExecutionProvider';input_type_shape=@([pscustomobject]@{uint8=@(1,6,32,32)});output_type_shape=@([pscustomobject]@{uint8=@(1,3,32,32)})}} })
$profilePath = Join-Path $directory 'ort-profile.json'
$profile | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $profilePath -Encoding utf8
$value.status = 'INTEROP_ROUNDTRIP_COMPLETED_PROFILE_VERIFICATION_PENDING'
$value.qnn_initialized = $true; $value.completed_rounds = 5; $value.external_memory_host = $true
$value.application_copy_free_gpu_npu_handoff = $true
$extra = @{backend='QnnHtp.dll';cpu_fallback_disabled=$true;ort_version='1.24.4';application_cpu_writes_to_shared_payload=$false;
    diagnostic_gpu_readback_used=$true;rounds=$roundRecords;input_allocator='QnnHtpShared';output_allocator='QnnHtpShared';
    invocation='direct_preallocated_run';qnn_memhandle_logging=$true;
    input_memory_flags=6;output_memory_flags=6;import_handle_type='HOST_ALLOCATION_BIT_EXT';ort_profile=('../evidence/' + $name + '/ort-profile.json');offline_fixture=$true}
foreach ($item in $extra.GetEnumerator()) { $value | Add-Member -NotePropertyName $item.Key -NotePropertyValue $item.Value -Force }
$logPath = $directory + '-console.log'
@(1..10 | ForEach-Object { 'Setting Qnn_Tensor_t memHandle to ORT tensor shared memory.' }) | Set-Content -LiteralPath $logPath -Encoding utf8
Save-Value $value
if ((Read-Value).status -ne 'INTEROP_ROUNDTRIP_VERIFIED') { throw 'Valid synthetic roundtrip fixture rejected' }
$tests.Add([pscustomobject]@{name='accept_five_changing_oracle_fixtures';passed=$true})
Add-Content -LiteralPath $logPath -Value 'Setting Qnn_Tensor_t clientBuf to ORT tensor memory.'
Reject 'reject_qnn_raw_memory_path' { Read-Value }
@(1..10 | ForEach-Object { 'Setting Qnn_Tensor_t memHandle to ORT tensor shared memory.' }) | Set-Content -LiteralPath $logPath -Encoding utf8

$path = Join-Path $directory 'gpu-readback-round-2.bin'
$saved = [IO.File]::ReadAllBytes($path)
$altered = [byte[]]$saved.Clone(); $altered[10] = 0
[IO.File]::WriteAllBytes($path,$altered)
Reject 'reject_wrong_gpu_input' { Read-Value }
$altered = [byte[]]$saved.Clone(); $altered[6144] = 253
[IO.File]::WriteAllBytes($path,$altered)
Reject 'reject_poison_or_stale_output' { Read-Value }
[IO.File]::WriteAllBytes($path,$saved)
$value.output_memory_flags = 2; Save-Value $value
Reject 'reject_noncoherent_import' { Read-Value }
$value.output_memory_flags = 6; Save-Value $value
foreach ($event in $profile) { $event.args.provider = 'CPUExecutionProvider' }
$profile | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $profilePath -Encoding utf8
Reject 'reject_cpu_fallback' { Read-Value }
foreach ($event in $profile) { $event.args.provider = 'QNNExecutionProvider' }
$profile | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $profilePath -Encoding utf8

[pscustomobject]@{status='OFFLINE_INTEROP_READER_TESTS_PASSED';device_executed=$false;fixture=$name;cases=$tests;
    limitation='All data and profile metadata are synthetic; this validates rejection/oracle logic and does not establish driver support or GPU/NPU interoperability.'} |
    ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $directory 'tests.json') -Encoding utf8
Get-Content -LiteralPath (Join-Path $directory 'tests.json') -Raw
