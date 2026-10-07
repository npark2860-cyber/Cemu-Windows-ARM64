$ErrorActionPreference='Stop'
$PSNativeCommandUseErrorActionPreference=$false
$base=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../LSFG-Release')).Path
Add-Type -TypeDefinition 'using System; using System.Text; using System.Runtime.InteropServices; public static class NpuBuildDosDevice { [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] public static extern uint QueryDosDevice(string name,StringBuilder target,int length); }'
function ReadBuildMapping {
    $buffer=[System.Text.StringBuilder]::new(32768)
    if([NpuBuildDosDevice]::QueryDosDevice('Q:',$buffer,$buffer.Capacity) -eq 0) {return ''}
    return $buffer.ToString()
}
$expected='\??\'+$base
$created=$false
if(Test-Path -LiteralPath 'Q:\') {
    if((ReadBuildMapping) -ne $expected) {throw 'Q: is already in use by a different path; will not replace it'}
} else {
    & subst Q: $base
    if($LASTEXITCODE -ne 0) {throw 'Could not map the existing build cache root'}
    $created=$true
}
try {
    if((ReadBuildMapping) -ne $expected) {throw 'Unexpected drive mapping'}
    & (Join-Path $PSScriptRoot 'build-cemu.cmd') *> (Join-Path $PSScriptRoot '../evidence/cemu-npu-build-v1.log')
    $buildExit=$LASTEXITCODE
    Get-Content -LiteralPath (Join-Path $PSScriptRoot '../evidence/cemu-npu-build-v1.log') -Tail 30
    if($buildExit -ne 0) {throw ('Cemu compile failed with exit '+$buildExit)}
} finally {
    # Remove only the temporary DOS drive mapping created above, never its files.
    if($created -and (ReadBuildMapping) -eq $expected) { & subst Q: /D }
}
