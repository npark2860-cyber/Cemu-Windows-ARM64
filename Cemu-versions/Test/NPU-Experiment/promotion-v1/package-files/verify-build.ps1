$ErrorActionPreference='Stop'
$manifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'NPU-RELEASE-BUILD.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($manifest.status -ne 'BUILT_DEVICE_TEST_PENDING' -or $manifest.module_abi -ne 2 -or $manifest.legacy_gpu_lsfg_linked -ne $false) {throw 'Unexpected NPU candidate identity'}
foreach($file in $manifest.files) {
    $path=Join-Path $PSScriptRoot $file.path
    if(-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) {throw ('Missing or changed candidate file: '+$file.path)}
}
foreach($name in @('npu_driver','gpu_driver')) {
    $driver=$manifest.$name
    $current=Get-ItemProperty -LiteralPath $driver.registry_key
    if($current.DriverVersion -ne $driver.version -or $current.InfPath -ne $driver.inf) {throw ('Driver changed since candidate preparation: '+$name)}
}
if((Get-FileHash -LiteralPath $manifest.npu_driver.rpc_library -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.npu_driver.rpc_sha256) {throw 'RPC library changed'}
[pscustomobject]@{status='NPU_RC1_FILES_VERIFIED_NOT_EXECUTED';executable=(Join-Path $PSScriptRoot $manifest.executable);cemu_executed=$false;gpu_npu_executed=$false}
