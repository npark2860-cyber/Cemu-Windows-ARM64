param([ValidateSet(720,1080)][int]$Height=720,[switch]$Run)
$ErrorActionPreference='Stop'
$verified=& (Join-Path $PSScriptRoot 'verify-build.ps1')
if(-not $Run) {$verified;return}
if($verified.status -ne 'NPU_RC1_FILES_VERIFIED_NOT_EXECUTED') {throw 'Candidate files not verified'}
. (Join-Path $PSScriptRoot 'probe_process.ps1')
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$prefix=Join-Path $PSScriptRoot ('evidence/module-'+$Height+'p-'+$stamp)
$report=$prefix+'.json'
$runtime=Join-Path $PSScriptRoot 'runtime'
$executable=Join-Path $runtime 'module-smoke-probe.exe'
$session=[ordered]@{status='RUNNING';started_at=(Get-Date).ToString('o');height=$Height;report=$report;cemu_executed=$false;forced_termination=$false;manifest_sha256=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'NPU-RELEASE-BUILD.json')).Hash.ToLowerInvariant()}
$session | ConvertTo-Json | Set-Content -LiteralPath ($prefix+'-session.json') -Encoding UTF8
$exitCode=Invoke-RecordedProbe -Executable $executable -ArgumentLine ('--run '+$Height+' "'+$report+'"') -WorkingDirectory $runtime -StdoutPath ($prefix+'-stdout.txt') -StderrPath ($prefix+'-stderr.txt')
$session.exit_code=$exitCode
$session.ended_at=(Get-Date).ToString('o')
$session.status='FAILED'
if(Test-Path -LiteralPath $report) {
    $result=Get-Content -LiteralPath $report -Raw -Encoding UTF8 | ConvertFrom-Json
    if($exitCode -eq 0 -and $result.status -eq 'MODULE_STARTUP_AND_NPU_RUN_VERIFIED' -and $result.processing_height -eq $Height) {$session.status=$result.status}
}
$session | ConvertTo-Json | Tee-Object -FilePath ($prefix+'-session.json')
if($session.status -eq 'FAILED') {throw ('NPU module check failed. Preserve report: '+$report)}
$result
