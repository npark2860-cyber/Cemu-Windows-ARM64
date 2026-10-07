$ErrorActionPreference = 'Stop'
$taskWorkspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$taskSettingsPath = Join-Path $taskWorkspace 'Cemu-versions\NPU-Promotion\Release\runtime\portable\settings.xml'
$taskEntryPath = Join-Path $PSScriptRoot 'evidence\resolution-entry.xml'
$taskPack = 'graphicPacks/downloadedGraphicPacks/Bayonetta_Resolution/rules.txt'
if (Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^Cemu' }) {
    throw 'Close Cemu normally before restoring its settings.'
}
$taskText = [IO.File]::ReadAllText($taskSettingsPath)
[xml]$taskXml = $taskText
if (@($taskXml.content.GraphicPack.Entry | Where-Object { $_.filename -eq $taskPack }).Count) {
    Write-Output 'Bayonetta resolution pack is already enabled. No changes made.'
    return
}
$taskSavedEntry = [IO.File]::ReadAllText($taskEntryPath)
if ([regex]::Matches($taskText, '</GraphicPack>').Count -ne 1) {
    throw 'Unexpected settings structure. No changes made.'
}
$taskNewText = $taskText.Replace('</GraphicPack>', $taskSavedEntry + '</GraphicPack>')
[xml]$taskCheckedXml = $taskNewText
$taskStamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
Copy-Item -LiteralPath $taskSettingsPath -Destination (Join-Path $PSScriptRoot ('evidence\settings-before-restore-' + $taskStamp + '.xml'))
[IO.File]::WriteAllText($taskSettingsPath, $taskNewText, [Text.UTF8Encoding]::new($false))
Write-Output 'Restored only the Bayonetta 1 resolution pack and its saved 1080p preset.'
