$ErrorActionPreference = 'Stop'
$base = Join-Path $PSScriptRoot 'Cemu-versions\Release\source'
$lab = Join-Path $PSScriptRoot 'Cemu-versions\Test\LSFG-Release'
$source = Join-Path $lab 'source'
$expected = 'c5205ccbc8ffe41129fbe921b5420a79ff283216'
if ((& git -C $base rev-parse HEAD).Trim() -ne $expected) { throw 'Wrong stock source' }
if (Test-Path -LiteralPath $source) { throw 'Experiment source already exists' }
function Git-Checked {
    param([string[]]$GitArgs)
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "Git failed: $($GitArgs -join ' ')" }
}
Git-Checked @('clone','--shared','--no-checkout',$base,$source)
Git-Checked @('-C',$source,'checkout','-b','codex/lsfg-release',$expected)
Git-Checked @('-C',$source,'remote','set-url','origin','https://github.com/npark2860-cyber/Cemu-Windows-ARM64.git')
function Copy-LocalSubmodules([string]$From, [string]$To) {
    $entries = @(& git -C $From ls-files --stage)
    foreach ($entry in $entries) {
        if ($entry -match '^160000 ([0-9a-f]{40}) 0\t(.+)$') {
            $revision = $Matches[1]; $relative = $Matches[2]
            $fromChild = Join-Path $From $relative
            $toChild = Join-Path $To $relative
            Git-Checked @('clone','--shared','--no-checkout',$fromChild,$toChild)
            Git-Checked @('-C',$toChild,'checkout','--detach',$revision)
            Copy-LocalSubmodules $fromChild $toChild
        }
    }
}
Copy-LocalSubmodules $base $source
$zip = 'C:\Users\angel\Documents\ChatGPT\Lossless Scaling ARM64\build\lsfg-cemu-arm64-windows-arm64-20260928.zip'
Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $lab 'package-original')
[pscustomobject]@{baseline_commit=$expected; branch='codex/lsfg-release'; source=$source; baseline_source=$base; package_sha256=(Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant(); created_at=(Get-Date).ToString('o'); note='Independent checkout; shared Git object store depends on retained baseline source. No baseline source modified.'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $lab 'evidence\source-origin.json') -Encoding utf8
