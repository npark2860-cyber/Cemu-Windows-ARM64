$ErrorActionPreference='Stop'
$python='C:/Users/angel/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:PYTHONUTF8='1'
foreach($role in @('Release+SE','Diagnostics','Diagnostics+SE')) {
    if($role -ne 'Release+SE') { & (Join-Path $PSScriptRoot 'build.ps1') -Variant $role }
    & $python (Join-Path $PSScriptRoot 'package.py') --role $role
    if($LASTEXITCODE -ne 0) {throw ('Package validation failed: '+$role)}
    & (Join-Path $PSScriptRoot 'verify-packages.ps1') -Variant $role
}
