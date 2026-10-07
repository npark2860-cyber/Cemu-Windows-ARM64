$ErrorActionPreference = 'Stop'
$catalogRoot = Join-Path $PSScriptRoot 'Cemu-versions'
$catalogPath = Join-Path $catalogRoot 'catalog.json'
$catalog = Get-Content -LiteralPath $catalogPath -Raw | ConvertFrom-Json
$credentialText = "protocol=https`nhost=github.com`n`n"
$credentialLines = $credentialText | & git -c credential.interactive=false credential fill 2>$null
if ($LASTEXITCODE -ne 0) { throw 'GitHub credential helper did not provide authentication.' }
$credentialPassword = $null
foreach ($credentialLine in $credentialLines) {
    if ($credentialLine.StartsWith('password=')) { $credentialPassword = $credentialLine.Substring(9) }
}
$credentialLines = $null
if (-not $credentialPassword) { throw 'No GitHub authentication was available from the credential helper.' }
$handler = [System.Net.Http.HttpClientHandler]::new()
$handler.AllowAutoRedirect = $false
$client = [System.Net.Http.HttpClient]::new($handler)
$client.Timeout = [TimeSpan]::FromMinutes(5)
$client.DefaultRequestHeaders.UserAgent.ParseAdd('Cemu-Local-Version-Catalog/1.0')
try {
    foreach ($role in $catalog.roles) {
        $roleRoot = Join-Path $catalogRoot $role.role
        $archiveDir = Join-Path $roleRoot 'archives'
        New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
        $archiveName = "$($role.build.artifact_name)-run-$($role.build.run_id).zip"
        $archivePath = Join-Path $archiveDir $archiveName
        $expectedDigest = $role.build.artifact_digest -replace '^sha256:', ''
        if (-not (Test-Path -LiteralPath $archivePath)) {
            Write-Output "DOWNLOAD $($role.role): run $($role.build.run_id), artifact $($role.build.artifact_id)"
            $request = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Get, $role.build.archive_download_url)
            $request.Headers.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new('Bearer', $credentialPassword)
            $request.Headers.Accept.ParseAdd('application/vnd.github+json')
            $response = $client.SendAsync($request).GetAwaiter().GetResult()
            $statusCode = [int]$response.StatusCode
            if ($statusCode -ne 302) { throw "GitHub artifact download failed: HTTP $statusCode for $($role.role)" }
            $downloadLocation = $response.Headers.Location
            if ($downloadLocation.Scheme -ne 'https') { throw 'Artifact redirect was not HTTPS.' }
            $request.Dispose()
            $response.Dispose()
            # The signed storage request is deliberately sent without GitHub credentials.
            $archiveResponse = $client.GetAsync($downloadLocation).GetAwaiter().GetResult()
            if (-not $archiveResponse.IsSuccessStatusCode) { throw "Artifact storage download failed: HTTP $([int]$archiveResponse.StatusCode)" }
            $stream = [System.IO.File]::Open($archivePath, [System.IO.FileMode]::CreateNew)
            try { $archiveResponse.Content.CopyToAsync($stream).GetAwaiter().GetResult() } finally { $stream.Dispose(); $archiveResponse.Dispose() }
        }
        $actualDigest = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualDigest -ne $expectedDigest) { throw "Archive SHA-256 mismatch: $($role.role)" }
        $extractPath = Join-Path $roleRoot "binaries/run-$($role.build.run_id)"
        $archive = [System.IO.Compression.ZipFile]::OpenRead($archivePath)
        try {
            $resolvedExtract = [System.IO.Path]::GetFullPath($extractPath).TrimEnd('\') + '\'
            foreach ($entry in $archive.Entries) {
                $resolvedEntry = [System.IO.Path]::GetFullPath((Join-Path $extractPath $entry.FullName))
                if (-not $resolvedEntry.StartsWith($resolvedExtract, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Archive entry escapes its version directory.' }
            }
        } finally { $archive.Dispose() }
        if (-not (Test-Path -LiteralPath $extractPath)) { [System.IO.Compression.ZipFile]::ExtractToDirectory($archivePath, $extractPath) }
        $files = @(Get-ChildItem -LiteralPath $extractPath -File -Recurse | ForEach-Object {
            [ordered]@{ path=[System.IO.Path]::GetRelativePath($extractPath, $_.FullName); size=$_.Length; sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
        })
        $role | Add-Member -Force -NotePropertyName archive_path -NotePropertyValue ([System.IO.Path]::GetRelativePath($catalogRoot, $archivePath))
        $role | Add-Member -Force -NotePropertyName binary_path -NotePropertyValue ([System.IO.Path]::GetRelativePath($catalogRoot, $extractPath))
        $role | Add-Member -Force -NotePropertyName files -NotePropertyValue $files
        $role.download_status = 'downloaded; GitHub archive SHA-256 verified'
        $catalog | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $catalogPath -Encoding utf8
        Write-Output "VERIFIED $($role.role): archive SHA-256 $actualDigest; $($files.Count) extracted files"
    }
} finally { $credentialPassword = $null; $client.Dispose(); $handler.Dispose() }
