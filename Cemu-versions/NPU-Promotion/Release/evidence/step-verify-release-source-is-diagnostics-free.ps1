$ErrorActionPreference='Stop'
$global:LASTEXITCODE=0
$env:PYTHONIOENCODING='utf-8'
$main = Get-Content 'src/gui/wxgui/MainWindow.cpp' -Raw
if ($main.Contains('ARM64 Diagnostics') -or $main.Contains('RuntimeDiagnostics')) {
  throw 'Release UI contains diagnostics code'
}
$pipeline = Get-Content 'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp' -Raw
if ($pipeline.Contains('[ADRENO_DIAG]') -or $pipeline.Contains('RuntimeDiagnostics::')) {
  throw 'Release pipeline contains diagnostics logging code'
}
$query = Get-Content 'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanQuery.cpp' -Raw
foreach ($forbidden in @('[GPU_QUERY_VIS]', '[PS_INPUT_LINKAGE]', 'Flag::GpuOcclusionQueryVisibility', 'Flag::PSInputLinkage')) {
  if ($query.Contains($forbidden)) { throw "Release query source contains diagnostic marker: $forbidden" }
}
Write-Host 'PASS: release sources are diagnostics-free'

if($LASTEXITCODE -ne 0) {throw "Preprocessing step failed"}
