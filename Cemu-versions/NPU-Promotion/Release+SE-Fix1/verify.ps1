$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$manifest=Get-Content -LiteralPath (Join-Path $root 'NPU-BUILD.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($manifest.role -ne 'Release+SE' -or $manifest.candidate -ne 'Fix1' -or $manifest.module_abi -ne 2) {throw 'Unexpected package identity'}
function AssertHash($path,$expected) {
    if(-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {throw ('Missing or changed file: '+$path)}
}
foreach($file in $manifest.files) {AssertHash (Join-Path $root $file.path) $file.sha256}
AssertHash (Join-Path $root $manifest.executable) $manifest.cemu_sha256
AssertHash (Join-Path $root 'runtime/cemu_npu.dll') $manifest.module_sha256
$inventory=Join-Path $root $manifest.source_inventory
AssertHash $inventory $manifest.source_inventory_sha256
foreach($file in (Get-Content -LiteralPath $inventory -Raw -Encoding UTF8 | ConvertFrom-Json)) {
    AssertHash (Join-Path (Join-Path $root 'source') $file.path) $file.sha256
}
AssertHash (Join-Path $root 'evidence/source.patch') $manifest.source_patch_sha256
[pscustomobject]@{
    status='FIX1_PACKAGE_FILES_VERIFIED'
    executable=(Join-Path $root $manifest.executable)
    cemu_sha256=$manifest.cemu_sha256
    game_test_pending=$true
    cemu_gpu_npu_controller_executed=$false
} | ConvertTo-Json
