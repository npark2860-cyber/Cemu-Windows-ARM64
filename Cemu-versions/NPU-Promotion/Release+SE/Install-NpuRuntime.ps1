param([switch]$Install)
$ErrorActionPreference='Stop'
$planPath=Join-Path $PSScriptRoot 'evidence/npu-runtime-20261005/install-plan.json'
$plan=Get-Content -LiteralPath $planPath -Raw -Encoding UTF8 | ConvertFrom-Json
$target=[IO.Path]::GetFullPath($plan.target_root).TrimEnd('\')
if($target -ne 'C:\Emulators\Cemu_arm64') {throw 'Unexpected install target'}
$sourceRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'runtime')).TrimEnd('\')
$evidenceRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'evidence/npu-runtime-20261005')).TrimEnd('\')
function UnderRoot([string]$root,[string]$relative) {
    $path=[IO.Path]::GetFullPath((Join-Path $root $relative))
    if(-not $path.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)) {throw ('Path escapes expected directory: '+$path)}
    return $path
}
function NoReparse([string]$path) {
    $current=$path
    while($current) {
        if(Test-Path -LiteralPath $current) {
            if((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {throw ('Unexpected linked path: '+$current)}
        }
        $parent=[IO.Path]::GetDirectoryName($current)
        if($parent -eq $current) {break}
        $current=$parent
    }
}
function Hash([string]$path) {return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
function NoCemu {
    if(@(Get-Process -Name '*Cemu*' -ErrorAction SilentlyContinue).Count) {throw 'Cemu is running. Close it normally before installation; no process was stopped.'}
}
if($plan.source_manifest -ne (Join-Path $PSScriptRoot 'NPU-BUILD.json') -or (Hash $plan.source_manifest) -ne $plan.source_manifest_sha256) {throw 'Source package identity changed'}
$backup=UnderRoot $evidenceRoot 'installed-before'
$receipt=UnderRoot $evidenceRoot 'installed-result.json'
if($backup -ne $plan.backup_root -or $receipt -ne $plan.receipt) {throw 'Unexpected evidence destination'}
NoReparse $target
$seen=@{}
foreach($file in $plan.files) {
    $relative=[string]$file.relative_path
    if($relative -match '(^|/)(portable|mlc01|settings.xml|controllerProfiles|gameProfiles)(/|$)') {throw 'User data must not be installed'}
    $destination=UnderRoot $target $relative
    $source=UnderRoot $sourceRoot $relative
    if($seen.ContainsKey($destination)) {throw 'Duplicate install target'}
    $seen[$destination]=$true
    if($file.source -ne $source -or (Hash $source) -ne $file.sha256) {throw ('Changed source file: '+$relative)}
    NoReparse $destination
    if(Test-Path -LiteralPath $destination) {
        if(-not $file.before_sha256 -or (Hash $destination) -ne $file.before_sha256) {throw ('Destination changed since preparation: '+$relative)}
    } elseif($file.before_sha256) {throw ('Original destination disappeared: '+$relative)}
}
foreach($file in $plan.protected_executables) {
    if((Hash (UnderRoot $target $file.relative_path)) -ne $file.sha256) {throw ('Existing executable changed: '+$file.relative_path)}
}
$runtimeManifest=UnderRoot $target 'NPU-RUNTIME.json'
if(Test-Path -LiteralPath $runtimeManifest) {throw 'Preserve existing installation record before retrying'}
$bytes=($plan.files | Measure-Object -Property bytes -Sum).Sum
if(-not $Install) {
    [pscustomobject]@{status='INSTALL_PLAN_VERIFIED';target=$target;files=$plan.files.Count;bytes=$bytes;user_data_modified=$false;devices_executed=$false} | ConvertTo-Json
    return
}
NoCemu
New-Item -ItemType Directory -Path $backup -Force | Out-Null
# Install dependencies first; make the path configuration available near the
# end, and replace the ABI3 host last. A mixed ABI fails back to original frames.
$ordered=$plan.files | Sort-Object @{Expression={if($_.relative_path -eq 'Cemu-Release-SE-NPU.exe') {3} elseif($_.relative_path -eq 'rpc-path.txt') {2} else {1}}},relative_path
$installed=@()
$preserved=@()
try {
    foreach($file in $ordered) {
        NoCemu
        $destination=UnderRoot $target $file.relative_path
        if($file.before_sha256 -eq $file.sha256) {
            if((Hash $destination) -ne $file.sha256) {throw 'Existing identical file changed during installation'}
            $preserved+=$file.relative_path
            $installed+=$file.relative_path
            continue
        }
        if($file.before_sha256) {
            if((Hash $destination) -ne $file.before_sha256) {throw 'Destination changed during installation'}
            $save=UnderRoot $backup $file.relative_path
            if(Test-Path -LiteralPath $save) {throw 'Preserve previous backup before retrying'}
            New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($save)) -Force | Out-Null
            Copy-Item -LiteralPath $destination -Destination $save
            if((Hash $save) -ne $file.before_sha256) {throw 'Backup verification failed'}
        }
        $temporary=$destination+'.codex-npu-stage'
        if(Test-Path -LiteralPath $temporary) {throw 'Preserve partial staged file before retrying'}
        New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($destination)) -Force | Out-Null
        Copy-Item -LiteralPath $file.source -Destination $temporary
        if((Hash $temporary) -ne $file.sha256) {throw 'Staged file verification failed'}
        NoCemu
        # Both absolute paths were checked under the fixed emulator directory.
        Move-Item -LiteralPath $temporary -Destination $destination -Force
        if((Hash $destination) -ne $file.sha256) {throw 'Installed file verification failed'}
        $installed+=$file.relative_path
    }
    foreach($file in $plan.files) {if((Hash (UnderRoot $target $file.relative_path)) -ne $file.sha256) {throw 'Final file verification failed'}}
    foreach($file in $plan.protected_executables) {if((Hash (UnderRoot $target $file.relative_path)) -ne $file.sha256) {throw 'Protected executable changed'}}
    if(Test-Path -LiteralPath (Join-Path $target 'portable')) {throw 'Unexpected portable mode directory'}
    [pscustomobject]@{module_abi=3;source_manifest_sha256=$plan.source_manifest_sha256;files=$plan.files;compatible_executables=@('Cemu-Release-NPU.exe','Cemu-Release-SE-NPU.exe');settings_mode='Existing AppData mode; portable directory not created'} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $runtimeManifest -Encoding UTF8
    $result=[pscustomobject]@{status='NPU_RUNTIME_INSTALLED_AND_HASH_VERIFIED';target=$target;files=$installed.Count;bytes=$bytes;identical_files_preserved=$preserved.Count;files_written=($installed.Count-$preserved.Count);module_abi=3;existing_release_executable_preserved=$true;user_data_modified=$false;cemu_gpu_npu_executed=$false;game_test_pending=$true;backup=$backup;finished_at=(Get-Date).ToString('o')}
    $result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $receipt -Encoding UTF8
    $result | ConvertTo-Json -Depth 5
} catch {
    [pscustomobject]@{status='INSTALL_INCOMPLETE';installed_files=$installed;error=$_.Exception.Message;no_processes_stopped=$true} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (UnderRoot $evidenceRoot 'install-error.json') -Encoding UTF8
    throw
}
