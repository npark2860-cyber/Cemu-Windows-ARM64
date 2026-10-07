param([switch]$Run)
$ErrorActionPreference='Stop'
$verified=& (Join-Path $PSScriptRoot 'verify-build.ps1')
if(-not $Run) {$verified;return}
if(Get-Process -Name 'Cemu*','module-smoke-probe','motion1080-pipeline-probe' -ErrorAction SilentlyContinue) {throw 'Another Cemu/NPU experiment is active; leave it running and arrange a separate test time'}
$lab=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../NPU-Experiment')).Path
$tag='npu-module-smoke-v2-'+(Get-Date -Format yyyyMMdd-HHmmss-fff)
$prefix=Join-Path $lab ('evidence/'+$tag)
$session=[ordered]@{status='STARTING';started_at=(Get-Date).ToString('o');executable=(Join-Path $PSScriptRoot 'runtime/module-smoke-probe.exe');working_directory=$lab;report=($prefix+'.json');cemu_executed=$false;ui_automation=$false;forced_termination=$false}
$session | ConvertTo-Json | Set-Content -LiteralPath ($prefix+'-session.json') -Encoding utf8
$process=Start-Process -FilePath $session.executable -ArgumentList @('--run',('"'+$session.report+'"')) -WorkingDirectory $lab -WindowStyle Hidden -RedirectStandardOutput ($prefix+'-stdout.txt') -RedirectStandardError ($prefix+'-stderr.txt') -PassThru
$process.WaitForExit()
$session.exit_code=$process.ExitCode
$session.ended_at=(Get-Date).ToString('o')
$session.status='FAILED'
if($process.ExitCode -eq 0 -and (Test-Path -LiteralPath $session.report)) {
    $result=Get-Content -LiteralPath $session.report -Raw | ConvertFrom-Json
    if($result.status -eq 'MODULE_STARTUP_AND_NPU_RUN_VERIFIED' -and $result.startup_off_zero_runs -and $result.observed_npu_runs -ge 1 -and $result.completed_jobs -ge 1) {$session.status='MODULE_STARTUP_AND_NPU_RUN_VERIFIED'}
}
$session | ConvertTo-Json | Set-Content -LiteralPath ($prefix+'-session.json') -Encoding utf8
$session | ConvertTo-Json
if($session.status -ne 'MODULE_STARTUP_AND_NPU_RUN_VERIFIED') {throw 'Module device check failed; inspect its report and stderr before any retry'}
