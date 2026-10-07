$ErrorActionPreference = 'Stop'
$root = Join-Path $PSScriptRoot 'Cemu-versions\Test\LSFG-Release'
$environmentRecord = Get-Content -LiteralPath (Join-Path $root 'evidence\stock-environment.json') -Raw | ConvertFrom-Json
$exe = Join-Path $environmentRecord.runtime 'Cemu.exe'
if ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $environmentRecord.stock_exe_sha256) { throw 'Wrong baseline executable' }
$recordPath = Join-Path $root 'evidence\stock-run.json'
if (Test-Path -LiteralPath $recordPath) { throw 'A baseline run record already exists' }
$start = [Diagnostics.ProcessStartInfo]::new()
$start.FileName = $exe
$start.WorkingDirectory = $environmentRecord.runtime
$start.UseShellExecute = $false
$start.ArgumentList.Add('-g')
$start.ArgumentList.Add($environmentRecord.game)
$start.ArgumentList.Add('-f')
$start.ArgumentList.Add('false')
foreach ($key in @($start.Environment.Keys)) {
    if ($key -match '^(CEMU_LSFG_|LSFG_|VK_INSTANCE_LAYERS$|VK_LAYER_PATH$|VK_ADD_LAYER_PATH$)') { $null = $start.Environment.Remove($key) }
}
$start.Environment['DISABLE_LSFG'] = '1'
$start.Environment['LSFG_LAYER_ENABLE'] = '0'
$startedAt = Get-Date
$process = [Diagnostics.Process]::Start($start)
$record = [ordered]@{role='Release'; sha256=$environmentRecord.stock_exe_sha256; exe=$exe; game=$environmentRecord.game; process_id=$process.Id; started_at=$startedAt.ToString('o'); status='RUNNING'; termination='none'; watchdog_kill=$false}
$record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $recordPath -Encoding utf8
Write-Output "Started stock Release PID $($process.Id). No termination timeout is installed."
while (-not $process.WaitForExit(1000)) { }
$record.status = 'EXITED'
$record.exit_code = $process.ExitCode
$record.ended_at = (Get-Date).ToString('o')
$record.duration_seconds = [math]::Round(((Get-Date)-$startedAt).TotalSeconds,2)
$record.termination = 'process exited; see UI observation record for user close versus failure'
$record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $recordPath -Encoding utf8
$log = Join-Path $environmentRecord.runtime 'portable\log.txt'
if (Test-Path -LiteralPath $log) { Copy-Item -LiteralPath $log -Destination (Join-Path $root 'evidence\stock-log.txt') }
$record | ConvertTo-Json -Depth 4
