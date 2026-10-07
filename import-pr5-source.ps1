$ErrorActionPreference = 'Stop'
$catalogRoot = Join-Path $PSScriptRoot 'Cemu-versions'
$selection = Get-Content -LiteralPath (Join-Path $catalogRoot 'evidence/pr5-selection.json') -Raw | ConvertFrom-Json
$repoUrl = 'https://github.com/npark2860-cyber/Cemu-Windows-ARM64.git'
$sourcePath = Join-Path $catalogRoot $selection.source_path
if (-not (Test-Path -LiteralPath $sourcePath)) {
    & git -c core.longpaths=true clone --quiet --depth 1 --single-branch --branch $selection.branch -- $repoUrl $sourcePath
    if ($LASTEXITCODE -ne 0) { throw 'PR #5 clone failed.' }
}
$head = (& git -C $sourcePath rev-parse HEAD).Trim()
if ($head -ne $selection.source_commit) { throw "PR #5 advanced: $head. Recheck before continuing." }
& git -C $sourcePath config core.longpaths true
& git -C $sourcePath -c core.longpaths=true submodule update --init --recursive --depth 1 --jobs 4
if ($LASTEXITCODE -ne 0) { throw 'PR #5 submodule checkout failed.' }
$catalogPath = Join-Path $catalogRoot 'catalog.json'
$catalog = Get-Content -LiteralPath $catalogPath -Raw | ConvertFrom-Json
$oldTest = $catalog.roles | Where-Object {$_.role -eq 'Test'}
if ($oldTest.source_commit -ne $selection.source_commit) {
    $oldTest | Add-Member -Force -NotePropertyName archive_note -NotePropertyValue 'Historical 2026-09-19 SE fingerprint test snapshot. Superseded by user-selected PR #5.'
    $catalog | Add-Member -Force -NotePropertyName historical_snapshots -NotePropertyValue @($oldTest)
    $catalog.roles = @($catalog.roles | Where-Object {$_.role -ne 'Test'}) + @($selection)
}
$se = $catalog.roles | Where-Object {$_.role -eq 'Release+SE'}
$se.PSObject.Properties.Remove('preferred_local_build')
$se | Add-Member -Force -NotePropertyName latest_se_work -NotePropertyValue ([ordered]@{ source='PR #5'; catalog_role='Test'; status='Open draft PR targeting test_SE, not yet promoted to Release+SE' })
$catalog | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $catalogPath -Encoding utf8
Write-Output "VERIFIED PR #5 source $head"
