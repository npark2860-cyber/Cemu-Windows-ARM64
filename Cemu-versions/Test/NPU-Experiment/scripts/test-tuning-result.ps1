# Offline reader regression tests using copied historical evidence and explicitly synthetic metadata.
# Does not start the native probe, create an ORT session, or load any device library.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root 'evidence/htp-io-u8nhwc-20260929-074227-880'
$fixtureName = 'tuning-reader-fixture-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$fixture = Join-Path $root ('evidence/' + $fixtureName)
if (Test-Path -LiteralPath $fixture) { throw 'Fixture directory already exists' }
New-Item -ItemType Directory -Path $fixture | Out-Null
Copy-Item -LiteralPath (Join-Path $source 'output.bin') -Destination (Join-Path $fixture 'output.bin')
Copy-Item -LiteralPath (Join-Path $source 'qnn-profile.csv') -Destination (Join-Path $fixture 'qnn-profile.csv')
$original = Get-Content -LiteralPath (Join-Path $source 'result.json') -Raw | ConvertFrom-Json
$originalProfile = [IO.Path]::GetFullPath((Join-Path (Join-Path $root 'runtime') $original.profile))
$profileText = Get-Content -LiteralPath $originalProfile -Raw
$profilePath = Join-Path $fixture 'ort-profile.json'
Set-Content -LiteralPath $profilePath -Value $profileText -Encoding utf8
$model = (Get-Content -LiteralPath (Join-Path $root 'evidence/io-probe-manifest.json') -Raw | ConvertFrom-Json).models | Where-Object variant -eq U8NHWC
$expectedHash = '0432f24c82156b07286f45a6c8957673ea3e4d4aee55338dc11bf241bfc03eed'
$cases = [Collections.Generic.List[object]]::new()
function Read-Fixture($settings, $hash = $expectedHash) {
    & (Join-Path $PSScriptRoot 'read-tuning-result.ps1') -RunDirectory $fixture -Model $model -Settings $settings -ExpectedOutputSha256 $hash -Iterations 10
}
function Save-Fixture($value) {
    $value | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $fixture 'result.json') -Encoding utf8
}
function Must-Reject([string]$name, [scriptblock]$operation) {
    $reason = $null
    try { & $operation | Out-Null } catch { $reason = $_.Exception.Message }
    if (-not $reason) { throw ('Reader incorrectly accepted ' + $name) }
    $cases.Add([pscustomobject]@{name=$name;passed=$true;reason=$reason})
}
$baseline = [pscustomobject]@{variant='Baseline';qnn_profile='detailed';performance='balanced';shared=$false;reuse=$false}
$value = $original | ConvertTo-Json -Depth 20 | ConvertFrom-Json
$value.profile = '../evidence/' + $fixtureName + '/ort-profile.json'
$extra = @{tuning_variant='Baseline';qnn_profiling_level='detailed';ort_profiling_enabled=$true;performance_mode='balanced';
    shared_memory=$false;reused_bound_output=$false;input_memory='Cpu';output_memory='Cpu';rpc_library='';
    run_samples_ms=@(1..10 | ForEach-Object { $original.run_mean_ms });offline_fixture=$true}
foreach ($item in $extra.GetEnumerator()) { $value | Add-Member -NotePropertyName $item.Key -NotePropertyValue $item.Value -Force }
Save-Fixture $value
if ((Read-Fixture $baseline).status -ne 'HTP_TUNING_VARIANT_VERIFIED') { throw 'Valid detailed fixture rejected' }
$cases.Add([pscustomobject]@{name='accept_complete_detailed_fixture';passed=$true})

$value.performance_mode = 'sustained_high_performance'
Save-Fixture $value
Must-Reject 'reject_wrong_settings' { Read-Fixture $baseline }
$value.performance_mode = 'balanced'
$value.output_memory = 'QnnHtpShared'
Save-Fixture $value
Must-Reject 'reject_wrong_allocator' { Read-Fixture $baseline }
$value.output_memory = 'Cpu'
Save-Fixture $value
Must-Reject 'reject_wrong_reference_output' { Read-Fixture $baseline ('0' * 64) }
Set-Content -LiteralPath $profilePath -Value $profileText.Replace('QNNExecutionProvider','CPUExecutionProvider') -Encoding utf8
Must-Reject 'reject_cpu_provider' { Read-Fixture $baseline }
Set-Content -LiteralPath $profilePath -Value $profileText -Encoding utf8

# Off must remain verifiable through ORT without requiring or fabricating a QNN CSV.
Move-Item -LiteralPath (Join-Path $fixture 'qnn-profile.csv') -Destination (Join-Path $fixture 'qnn-profile-preserved.csv')
$off = [pscustomobject]@{variant='NoQnnProfile';qnn_profile='off';performance='balanced';shared=$false;reuse=$false}
$value.tuning_variant = $off.variant
$value.qnn_profiling_level = 'off'
Save-Fixture $value
$offResult = Read-Fixture $off
if ($offResult.status -ne 'HTP_TUNING_VARIANT_VERIFIED' -or @($offResult.accelerator_metrics).Count -ne 0) { throw 'Off fixture failed or fabricated device metrics' }
$cases.Add([pscustomobject]@{name='accept_off_without_qnn_csv';passed=$true})

$shared = [pscustomobject]@{variant='SharedBalanced';qnn_profile='off';performance='balanced';shared=$true;reuse=$true;rpc_library='C:\fixture-only\libcdsprpc.dll'}
$value.tuning_variant = $shared.variant
$value.shared_memory = $true
$value.reused_bound_output = $true
$value.input_memory = $value.output_memory = 'QnnHtpShared'
$value.rpc_library = $shared.rpc_library
Save-Fixture $value
if ((Read-Fixture $shared).status -ne 'HTP_TUNING_VARIANT_VERIFIED') { throw 'Shared metadata fixture rejected' }
$cases.Add([pscustomobject]@{name='accept_consistent_shared_metadata_only';passed=$true})

[pscustomobject]@{status='OFFLINE_READER_TESTS_PASSED';device_executed=$false;fixture=$fixtureName;cases=$cases;
    limitation='Synthetic tuning metadata applied to copied historical output/profile. These tests do not establish native shared-memory support or performance.'} |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $fixture 'tests.json') -Encoding utf8
Get-Content -LiteralPath (Join-Path $fixture 'tests.json') -Raw
