from pathlib import Path

def replace_once(text, old, new, label):
    count=text.count(old)
    if count!=1: raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old,new,1)

p=Path("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp")
t=p.read_text(encoding="utf-8")
t=replace_once(t,'#include "HW/Espresso/PPCState.h"\n','#include "HW/Espresso/PPCState.h"\n#include "diagnostics/RuntimeDiagnostics.h"\n',"AArch64 diag include")
t=replace_once(t,'bool PPCRecompiler_generateAArch64Code(struct PPCRecFunction_t* PPCRecFunction, struct ppcImlGenContext_t* ppcImlGenContext)\n{\n','''bool PPCRecompiler_generateAArch64Code(struct PPCRecFunction_t* PPCRecFunction, struct ppcImlGenContext_t* ppcImlGenContext)
{
\tRuntimeDiagnostics::ScopedJitCompile diagJitCompile;
''',"JIT timing scope")
t=replace_once(t,'\taarch64GenContext.readyRE();\n\n\t// set code\n','''\taarch64GenContext.readyRE();
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::JitPerformance) || RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ReadyReICache))
\t{
\t\tRuntimeDiagnostics::g_jitReadyReCount.fetch_add(1, std::memory_order_relaxed);
\t\tRuntimeDiagnostics::NoteEvent();
\t}

\t// set code
''',"readyRE counter")
p.write_text(t,encoding="utf-8",newline="\n")

p=Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp")
t=p.read_text(encoding="utf-8")
t=replace_once(t,'#include "HW/Latte/Renderer/RendererCore.h"\n','#include "HW/Latte/Renderer/RendererCore.h"\n#include "diagnostics/RuntimeDiagnostics.h"\n',"pipeline diag include")
t=replace_once(t,'bool PipelineCompiler::Compile(bool forceCompile, bool isRenderThread, bool showInOverlay)\n{\n','''bool PipelineCompiler::Compile(bool forceCompile, bool isRenderThread, bool showInOverlay)
{
\tRuntimeDiagnostics::ScopedPipelineCompile diagPipelineCompile;
''',"pipeline timing scope")
p.write_text(t,encoding="utf-8",newline="\n")

p=Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
t=p.read_text(encoding="utf-8")
if '#include "diagnostics/RuntimeExperiments.h"\n' in t:
    t=replace_once(t,'#include "diagnostics/RuntimeExperiments.h"\n','#include "diagnostics/RuntimeExperiments.h"\n#include "diagnostics/RuntimeDiagnostics.h"\n',"core diag include")
else:
    t=replace_once(t,'#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"\n','#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"\n#include "diagnostics/RuntimeDiagnostics.h"\n',"core diag include fallback")
t=replace_once(t,'\tif (it != ds_cache.cend())\n\t\treturn it->second;\n','''\tif (it != ds_cache.cend())
\t{
\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DescriptorStats))
\t\t\tRuntimeDiagnostics::g_descriptorCacheHits.fetch_add(1, std::memory_order_relaxed);
\t\treturn it->second;
\t}
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DescriptorStats))
\t\tRuntimeDiagnostics::g_descriptorCacheMisses.fetch_add(1, std::memory_order_relaxed);
''',"descriptor hit miss")
t=replace_once(t,'\tVkDescriptorSetInfo* dsInfo = new VkDescriptorSetInfo();\n','''\tVkDescriptorSetInfo* dsInfo = new VkDescriptorSetInfo();
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DescriptorStats))
\t\tRuntimeDiagnostics::g_descriptorAlloc.fetch_add(1, std::memory_order_relaxed);
''',"descriptor allocation")
t=replace_once(t,'\tif (!descriptorWrites.empty())\n\t\tvkUpdateDescriptorSets(m_logicalDevice, (uint32)descriptorWrites.size(), descriptorWrites.data(), 0, nullptr);\n','''\tif (!descriptorWrites.empty())
\t{
\t\tvkUpdateDescriptorSets(m_logicalDevice, (uint32)descriptorWrites.size(), descriptorWrites.data(), 0, nullptr);
\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DescriptorStats))
\t\t\tRuntimeDiagnostics::AddDescriptorWrite(descriptorWrites.size());
\t}
''',"descriptor update")
repls = [
('\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 0, 2, dsArray, numDynOffsetsVS + numDynOffsetsPS, dynamicOffsets);','\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 0, 2, dsArray, numDynOffsetsVS + numDynOffsetsPS, dynamicOffsets);\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DescriptorStats)) RuntimeDiagnostics::g_descriptorBinds.fetch_add(1, std::memory_order_relaxed);'),
('\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 0, 1, &vertexDS->m_vkObjDescriptorSet->descriptorSet, numDynOffsets, dynamicOffsets);','\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 0, 1, &vertexDS->m_vkObjDescriptorSet->descriptorSet, numDynOffsets, dynamicOffsets);\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DescriptorStats)) RuntimeDiagnostics::g_descriptorBinds.fetch_add(1, std::memory_order_relaxed);'),
('\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 1, 1, &pixelDS->m_vkObjDescriptorSet->descriptorSet, numDynOffsets, dynamicOffsets);','\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 1, 1, &pixelDS->m_vkObjDescriptorSet->descriptorSet, numDynOffsets, dynamicOffsets);\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DescriptorStats)) RuntimeDiagnostics::g_descriptorBinds.fetch_add(1, std::memory_order_relaxed);'),
('\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 2, 1, &geometryDS->m_vkObjDescriptorSet->descriptorSet, numDynOffsets, dynamicOffsets);','\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 2, 1, &geometryDS->m_vkObjDescriptorSet->descriptorSet, numDynOffsets, dynamicOffsets);\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DescriptorStats)) RuntimeDiagnostics::g_descriptorBinds.fetch_add(1, std::memory_order_relaxed);'),
('\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, dsArrayBase, dsArraySize, dsArray, numDynOffsets, dynamicOffsets);','\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, dsArrayBase, dsArraySize, dsArray, numDynOffsets, dynamicOffsets);\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DescriptorStats)) RuntimeDiagnostics::g_descriptorBinds.fetch_add(1, std::memory_order_relaxed);')]
for old,new in repls:
    t=t.replace(old,new)
t=t.replace('\tLatteGPUState.drawCallCounter++;\n', '\tLatteGPUState.drawCallCounter++;\n\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DrawCallCount) || RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::HitchTrigger)) RuntimeDiagnostics::g_frameDraws.fetch_add(1, std::memory_order_relaxed);\n')
p.write_text(t,encoding="utf-8",newline="\n")

p=Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
t=p.read_text(encoding="utf-8")
if '#include "diagnostics/RuntimeExperiments.h"\n' in t:
    t=replace_once(t,'#include "diagnostics/RuntimeExperiments.h"\n','#include "diagnostics/RuntimeExperiments.h"\n#include "diagnostics/RuntimeDiagnostics.h"\n',"renderer diag include")
else:
    t=replace_once(t,'#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"\n','#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"\n#include "diagnostics/RuntimeDiagnostics.h"\n',"renderer diag include fallback")
t=replace_once(t,'void VulkanRenderer::bufferCache_upload(uint8* buffer, sint32 size, uint32 bufferOffset)\n{\n','''void VulkanRenderer::bufferCache_upload(uint8* buffer, sint32 size, uint32 bufferOffset)
{
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::MemoryUploadStats) && size > 0)
\t\tRuntimeDiagnostics::AddUploadBytes((uint64_t)size);
''',"buffer upload bytes")
t=replace_once(t,'void VulkanRenderer::bufferCache_copy(uint32 srcOffset, uint32 dstOffset, uint32 size)\n{\n','''void VulkanRenderer::bufferCache_copy(uint32 srcOffset, uint32 dstOffset, uint32 size)
{
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::MemoryUploadStats))
\t\tRuntimeDiagnostics::AddCopyBytes(size);
''',"buffer copy bytes")
p.write_text(t,encoding="utf-8",newline="\n")
print("[diagnostics-performance] installed")
