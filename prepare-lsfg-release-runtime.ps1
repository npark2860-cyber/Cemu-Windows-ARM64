$ErrorActionPreference = 'Stop'
$root = Join-Path $PSScriptRoot 'Cemu-versions\Test\LSFG-Release'
$runtime = Join-Path $root 'runtime-stock'
$portable = Join-Path $runtime 'portable'
$originalData = 'C:\Users\angel\AppData\Roaming\Cemu'
$originalExe = 'C:\Emulators\Cemu_arm64\Cemu.exe'
$expected = 'd2d77ee6961d9f834740ae450653a9f9235da27f43f3b82ed35ca7b2acc56abb'
if ((Get-FileHash -LiteralPath $originalExe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw 'Stock Release identity mismatch' }
if (Test-Path -LiteralPath $runtime) { throw 'Runtime already exists; do not overwrite test state' }
New-Item -ItemType Directory -Path $portable -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $root 'evidence') -Force | Out-Null
Copy-Item -LiteralPath $originalExe -Destination (Join-Path $runtime 'Cemu.exe')
foreach ($name in @('settings.xml', 'controllerProfiles', 'gameProfiles', 'graphicPacks', 'shaderCache')) {
    Copy-Item -LiteralPath (Join-Path $originalData $name) -Destination $portable -Recurse
}
$mlc = Join-Path $portable 'mlc01'
New-Item -ItemType Directory -Path (Join-Path $mlc 'usr\save\00050000') -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $originalData 'mlc01\usr\save\00050000\101c9300') -Destination (Join-Path $mlc 'usr\save\00050000') -Recurse
Copy-Item -LiteralPath (Join-Path $originalData 'mlc01\usr\save\system') -Destination (Join-Path $mlc 'usr\save') -Recurse
Copy-Item -LiteralPath (Join-Path $originalData 'mlc01\sys') -Destination $mlc -Recurse
# Game title contents are only opened for reading during these runs. Mutable
# saves, settings, caches and graphic packs are independent copies above.
New-Item -ItemType Junction -Path (Join-Path $mlc 'usr\title') -Target (Join-Path $originalData 'mlc01\usr\title') | Out-Null
[xml]$config = Get-Content -LiteralPath (Join-Path $portable 'settings.xml')
$config.content.mlc_path = $mlc.Replace('\','/')
$config.content.fullscreen = 'false'
$config.content.window_maximized = 'false'
$config.content.check_update = 'false'
$config.content.use_discord_presence = 'false'
$config.Save((Join-Path $portable 'settings.xml'))
$protected = @($originalExe, (Join-Path $originalData 'settings.xml')) + @(Get-ChildItem -LiteralPath (Join-Path $originalData 'mlc01\usr\save\00050000\101c9300') -File -Recurse | ForEach-Object FullName)
$hashes = @($protected | ForEach-Object { [pscustomobject]@{path=$_; sha256=(Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash.ToLowerInvariant()} })
[pscustomobject]@{
    prepared_at = (Get-Date).ToString('o')
    baseline_role = 'Release (not SE)'
    stock_exe_sha256 = $expected
    runtime = $runtime
    game = Join-Path $mlc 'usr\title\00050000\101c9300'
    mutable_data_is_copied = $true
    original_title_content_junction = Join-Path $mlc 'usr\title'
    protected_files = $hashes
    config_changes = @('private mlc_path', 'windowed', 'update check off', 'Discord presence off')
    graphics_settings_and_packs = 'preserved from copied user settings'
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $root 'evidence\stock-environment.json') -Encoding utf8
Write-Output "Prepared stock runtime: $runtime"
Write-Output "SHA256: $expected"
