$ErrorActionPreference='Stop'
$manifestPath=Join-Path $PSScriptRoot 'NPU-RELEASE-BUILD.json'
$manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if($manifest.status -ne 'BUILT_NOT_RUNTIME_TESTED' -or $manifest.variant -ne 'Release (NPU EXP v1)' -or $manifest.cemu_machine -ne 'ARM64 0xAA64') {throw 'Unexpected experiment identity'}
foreach($file in $manifest.files) {
    $path=Join-Path $PSScriptRoot $file.path
    if(-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) {throw ('Missing or changed experiment file: '+$file.path)}
}
foreach($name in @('npu_driver','gpu_driver')) {
    $driver=$manifest.$name
    $current=Get-ItemProperty -LiteralPath $driver.registry_key
    if($current.DriverVersion -ne $driver.version -or $current.InfPath -ne $driver.inf) {throw ('Driver changed since build: '+$name)}
}
if((Get-FileHash -LiteralPath $manifest.npu_driver.rpc_library -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.npu_driver.rpc_sha256) {throw 'Pinned RPC driver library changed'}
[pscustomobject]@{status='NPU_RELEASE_FILES_VERIFIED_NOT_EXECUTED';executable=(Join-Path $PSScriptRoot $manifest.executable);variant=$manifest.variant;cemu_executed=$false;gpu_npu_executed=$false;runtime_validation='Pending a separately agreed test time'}
