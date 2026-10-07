$ErrorActionPreference = 'Stop'
$lab = Join-Path $PSScriptRoot 'Cemu-versions\Test\LSFG-Release'
$stock = Join-Path $lab 'runtime-stock'
$runtime = Join-Path $lab 'runtime-experiment'
if (Test-Path -LiteralPath $runtime) { throw 'Experiment runtime already exists' }
$portable = Join-Path $runtime 'portable'
New-Item -ItemType Directory -Path (Join-Path $portable 'mlc01\usr') -Force | Out-Null
foreach ($name in @('settings.xml','controllerProfiles','gameProfiles','graphicPacks','shaderCache')) {
    Copy-Item -LiteralPath (Join-Path $stock "portable\$name") -Destination $portable -Recurse
}
Copy-Item -LiteralPath (Join-Path $stock 'portable\mlc01\usr\save') -Destination (Join-Path $portable 'mlc01\usr') -Recurse
Copy-Item -LiteralPath (Join-Path $stock 'portable\mlc01\sys') -Destination (Join-Path $portable 'mlc01') -Recurse
New-Item -ItemType Junction -Path (Join-Path $portable 'mlc01\usr\title') -Target 'C:\Users\angel\AppData\Roaming\Cemu\mlc01\usr\title' | Out-Null
Copy-Item -LiteralPath (Join-Path $stock 'Cemu.exe') -Destination (Join-Path $runtime 'Cemu-official.exe')
Copy-Item -LiteralPath (Join-Path $lab 'source\bin\Cemu_release.exe') -Destination (Join-Path $runtime 'Cemu-rebuilt-stock.exe')
[xml]$cfg = Get-Content -LiteralPath (Join-Path $portable 'settings.xml')
$cfg.content.mlc_path = (Join-Path $portable 'mlc01').Replace('\','/')
$cfg.content.window_size.x = '1050'
$cfg.content.window_size.y = '740'
$cfg.content.window_position.x = '150'
$cfg.content.window_position.y = '100'
$cfg.content.Graphic.UpscaleFilter = '4'
$entries = $cfg.SelectNodes("//GraphicPack/Entry[@filename='graphicPacks/downloadedGraphicPacks/BreathOfTheWild/Graphics/rules.txt']/Preset[category='Resolution']/preset")
if ($entries.Count -ne 1) { throw 'BOTW resolution preset is ambiguous' }
$entries[0].InnerText = '960x540'
$cfg.Save((Join-Path $portable 'settings.xml'))
Copy-Item -LiteralPath (Join-Path $portable 'settings.xml') -Destination (Join-Path $lab 'evidence\fsr-test-settings.xml')
@('Cemu-official.exe','Cemu-rebuilt-stock.exe') | ForEach-Object {
    [pscustomobject]@{file=$_;sha256=(Get-FileHash -LiteralPath (Join-Path $runtime $_) -Algorithm SHA256).Hash.ToLowerInvariant()}
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $lab 'evidence\rebuild-identities.json')
Write-Output 'Prepared FSR experiment: 960x540 rendering, FSR upscale, private settings/save/cache.'
