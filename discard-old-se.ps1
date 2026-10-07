$ErrorActionPreference = 'Stop'
$catalogRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'Cemu-versions'))
$targets = @(
    @{ Path='C:\Emulators\Cemu_arm64\Cemu_se.exe'; Hash='17231aa75f907d3804b27ee40762e9940c70443f33ca807157b80790fcb4d496' },
    @{ Path=(Join-Path $catalogRoot 'Release+SE/binaries/run-35399518440/Cemu.exe'); Hash='17231aa75f907d3804b27ee40762e9940c70443f33ca807157b80790fcb4d496' },
    @{ Path=(Join-Path $catalogRoot 'Release+SE/archives/cemu-arm64-release-run-35399518440.zip'); Hash='e55436daec5f25adcc4967f48cec6fb7c65745a4d1b8be34257cf4e949bb4477' }
)
$finalPath='C:\Emulators\Cemu_arm64\Cemu_se_test.exe'
$finalExpected='e8791dbea63e85111c1b9a4feab98f31ca469b1802caf379aa5120cffa2dc9c8'
if ((Get-FileHash -LiteralPath $finalPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $finalExpected) { throw 'Final SE changed; stop before discarding anything.' }
foreach ($target in $targets) {
    $target.Path=[System.IO.Path]::GetFullPath($target.Path)
    if (-not (Test-Path -LiteralPath $target.Path -PathType Leaf)) { throw "Discard target missing: $($target.Path)" }
    if ((Get-FileHash -LiteralPath $target.Path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $target.Hash) { throw "Discard target hash mismatch: $($target.Path)" }
}
Add-Type -AssemblyName Microsoft.VisualBasic
$records=@()
foreach ($target in $targets) {
    [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($target.Path, [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs, [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin, [Microsoft.VisualBasic.FileIO.UICancelOption]::ThrowException)
    if (Test-Path -LiteralPath $target.Path) { throw "Discard target still exists: $($target.Path)" }
    $records += [ordered]@{ path=$target.Path; sha256=$target.Hash; action='sent to Recycle Bin at user request'; discarded_at=[DateTimeOffset]::Now.ToString('o') }
    Write-Output "DISCARDED $($target.Path)"
}
if ((Get-FileHash -LiteralPath $finalPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $finalExpected) { throw 'Final SE verification failed after discard.' }
$records | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $catalogRoot 'evidence/discarded-old-se.json') -Encoding utf8
Write-Output 'Final Cemu_se_test.exe preserved; SHA-256 unchanged.'
