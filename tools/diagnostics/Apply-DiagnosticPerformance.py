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

# ARM64 texture hash NEON A/B experiment.
# Default behavior is unchanged. On AArch64, texture-hash-neon mirrors the
# existing x64 AVX2 huge-uncompressed-texture sampling scheme: 32-byte XOR
# samples every 288 bytes, reduced by summing eight 32-bit lanes.
p = Path("src/Cafe/HW/Latte/Core/LatteTextureCache.cpp")
t = p.read_text(encoding="utf-8")
t = ensure_include(t, '#include "Common/cpu_features.h"\n', '#include "Cafe/HW/Latte/Renderer/Renderer.h"\n', '#include "diagnostics/RuntimeExperiments.h"\n', "texture hash experiment include")
if '#include <arm_neon.h>\n' not in t:
    t = replace_once(
        t,
        '#include "diagnostics/RuntimeExperiments.h"\n',
        '#include "diagnostics/RuntimeExperiments.h"\n#if defined(__aarch64__)\n#include <arm_neon.h>\n#endif\n',
        "texture hash NEON include",
    )
neon_anchor = '''#else
\t\t\tif( false ) {}
#endif
\t\t\telse
'''
neon_block = '''#elif defined(__aarch64__)
\t\t\tstatic const bool expNeonTextureHash = RuntimeExperiments::Enabled("texture-hash-neon");
\t\t\tif (expNeonTextureHash)
\t\t\t{
\t\t\t\tuint32x4_t h128a = vdupq_n_u32(0);
\t\t\t\tuint32x4_t h128b = vdupq_n_u32(0);
\t\t\t\tconst uint8* readPtr = reinterpret_cast<const uint8*>(texDataU32);
\t\t\t\tuint32 sampleCount = memRange / 288;
\t\t\t\twhile (sampleCount--)
\t\t\t\t{
\t\t\t\t\th128a = veorq_u32(h128a, vld1q_u32(reinterpret_cast<const uint32*>(readPtr)));
\t\t\t\t\th128b = veorq_u32(h128b, vld1q_u32(reinterpret_cast<const uint32*>(readPtr + 16)));
\t\t\t\t\treadPtr += 288;
\t\t\t\t}
\t\t\t\thashVal = vaddvq_u32(h128a) + vaddvq_u32(h128b);
\t\t\t}
#else
\t\t\tif( false ) {}
#endif
\t\t\telse
'''
t = replace_once(t, neon_anchor, neon_block, "ARM64 texture hash NEON branch")
p.write_text(t, encoding="utf-8", newline="\n")

# PPC thread profiler cadence A/B diagnostic.
# Keep the suspend-completion polling at 1 ms, but reduce only the outer
# observation cadence from 1 ms to 10 ms to minimize profiler-induced FPS loss.
p = Path("src/gui/wxgui/windows/PPCThreadsViewer/DebugPPCThreadsWindow.cpp")
t = p.read_text(encoding="utf-8")
t = replace_once(
    t,
    '\t\tstd::this_thread::sleep_for(std::chrono::milliseconds(1));\n\t}\n\n\tauto pct = [observationCount](uint64 value) -> double {',
    '\t\tstd::this_thread::sleep_for(std::chrono::milliseconds(10));\n\t}\n\n\tauto pct = [observationCount](uint64 value) -> double {',
    "PPC profiler outer sampling cadence",
)
p.write_text(t, encoding="utf-8", newline="\n")

# Map the stable BOTW guest-PC hotspots to their exact AArch64 JIT entrypoints.
# This is report-only and runs only when jit-hotspot-native is explicitly enabled.
p = Path("src/gui/wxgui/windows/PPCThreadsViewer/DebugPPCThreadsWindow.cpp")
t = p.read_text(encoding="utf-8")
t = ensure_include(
    t,
    '#include "Cafe/OS/RPL/rpl_symbol_storage.h"\n',
    '#include "DebugPPCThreadsWindow.h"\n',
    '#include "Cafe/HW/Espresso/Recompiler/PPCRecompiler.h"\n#include "diagnostics/RuntimeExperiments.h"\n',
    "PPC profiler JIT hotspot includes",
)
hotspot_anchor = '''\t\tcemuLog_log(LogType::Force, "[{:08x}] {:8.2f}% (Samples: {:5}) Symbol: {}", sample.first,
\t\t\t\t\t(double)(sample.second * 100) / (double)totalSampleCount, sample.second, strName);
'''
hotspot_block = '''\t\tcemuLog_log(LogType::Force, "[{:08x}] {:8.2f}% (Samples: {:5}) Symbol: {}", sample.first,
\t\t\t\t\t(double)(sample.second * 100) / (double)totalSampleCount, sample.second, strName);

\t\tif (RuntimeExperiments::Enabled("jit-hotspot-native") &&
\t\t\t(sample.first == 0x0420CB80 || sample.first == 0x02A281A0 || sample.first == 0x03B84854 ||
\t\t\t sample.first == 0x0399B4DC || sample.first == 0x03818C6C))
\t\t{
\t\t\tPPCREC_JUMP_ENTRY nativeEntry = nullptr;
\t\t\tif (ppcRecompilerInstanceData != nullptr && sample.first < PPC_REC_CODE_AREA_END)
\t\t\t\tnativeEntry = ppcRecompilerInstanceData->ppcRecompilerDirectJumpTable[sample.first / 4];

\t\t\tconst bool nativeValid = nativeEntry != nullptr &&
\t\t\t\tnativeEntry != PPCRecompiler_leaveRecompilerCode_unvisited &&
\t\t\t\tnativeEntry != PPCRecompiler_leaveRecompilerCode_visited;
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[JIT_HOTSPOT_MAP] guest=0x{:08x} native=0x{:016x} valid={}",
\t\t\t\tsample.first, (uint64)(uintptr_t)nativeEntry, nativeValid);

\t\t\tif (nativeValid)
\t\t\t{
\t\t\t\tconst uint32* nativeWords = reinterpret_cast<const uint32*>(nativeEntry);
\t\t\t\tfor (uint32 nativeOffset = 0; nativeOffset < 128; nativeOffset += 16)
\t\t\t\t{
\t\t\t\t\tconst uint32 wordIndex = nativeOffset / 4;
\t\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\t"[JIT_HOTSPOT_CODE] guest=0x{:08x} native_off=0x{:03x} {:08x} {:08x} {:08x} {:08x}",
\t\t\t\t\t\tsample.first, nativeOffset,
\t\t\t\t\t\tnativeWords[wordIndex + 0], nativeWords[wordIndex + 1],
\t\t\t\t\t\tnativeWords[wordIndex + 2], nativeWords[wordIndex + 3]);
\t\t\t\t}
\t\t\t}
\t\t}
'''
t = replace_once(t, hotspot_anchor, hotspot_block, "PPC profiler JIT hotspot native mapping")
p.write_text(t, encoding="utf-8", newline="\n")

print("[diagnostics-performance] installed")
