from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


def ensure_include(text, preferred_anchor, fallback_anchor, include_line, label):
    if include_line in text:
        return text
    if preferred_anchor in text:
        return text.replace(preferred_anchor, preferred_anchor + include_line, 1)
    if fallback_anchor in text:
        return text.replace(fallback_anchor, fallback_anchor + include_line, 1)
    raise RuntimeError(f"{label}: include anchor not found")


# AArch64 JIT compile/readyRE performance counters
p = Path("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp")
t = p.read_text(encoding="utf-8")
t = ensure_include(t, '#include "HW/Espresso/PPCState.h"\n', '#include "Common/precompiled.h"\n', '#include "diagnostics/RuntimeDiagnostics.h"\n', "AArch64 diag include")
t = replace_once(t,
    'bool PPCRecompiler_generateAArch64Code(struct PPCRecFunction_t* PPCRecFunction, struct ppcImlGenContext_t* ppcImlGenContext)\n{\n',
    'bool PPCRecompiler_generateAArch64Code(struct PPCRecFunction_t* PPCRecFunction, struct ppcImlGenContext_t* ppcImlGenContext)\n{\n\tRuntimeDiagnostics::ScopedJitCompile diagJitCompile;\n',
    "JIT timing scope")
t = replace_once(t,
    '\taarch64GenContext.readyRE();\n\n\t// set code\n',
    '\taarch64GenContext.readyRE();\n\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::JitPerformance) || RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ReadyReICache))\n\t{\n\t\tRuntimeDiagnostics::g_jitReadyReCount.fetch_add(1, std::memory_order_relaxed);\n\t\tRuntimeDiagnostics::NoteEvent();\n\t}\n\n\t// set code\n',
    "readyRE counter")
p.write_text(t, encoding="utf-8", newline="\n")

# Pipeline compile timing
p = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp")
t = p.read_text(encoding="utf-8")
t = ensure_include(t, '#include "diagnostics/RuntimeExperiments.h"\n', '#include "HW/Latte/Renderer/RendererCore.h"\n', '#include "diagnostics/RuntimeDiagnostics.h"\n', "pipeline diag include")
t = replace_once(t,
    'bool PipelineCompiler::Compile(bool forceCompile, bool isRenderThread, bool showInOverlay)\n{\n',
    'bool PipelineCompiler::Compile(bool forceCompile, bool isRenderThread, bool showInOverlay)\n{\n\tRuntimeDiagnostics::ScopedPipelineCompile diagPipelineCompile;\n',
    "pipeline timing scope")
p.write_text(t, encoding="utf-8", newline="\n")

# Descriptor cache/update/bind and draw counters
p = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
t = p.read_text(encoding="utf-8")
t = ensure_include(t, '#include "diagnostics/RuntimeExperiments.h"\n', '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"\n', '#include "diagnostics/RuntimeDiagnostics.h"\n', "core diag include")
t = replace_once(t,
    '\tif (it != ds_cache.cend())\n\t\treturn it->second;\n',
    '\tif (it != ds_cache.cend())\n\t{\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DescriptorStats))\n\t\t\tRuntimeDiagnostics::g_descriptorCacheHits.fetch_add(1, std::memory_order_relaxed);\n\t\treturn it->second;\n\t}\n\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DescriptorStats))\n\t\tRuntimeDiagnostics::g_descriptorCacheMisses.fetch_add(1, std::memory_order_relaxed);\n',
    "descriptor hit miss")
t = replace_once(t,
    '\tVkDescriptorSetInfo* dsInfo = new VkDescriptorSetInfo();\n',
    '\tVkDescriptorSetInfo* dsInfo = new VkDescriptorSetInfo();\n\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DescriptorStats))\n\t\tRuntimeDiagnostics::g_descriptorAlloc.fetch_add(1, std::memory_order_relaxed);\n',
    "descriptor allocation")
t = replace_once(t,
    '\tif (!descriptorWrites.empty())\n\t\tvkUpdateDescriptorSets(m_logicalDevice, (uint32)descriptorWrites.size(), descriptorWrites.data(), 0, nullptr);\n',
    '\tif (!descriptorWrites.empty())\n\t{\n\t\tvkUpdateDescriptorSets(m_logicalDevice, (uint32)descriptorWrites.size(), descriptorWrites.data(), 0, nullptr);\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DescriptorStats))\n\t\t\tRuntimeDiagnostics::AddDescriptorWrite(descriptorWrites.size());\n\t}\n',
    "descriptor update")

bind_patterns = [
    'vkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 0, 2, dsArray, numDynOffsetsVS + numDynOffsetsPS, dynamicOffsets);',
    'vkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 0, 1, &vertexDS->m_vkObjDescriptorSet->descriptorSet, numDynOffsets, dynamicOffsets);',
    'vkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 1, 1, &pixelDS->m_vkObjDescriptorSet->descriptorSet, numDynOffsets, dynamicOffsets);',
    'vkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 2, 1, &geometryDS->m_vkObjDescriptorSet->descriptorSet, numDynOffsets, dynamicOffsets);',
    'vkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, dsArrayBase, dsArraySize, dsArray, numDynOffsets, dynamicOffsets);',
]
for pattern in bind_patterns:
    if pattern in t:
        t = t.replace(pattern, pattern + '\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DescriptorStats)) RuntimeDiagnostics::g_descriptorBinds.fetch_add(1, std::memory_order_relaxed);')

t = t.replace(
    '\tLatteGPUState.drawCallCounter++;\n',
    '\tLatteGPUState.drawCallCounter++;\n\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DrawCallCount) || RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::HitchTrigger)) RuntimeDiagnostics::g_frameDraws.fetch_add(1, std::memory_order_relaxed);\n')
p.write_text(t, encoding="utf-8", newline="\n")

# Upload/copy byte counters
p = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
t = p.read_text(encoding="utf-8")
t = ensure_include(t, '#include "diagnostics/RuntimeExperiments.h"\n', '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"\n', '#include "diagnostics/RuntimeDiagnostics.h"\n', "renderer diag include")
t = replace_once(t,
    'void VulkanRenderer::bufferCache_upload(uint8* buffer, sint32 size, uint32 bufferOffset)\n{\n',
    'void VulkanRenderer::bufferCache_upload(uint8* buffer, sint32 size, uint32 bufferOffset)\n{\n\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::MemoryUploadStats) && size > 0)\n\t\tRuntimeDiagnostics::AddUploadBytes((uint64_t)size);\n',
    "buffer upload bytes")
t = replace_once(t,
    'void VulkanRenderer::bufferCache_copy(uint32 srcOffset, uint32 dstOffset, uint32 size)\n{\n',
    'void VulkanRenderer::bufferCache_copy(uint32 srcOffset, uint32 dstOffset, uint32 size)\n{\n\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::MemoryUploadStats))\n\t\tRuntimeDiagnostics::AddCopyBytes(size);\n',
    "buffer copy bytes")
p.write_text(t, encoding="utf-8", newline="\n")
print("[diagnostics-performance] installed")
