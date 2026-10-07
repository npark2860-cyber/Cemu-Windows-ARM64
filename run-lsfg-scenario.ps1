param([Parameter(Mandatory)][ValidatePattern('^[a-z0-9-]+$')][string]$Name,
      [Parameter(Mandatory)][ValidateSet('Cemu-official.exe','Cemu-rebuilt-stock.exe','Cemu-lsfg.exe','Cemu-lsfg-perf.exe','Cemu-lsfg-profile.exe','Cemu-lsfg-tune.exe','Cemu-lsfg-resize.exe')][string]$Executable)
$ErrorActionPreference = 'Stop'
$lab = Join-Path $PSScriptRoot 'Cemu-versions\Test\LSFG-Release'
$runtime = Join-Path $lab 'runtime-experiment'
$exe = Join-Path $runtime $Executable
$recordPath = Join-Path $lab "evidence\$Name-run.json"
if (Test-Path -LiteralPath $recordPath) { throw 'Scenario record already exists' }
$start = [Diagnostics.ProcessStartInfo]::new()
$start.FileName = $exe
$start.WorkingDirectory = $runtime
$start.UseShellExecute = $false
$start.ArgumentList.Add('-g')
$start.ArgumentList.Add((Join-Path $runtime 'portable\mlc01\usr\title\00050000\101c9300'))
$start.ArgumentList.Add('-f')
$start.ArgumentList.Add('false')
foreach ($key in @($start.Environment.Keys)) {
    if ($key -match '^(CEMU_LSFG_|LSFG_|VK_INSTANCE_LAYERS$|VK_LAYER_PATH$|VK_ADD_LAYER_PATH$)') { $null = $start.Environment.Remove($key) }
}
$start.Environment['DISABLE_LSFG'] = '1'
$start.Environment['DISABLE_LSFGVK'] = '1'
$start.Environment['LSFG_LAYER_ENABLE'] = '0'
$startedAt = Get-Date
$process = [Diagnostics.Process]::Start($start)
$record = [ordered]@{scenario=$Name;exe=$exe;sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant();process_id=$process.Id;started_at=$startedAt.ToString('o');status='RUNNING';watchdog_kill=$false}
$record | ConvertTo-Json | Set-Content -LiteralPath $recordPath -Encoding utf8
Write-Output "Started $Name PID $($process.Id); no forced termination timeout."
while (-not $process.WaitForExit(1000)) { }
$record.status='EXITED'
$record.exit_code=$process.ExitCode
$record.ended_at=(Get-Date).ToString('o')
$record.duration_seconds=[math]::Round(((Get-Date)-$startedAt).TotalSeconds,2)
$record | ConvertTo-Json | Set-Content -LiteralPath $recordPath -Encoding utf8
Copy-Item -LiteralPath (Join-Path $runtime 'portable\log.txt') -Destination (Join-Path $lab "evidence\$Name-log.txt")
$record | ConvertTo-Json
