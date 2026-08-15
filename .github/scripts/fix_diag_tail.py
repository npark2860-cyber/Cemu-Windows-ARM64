from pathlib import Path

path = Path('.github/scripts/diag_adreno_patch.py')
s = path.read_text(encoding='utf-8')
marker = '# Both regular draw paths return early on a null VkPipeline.'
idx = s.find(marker)
if idx < 0:
    raise RuntimeError('Diagnostic tail marker not found')

prefix = s[:idx]
tail = r"""# Persist the compatibility changes made in VulkanRenderer.cpp.
write(vr, v)

# Both regular draw paths live in VulkanRendererCore.cpp, not VulkanRenderer.cpp.
# Log only null handles that came from an actual vkCreateGraphicsPipelines failure.
core = "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp"
c = read(core)
null_head = "if (vkObjPipeline->GetPipeline() == VK_NULL_HANDLE)\n\t{"
if c.count(null_head) != 2:
    raise RuntimeError(f"Expected 2 null-pipeline draw checks in VulkanRendererCore.cpp, found {c.count(null_head)}")

diag_head = '''if (vkObjPipeline->GetPipeline() == VK_NULL_HANDLE)
\t{
\t\tif (pipeline_info->diagCompileFailed.load(std::memory_order_relaxed) &&
\t\t\t!pipeline_info->diagFailureDrawLogged.exchange(true, std::memory_order_relaxed))
\t\t{
\t\t\tconst uint64 vsHash = pipeline_info->vertexShader ? pipeline_info->vertexShader->baseHash : 0;
\t\t\tconst uint64 psHash = pipeline_info->pixelShader ? pipeline_info->pixelShader->baseHash : 0;
\t\t\tconst uint64 gsHash = pipeline_info->geometryShader ? pipeline_info->geometryShader->baseHash : 0;
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[ADRENO_DIAG] FAILED_PIPELINE_DRAW_SKIPPED state={:016x} min={:016x} vs={:016x} ps={:016x} gs={:016x} prim={}",
\t\t\t\tpipeline_info->stateHash, pipeline_info->minimalStateHash, vsHash, psHash, gsHash, (uint32)pipeline_info->primitiveMode);
\t\t}'''
c = c.replace(null_head, diag_head)
write(core, c)

print("Diagnostic patch applied successfully")
"""

path.write_text(prefix + tail, encoding='utf-8', newline='\n')
print('Diagnostic script tail corrected')
