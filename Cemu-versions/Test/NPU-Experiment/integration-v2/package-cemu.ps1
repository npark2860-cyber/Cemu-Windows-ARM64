param([switch]$IncludeExecutable)
$ErrorActionPreference='Stop'
$lab=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$release=(Resolve-Path -LiteralPath (Join-Path $lab '../LSFG-Release')).Path
$destination=Join-Path $lab '../NPU-Release-v2/runtime'
New-Item -ItemType Directory -Path $destination -Force | Out-Null
$destination=(Resolve-Path -LiteralPath $destination).Path
$baseManifest=Get-Content -LiteralPath (Join-Path $lab 'evidence/motion1080-probe-manifest.json') -Raw | ConvertFrom-Json
# The existing preflight verifies every pinned runtime/model/shader dependency.
$preflight=& (Join-Path $lab 'run-motion1080-probe.ps1')
if($preflight.status -ne 'FILES_VERIFIED_NOT_EXECUTED') {throw 'Frozen probe dependency verification failed'}
foreach($file in Get-ChildItem -LiteralPath (Join-Path $lab 'runtime') -File) {
    if($file.Extension -in @('.dll','.so','.cat')) {Copy-Item -LiteralPath $file.FullName -Destination $destination -Force}
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'build/cemu_npu.dll') -Destination $destination -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'build/module-smoke-probe.exe') -Destination $destination -Force
Copy-Item -LiteralPath (Join-Path $lab $baseManifest.model.model) -Destination (Join-Path $destination 'anvil-1080p-u8nhwc.onnx') -Force
New-Item -ItemType Directory -Path (Join-Path $destination 'shaders') -Force | Out-Null
foreach($name in @('generate','downsample','flow','pack','compose')) {
    Copy-Item -LiteralPath (Join-Path $lab ('shaders/motion1080-'+$name+'.spv')) -Destination (Join-Path $destination 'shaders') -Force
}
[System.IO.File]::WriteAllText((Join-Path $destination 'rpc-path.txt'),$baseManifest.driver.rpc_library+[Environment]::NewLine,[System.Text.UTF8Encoding]::new($false))
if(-not (Test-Path -LiteralPath (Join-Path $destination 'resources'))) {
    Copy-Item -LiteralPath (Join-Path $release 'source/bin/resources') -Destination $destination -Recurse
}
$portable=Join-Path $destination 'portable'
New-Item -ItemType Directory -Path $portable -Force | Out-Null
# Only seed independent settings once. Keep the existing explicit MLC path so
# installed games/saves remain discoverable; do not copy or edit MLC contents.
foreach($name in @('settings.xml','title_list_cache.xml','controllerProfiles','gameProfiles','graphicPacks')) {
    $seed=Join-Path $release ('runtime-experiment/portable/'+$name)
    $target=Join-Path $portable $name
    if((Test-Path -LiteralPath $seed) -and -not (Test-Path -LiteralPath $target)) {Copy-Item -LiteralPath $seed -Destination $target -Recurse}
}
if($IncludeExecutable) {
    $binary=Join-Path $release 'source/bin/Cemu_release.exe'
    $bytes=[System.IO.File]::ReadAllBytes($binary)
    $machine=[BitConverter]::ToUInt16($bytes,([BitConverter]::ToInt32($bytes,60)+4))
    if($machine -ne 0xaa64) {throw 'Cemu binary is not native ARM64'}
    $contents=[System.Text.Encoding]::UTF8.GetString($bytes)
    if(-not $contents.Contains('NPU EXP v2 - Release') -or -not $contents.Contains('[NPU] READY/OFF')) {throw 'Cemu binary lacks the NPU experiment identity/path'}
    Copy-Item -LiteralPath $binary -Destination (Join-Path $destination 'Cemu-npu-exp-v2.exe') -Force
}
[pscustomobject]@{runtime=$destination;executable_included=[bool]$IncludeExecutable;device_executed=$false}
