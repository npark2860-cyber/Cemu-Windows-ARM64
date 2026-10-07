$ErrorActionPreference = 'Stop'
$catalogRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'Cemu-versions'))
$catalogPath = Join-Path $catalogRoot 'catalog.json'
$catalog = Get-Content -LiteralPath $catalogPath -Raw | ConvertFrom-Json
$finalSe = $catalog.roles | Where-Object {$_.source_commit -eq '9c0b899eb31792353909ac7ff81ed42b2dd7f8fa'}
if (-not $finalSe) { throw 'Verified PR #5 entry is missing.' }
if ($finalSe.role -eq 'Release+SE') { Write-Output 'Final SE selection already applied.'; return }
$oldSe = $catalog.roles | Where-Object {$_.role -eq 'Release+SE'}
$moves = @(
    @{ From=$oldSe.source_path; To='Release+SE/history/source-240b52c853f3' },
    @{ From=$finalSe.source_path; To='Release+SE/source' },
    @{ From=$finalSe.archive_path; To=('Release+SE/archives/' + [System.IO.Path]::GetFileName($finalSe.archive_path)) },
    @{ From=$finalSe.binary_path; To='Release+SE/binaries/run-35507685980' }
)
foreach ($move in $moves) {
    $from = [System.IO.Path]::GetFullPath((Join-Path $catalogRoot $move.From))
    $to = [System.IO.Path]::GetFullPath((Join-Path $catalogRoot $move.To))
    $prefix = $catalogRoot.TrimEnd('\') + '\'
    if (-not $from.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -or -not $to.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)) { throw 'Move would leave the version catalog.' }
    if (-not (Test-Path -LiteralPath $from)) { throw "Missing source: $from" }
    if (Test-Path -LiteralPath $to) { throw "Destination exists: $to" }
    New-Item -ItemType Directory -Path ([System.IO.Path]::GetDirectoryName($to)) -Force | Out-Null
    Move-Item -LiteralPath $from -Destination $to
}
$oldSe.source_path = 'Release+SE/history/source-240b52c853f3'
$oldSe.role_kind = 'historical-reference'
$oldSe | Add-Member -Force -NotePropertyName archive_note -NotePropertyValue 'Former upstream Release+SE snapshot and Cemu_se.exe distribution; user designates Cemu_se_test.exe / PR #5 as final SE baseline.'
$catalog.historical_snapshots = @($catalog.historical_snapshots) + @($oldSe)
$finalSe.role = 'Release+SE'
$finalSe.role_kind = 'baseline'
$finalSe.source_path = 'Release+SE/source'
$finalSe.archive_path = $moves[2].To
$finalSe.binary_path = $moves[3].To
$finalSe.selected_by_user = 'User explicitly confirms C:\Emulators\Cemu_arm64\Cemu_se_test.exe is the final SE version.'
$finalSe | Add-Member -Force -NotePropertyName installed_baseline_path -NotePropertyValue 'C:\Emulators\Cemu_arm64\Cemu_se_test.exe'
$finalSe | Add-Member -Force -NotePropertyName installed_baseline_sha256 -NotePropertyValue 'e8791dbea63e85111c1b9a4feab98f31ca469b1802caf379aa5120cffa2dc9c8'
$catalog.roles = @($catalog.roles | Where-Object {$_ -ne $oldSe -and $_ -ne $finalSe}) + @($finalSe)
$orderedRoles = @('Release','Release+SE','Diagnostics','Diagnostics+SE')
$catalog.roles = @($orderedRoles | ForEach-Object { $selectedRole=$_; $catalog.roles | Where-Object {$_.role -eq $selectedRole} })
foreach ($match in $catalog.installed_binary_matches) {
    if ($match.installed_path -eq $finalSe.installed_baseline_path) { $match.matched_roles=@('Release+SE (user-selected final SE)') }
    if ($match.installed_path -eq 'C:\Emulators\Cemu_arm64\Cemu_se.exe') { $match.matched_roles=@('Historical Release+SE') }
}
$catalog | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $catalogPath -Encoding utf8
$catalog.installed_binary_matches | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $catalogRoot 'evidence/installed-binary-matches.json') -Encoding utf8
Write-Output 'Final SE baseline registered as Release+SE; previous source and binary preserved as history.'
