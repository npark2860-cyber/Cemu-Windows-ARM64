param([ValidateSet('All','Release','Release+SE','Diagnostics','Diagnostics+SE')][string]$Variant='All')
$ErrorActionPreference='Stop'
$roles=if($Variant -eq 'All') {@('Release','Release+SE','Diagnostics','Diagnostics+SE')} else {@($Variant)}
foreach($role in $roles) {
    $root=Join-Path $PSScriptRoot $role
    $manifest=Get-Content -LiteralPath (Join-Path $root 'NPU-BUILD.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $expectedAbi=2
    if($role -in @('Release','Release+SE') -and $manifest.in_place_bugfix.name -eq 'native-originals-and-bounded-GPU-lag-buffering') {$expectedAbi=3}
    if($manifest.status -ne 'LOCAL_BUILD_AND_PACKAGE_VERIFIED' -or $manifest.role -ne $role -or $manifest.module_abi -ne $expectedAbi -or $manifest.legacy_gpu_lsfg_linked -ne $false) {throw ('Unexpected package identity: '+$role)}
    foreach($file in $manifest.files) {
        $path=Join-Path $root $file.path
        if(-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) {throw ('Missing or changed package file: '+$role+'/'+$file.path)}
    }
    $inventory=Join-Path $root $manifest.source_inventory
    if((Get-FileHash -LiteralPath $inventory -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.source_inventory_sha256) {throw ('Source inventory changed: '+$role)}
    $sources=Get-Content -LiteralPath $inventory -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach($file in $sources) {
        $path=Join-Path (Join-Path $root 'source') $file.path
        if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) {throw ('Changed source file: '+$role+'/'+$file.path)}
    }
    if((Get-FileHash -LiteralPath (Join-Path $root $manifest.executable) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.cemu_sha256) {throw ('Executable identity mismatch: '+$role)}
    if((Get-FileHash -LiteralPath (Join-Path $root 'runtime/cemu_npu.dll') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.module_sha256) {throw ('NPU module identity mismatch: '+$role)}
    foreach($name in @('npu_driver','gpu_driver')) {
        $driver=$manifest.$name
        $current=Get-ItemProperty -LiteralPath $driver.registry_key
        if($current.DriverVersion -ne $driver.version -or $current.InfPath -ne $driver.inf) {throw ('Driver changed since validation: '+$name)}
    }
    if((Get-FileHash -LiteralPath $manifest.npu_driver.rpc_library -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.npu_driver.rpc_sha256) {throw 'RPC library changed since validation'}
    [pscustomobject]@{status='NPU_PACKAGE_FILES_VERIFIED';variant=$role;executable=(Join-Path $root $manifest.executable);cemu_executed=$false;gpu_npu_executed=$false}
}
