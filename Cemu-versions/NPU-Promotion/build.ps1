param([Parameter(Mandatory=$true)][ValidateSet('Release','Release+SE','Diagnostics','Diagnostics+SE')][string]$Variant,
      [ValidatePattern('^[a-z][a-z0-9-]*$')][string]$Pass='build')
$ErrorActionPreference='Stop'
$PSNativeCommandUseErrorActionPreference=$false
$base=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot $Variant)).Path
if(-not (Test-Path -LiteralPath (Join-Path $base 'evidence/integrated.json'))) {throw 'Integrate and audit this variant first'}
$log=Join-Path $base ('evidence/'+$Pass+'.log')
if(Test-Path -LiteralPath $log) {throw 'Preserve existing build log; choose a new explicit -Pass for retries'}
$original=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../Test/LSFG-Release')).Path
foreach($name in @('toolchain','compiler-rt','vcpkg-installed')) {
    $target=(Get-Item -LiteralPath (Join-Path $original $name)).Target
    $link=Join-Path $base $name
    if(Test-Path -LiteralPath $link) {
        if((Get-Item -LiteralPath $link).Target -ne $target) {throw ('Unexpected build resource link: '+$link)}
    } else {New-Item -ItemType Junction -Path $link -Target $target | Out-Null}
}
if(-not ('NpuPromotionDosDevice' -as [type])) {Add-Type -TypeDefinition 'using System; using System.Text; using System.Runtime.InteropServices; public static class NpuPromotionDosDevice { [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] public static extern uint QueryDosDevice(string name,StringBuilder target,int length); }'}
function ReadBuildMapping {
    $buffer=[System.Text.StringBuilder]::new(32768)
    if([NpuPromotionDosDevice]::QueryDosDevice('Q:',$buffer,$buffer.Capacity) -eq 0) {return ''}
    return $buffer.ToString()
}
$expected='\??\'+$base
$created=$false
if(ReadBuildMapping) {
    if((ReadBuildMapping) -ne $expected) {throw 'Q: is already in use; do not replace an active build mapping'}
} else {
    & subst Q: $base
    if($LASTEXITCODE -ne 0) {throw 'Could not map the build directory'}
    $created=$true
}
try {
    if((ReadBuildMapping) -ne $expected) {throw 'Unexpected build mapping'}
    & (Join-Path $PSScriptRoot 'build.cmd') *> $log
    $buildExit=$LASTEXITCODE
    Get-Content -LiteralPath $log -Tail 12
    [pscustomobject]@{variant=$Variant;pass=$Pass;exit_code=$buildExit;finished_at=(Get-Date).ToString('o');device_executed=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $base ('evidence/'+$Pass+'-result.json')) -Encoding UTF8
    if($buildExit -ne 0) {throw ('Build failed: '+$Variant+' exit='+$buildExit)}
} finally {
    if($created -and (ReadBuildMapping) -eq $expected) { & subst Q: /D }
}
