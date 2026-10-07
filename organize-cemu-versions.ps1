param([switch]$InitializeSubmodules)
$ErrorActionPreference = 'Stop'
$repoUrl = 'https://github.com/npark2860-cyber/Cemu-Windows-ARM64.git'
$catalogRoot = Join-Path $PSScriptRoot 'Cemu-versions'
$roles = @(
    @{ Role='Release'; Branch='final-adreno-compat-arm64'; Commit='c5205ccbc8ffe41129fbe921b5420a79ff283216' },
    @{ Role='Release+SE'; Branch='Release+SE'; Commit='240b52c853f3d8a7b111c74dd95277ba50866204' },
    @{ Role='Diagnostics'; Branch='fix/arm64-diagnostics-ui-artifact-gate'; Commit='6aa13388289ed41c2f7c802c5b096b142dc1b4c8' },
    @{ Role='Diagnostics+SE'; Branch='feat/enhanced-sound-experience-v1'; Commit='b18d8faae5a4b2316974ef4907e0739a9e3a5c2b' },
    @{ Role='Test'; Branch='test/se-fingerprint-index-v1'; Commit='668acee48ae048a86d663546b56ca5494ae1a77c' }
)
New-Item -ItemType Directory -Path $catalogRoot -Force | Out-Null
foreach ($role in $roles) {
    $sourcePath = Join-Path (Join-Path $catalogRoot $role.Role) 'source'
    if (-not (Test-Path -LiteralPath $sourcePath)) {
        Write-Output "CLONE $($role.Role) <- $($role.Branch)"
        & git -c core.longpaths=true clone --quiet --depth 1 --single-branch --branch $role.Branch -- $repoUrl $sourcePath
        if ($LASTEXITCODE -ne 0) { throw "Clone failed: $($role.Role)" }
    }
    $actualCommit = (& git -C $sourcePath rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $actualCommit -ne $role.Commit) { throw "Commit mismatch for $($role.Role): $actualCommit. Review remote changes before continuing." }
    $actualBranch = (& git -C $sourcePath branch --show-current).Trim()
    $actualRemote = (& git -C $sourcePath remote get-url origin).Trim()
    if ($actualBranch -ne $role.Branch -or $actualRemote -ne $repoUrl) { throw "Identity mismatch: $($role.Role)" }
    & git -C $sourcePath config core.longpaths true
    if ($InitializeSubmodules) {
        Write-Output "SUBMODULES $($role.Role)"
        & git -C $sourcePath -c core.longpaths=true submodule update --init --recursive --depth 1 --jobs 4
        if ($LASTEXITCODE -ne 0) { throw "Submodule initialization failed: $($role.Role)" }
    }
    $status = @(& git -C $sourcePath status --porcelain)
    if ($LASTEXITCODE -ne 0 -or $status.Count -gt 0) { throw "Checkout has unexpected changes: $($role.Role)" }
    Write-Output "VERIFIED $($role.Role) $actualCommit"
}
