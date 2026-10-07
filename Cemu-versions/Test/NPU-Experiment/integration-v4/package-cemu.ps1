$ErrorActionPreference='Stop'
$lab=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$test=(Resolve-Path -LiteralPath (Join-Path $lab '..')).Path
$baseRoot=Join-Path $test 'NPU-Release-v3'
$base=Get-Content -LiteralPath (Join-Path $baseRoot 'NPU-RELEASE-BUILD.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$package=Join-Path $test 'NPU-Release-v4'
$runtime=Join-Path $package 'runtime'
if(Test-Path -LiteralPath $runtime) {throw 'Preserve the existing runtime; inspect before repackaging'}
$baseCheck=& (Join-Path $baseRoot 'verify-build.ps1')
if($baseCheck.status -ne 'NPU_RELEASE_FILES_VERIFIED_NOT_EXECUTED') {throw 'v3 package verification failed'}
$flowCheck=& (Join-Path $lab 'flow-cache-v4/run.ps1')
if($flowCheck.status -ne 'FLOW_CACHE_FILES_VERIFIED_NOT_EXECUTED') {throw 'Flow candidate changed'}
$reportPath=Join-Path $lab 'evidence/flow-cache-v4-20260929-165722-515.json'
$session=Get-Content -LiteralPath (Join-Path $lab 'evidence/flow-cache-v4-20260929-165722-515-session.json') -Raw | ConvertFrom-Json
$report=Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
$candidateManifest=(Get-FileHash -LiteralPath (Join-Path $lab 'flow-cache-v4/manifest.json')).Hash.ToLowerInvariant()
if($session.exit_code -ne 0 -or $session.manifest_sha256 -ne $candidateManifest -or $report.status -ne 'FLOW_CACHE_WARP_MAPPING_VERIFIED' -or $report.equivalent_warp_pairs -ne 45 -or $report.warp_mapping_differing_pixels -ne 0 -or $report.measured_pairs -ne 30 -or $report.cached.mean_ms -ge $report.baseline.mean_ms) {throw 'Successful comparison and performance evidence unavailable'}
$binary=Join-Path $test 'LSFG-Release/source/bin/Cemu_release.exe'
$pe=[System.IO.File]::ReadAllBytes($binary)
if([BitConverter]::ToUInt16($pe,([BitConverter]::ToInt32($pe,60)+4)) -ne 0xaa64) {throw 'Expected ARM64 Cemu'}
$text=[System.Text.Encoding]::UTF8.GetString($pe)
if(-not $text.Contains('NPU EXP v4 - Release - Flow Cache') -or -not $text.Contains('[NPU] READY/OFF')) {throw 'Expected v4 Release NPU binary identity'}
New-Item -ItemType Directory -Path $runtime | Out-Null
# Copy only pinned application dependencies. Do not clone saves, logs or caches.
foreach($file in $base.files) {
    if(-not $file.path.StartsWith('runtime/') -or $file.path -eq $base.executable -or $file.path -eq 'runtime/shaders/motion1080-flow.spv') {continue}
    $destination=Join-Path $package $file.path
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $baseRoot $file.path) -Destination $destination
}
Copy-Item -LiteralPath $binary -Destination (Join-Path $runtime 'Cemu-npu-exp-v4.exe')
Copy-Item -LiteralPath (Join-Path $lab 'flow-cache-v4/runtime/flow-cached.spv') -Destination (Join-Path $runtime 'shaders/motion1080-flow.spv')
$portable=Join-Path $runtime 'portable'
New-Item -ItemType Directory -Path $portable | Out-Null
foreach($name in @('settings.xml','title_list_cache.xml','controllerProfiles','gameProfiles','graphicPacks')) {
    $seed=Join-Path $baseRoot ('runtime/portable/'+$name)
    if(Test-Path -LiteralPath $seed) {Copy-Item -LiteralPath $seed -Destination (Join-Path $portable $name) -Recurse}
}
[pscustomobject]@{status='NPU_V4_PACKAGE_PREPARED_NOT_EXECUTED';runtime=$runtime;cemu_executed=$false;gpu_npu_executed=$false}
