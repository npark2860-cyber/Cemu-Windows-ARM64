$ErrorActionPreference = 'Stop'
$lab = Join-Path $PSScriptRoot 'Cemu-versions\Test\LSFG-Release'
$source = Join-Path $lab 'source'
$python = 'C:\Users\angel\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$lines = [IO.File]::ReadAllLines((Join-Path $source '.github\workflows\final-adreno-compat-arm64.yml'))
$blocks = @{}
$step = ''
for ($i=0; $i -lt $lines.Length; $i++) {
    if ($lines[$i] -match '^      - name: (.+)$') { $step = $Matches[1] }
    if ($lines[$i] -eq '        run: |') {
        $body = [Collections.Generic.List[string]]::new()
        for ($j=$i+1; $j -lt $lines.Length; $j++) {
            if ($lines[$j].StartsWith('          ')) { $body.Add($lines[$j].Substring(10)) }
            elseif ($lines[$j].Trim() -eq '') { $body.Add('') }
            else { break }
        }
        $blocks[$step] = $body -join [Environment]::NewLine
    }
}
$selected = @('Apply known-good pre-e834 runtime behavior','Apply AMD FidelityFX FSR1','Apply Cemu ARM64 window branding','Verify release source is diagnostics-free')
$stepDir = Join-Path $lab 'build-steps'
New-Item -ItemType Directory -Path $stepDir -Force | Out-Null
Push-Location $source
try {
    $index = 0
    foreach ($name in $selected) {
        $index++
        if (-not $blocks.ContainsKey($name)) { throw "Missing known CI step: $name" }
        $code = $blocks[$name].Replace('python tools/', "& '$python' tools/")
        $path = Join-Path $stepDir "$index.ps1"
        [IO.File]::WriteAllText($path, '$ErrorActionPreference = ''Stop''' + [Environment]::NewLine + $code)
        & $path *> (Join-Path $lab "evidence\build-step-$index.log")
        if ($LASTEXITCODE -ne 0) { throw "Step failed: $name" }
        Write-Output "Applied: $name"
        if ($index -eq 1) {
            & $python './tools/compat/Apply-PSDefaultLinkageFix.py' *> (Join-Path $lab 'evidence\build-step-ps-linkage.log')
            if ($LASTEXITCODE -ne 0) { throw 'PS DEFAULT_VAL patch failed' }
            Write-Output 'Applied: PS DEFAULT_VAL linkage compatibility'
        }
    }
    & git diff --check
    if ($LASTEXITCODE -ne 0) { throw 'Whitespace check failed' }
    & git diff --stat
    & git diff --binary | Set-Content -LiteralPath (Join-Path $lab 'evidence\official-release-preprocessing.patch') -Encoding utf8
} finally { Pop-Location }
