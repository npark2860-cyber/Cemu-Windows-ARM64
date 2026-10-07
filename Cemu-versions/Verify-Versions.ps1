$ErrorActionPreference = 'Stop'
function Test-SubmoduleCommits([string]$Repository) {
    if (-not (Test-Path -LiteralPath (Join-Path $Repository '.gitmodules'))) { return }
    $entries = @(& git -C $Repository ls-files --stage)
    if ($LASTEXITCODE -ne 0) { throw "Cannot inspect submodules: $Repository" }
    foreach ($entry in $entries) {
        if ($entry -match '^160000 ([0-9a-f]{40}) 0\t(.+)$') {
            $expected = $Matches[1]
            $child = Join-Path $Repository $Matches[2]
            if (-not (Test-Path -LiteralPath (Join-Path $child '.git'))) { throw "Missing submodule: $child" }
            $actual = (& git -C $child rev-parse HEAD).Trim()
            if ($LASTEXITCODE -ne 0 -or $actual -ne $expected) { throw "Submodule commit mismatch: $child" }
            Test-SubmoduleCommits $child
        }
    }
}
$catalog = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'catalog.json') -Raw | ConvertFrom-Json
foreach ($role in $catalog.roles) {
    $source = Join-Path $PSScriptRoot $role.source_path
    $head = (& git -C $source rev-parse HEAD).Trim()
    $branch = (& git -C $source branch --show-current).Trim()
    $remote = (& git -C $source remote get-url origin).Trim()
    if ($head -ne $role.source_commit -or $branch -ne $role.branch -or $remote -ne $catalog.repository) { throw "Source identity mismatch: $($role.role)" }
    $changes = @(& git -C $source status --porcelain)
    if ($LASTEXITCODE -ne 0 -or $changes.Count) { throw "Source changed: $($role.role)" }
    Test-SubmoduleCommits $source
    $archive = Join-Path $PSScriptRoot $role.archive_path
    $zipHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ("sha256:$zipHash" -ne $role.build.artifact_digest) { throw "Archive identity mismatch: $($role.role)" }
    foreach ($file in $role.files) {
        $path = Join-Path (Join-Path $PSScriptRoot $role.binary_path) $file.path
        $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hash -ne $file.sha256) { throw "Binary file identity mismatch: $($role.role) / $($file.path)" }
    }
    Write-Output "PASS [$($role.role)] source $($head.Substring(0,12)); artifact run $($role.build.run_id); files $($role.files.Count)"
}
Write-Output 'Identity verification only. This does not certify runtime stability or LSFG correctness.'
