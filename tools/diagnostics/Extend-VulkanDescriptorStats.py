from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


p = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
t = p.read_text(encoding="utf-8")

stats_anchor = '''static uint64 s_rtStatLoadRAW = 0;

static bool RTExpEnabled(std::string_view name)
'''
stats_block = '''static uint64 s_rtStatLoadRAW = 0;

// Reuse the existing Diagnostic Edition descriptor counters. This bridge only
// enables that already-instrumented report path when the dedicated env launcher
// is used, and periodically emits a compact summary. No Vulkan state changes.
static uint64 s_vkDescDiagDraws = 0;
static uint64 s_vkDescBindFirstMain = 0;
static uint64 s_vkDescBindFirstGeometry = 0;
static uint64 s_vkDescBindContinuedMain = 0;
static uint64 s_vkDescBindContinuedGeometry = 0;

static bool VkDescriptorStatsEnvEnabled()
{
\tstatic const bool enabled = RuntimeExperiments::Enabled("vk-descriptor-stats");
\tif (enabled && !RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DescriptorStats))
\t\tRuntimeDiagnostics::SetEnabled(RuntimeDiagnostics::Flag::DescriptorStats, true);
\treturn enabled;
}

static void VkDescriptorStatsNoteBind(uint32 bindClass)
{
\tif (!VkDescriptorStatsEnvEnabled())
\t\treturn;
\tswitch (bindClass)
\t{
\tcase 0: ++s_vkDescBindFirstMain; break;
\tcase 1: ++s_vkDescBindFirstGeometry; break;
\tcase 2: ++s_vkDescBindContinuedMain; break;
\tcase 3: ++s_vkDescBindContinuedGeometry; break;
\tdefault: cemu_assert_debug(false); break;
\t}
}

static void VkDescriptorStatsReportDraw()
{
\tif (!VkDescriptorStatsEnvEnabled())
\t\treturn;
\t++s_vkDescDiagDraws;
\tif ((s_vkDescDiagDraws % 10000ULL) != 0)
\t\treturn;

\tconst uint64 hits = RuntimeDiagnostics::g_descriptorCacheHits.load(std::memory_order_relaxed);
\tconst uint64 misses = RuntimeDiagnostics::g_descriptorCacheMisses.load(std::memory_order_relaxed);
\tcemuLog_log(LogType::Force,
\t\t"[VK_DESCRIPTOR_STATS] draws={} lookups={} hits={} misses={} alloc={} update_writes={} bind_calls={} bind_first_main={} bind_first_gs={} bind_cont_main={} bind_cont_gs={}",
\t\ts_vkDescDiagDraws, hits + misses, hits, misses,
\t\tRuntimeDiagnostics::g_descriptorAlloc.load(std::memory_order_relaxed),
\t\tRuntimeDiagnostics::g_descriptorUpdateWrites.load(std::memory_order_relaxed),
\t\tRuntimeDiagnostics::g_descriptorBinds.load(std::memory_order_relaxed),
\t\ts_vkDescBindFirstMain, s_vkDescBindFirstGeometry,
\t\ts_vkDescBindContinuedMain, s_vkDescBindContinuedGeometry);
}

static bool RTExpEnabled(std::string_view name)
'''
t = replace_once(t, stats_anchor, stats_block, "Vulkan descriptor stats bridge state")

lookup_anchor = '''VkDescriptorSetInfo* VulkanRenderer::draw_getOrCreateDescriptorSet(PipelineInfo* pipeline_info, LatteDecompilerShader* shader)
{
\tconst uint64 stateHash = GetDescriptorSetStateHash(shader);
'''
lookup_block = '''VkDescriptorSetInfo* VulkanRenderer::draw_getOrCreateDescriptorSet(PipelineInfo* pipeline_info, LatteDecompilerShader* shader)
{
\tVkDescriptorStatsEnvEnabled();
\tconst uint64 stateHash = GetDescriptorSetStateHash(shader);
'''
t = replace_once(t, lookup_anchor, lookup_block, "descriptor env enable hook")

first_start = t.index("void VulkanRenderer::draw_execute_first(")
continued_start = t.index("void VulkanRenderer::draw_execute_continued(", first_start)
draw_execute_start = t.index("void VulkanRenderer::draw_execute(", continued_start)
first = t[first_start:continued_start]
continued = t[continued_start:draw_execute_start]

first_combined = '''\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 0, 2, dsArray, numDynOffsetsVS + numDynOffsetsPS, dynamicOffsets);'''
first = replace_once(first, first_combined, '\t\tVkDescriptorStatsNoteBind(0);\n' + first_combined, "first combined descriptor bind class")

first_vertex = '''\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 0, 1, &vertexDS->m_vkObjDescriptorSet->descriptorSet, numDynOffsets, dynamicOffsets);'''
first = replace_once(first, first_vertex, '\t\tVkDescriptorStatsNoteBind(0);\n' + first_vertex, "first vertex descriptor bind class")

first_pixel = '''\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 1, 1, &pixelDS->m_vkObjDescriptorSet->descriptorSet, numDynOffsets, dynamicOffsets);'''
first = replace_once(first, first_pixel, '\t\tVkDescriptorStatsNoteBind(0);\n' + first_pixel, "first pixel descriptor bind class")

geometry_bind = '''\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 2, 1, &geometryDS->m_vkObjDescriptorSet->descriptorSet, numDynOffsets, dynamicOffsets);'''
first = replace_once(first, geometry_bind, '\t\tVkDescriptorStatsNoteBind(1);\n' + geometry_bind, "first geometry descriptor bind class")

continued_main = '''\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, dsArrayBase, dsArraySize, dsArray, numDynOffsets, dynamicOffsets);'''
continued = replace_once(continued, continued_main, '\t\tVkDescriptorStatsNoteBind(2);\n' + continued_main, "continued main descriptor bind class")
continued = replace_once(continued, geometry_bind, '\t\tVkDescriptorStatsNoteBind(3);\n' + geometry_bind, "continued geometry descriptor bind class")

t = t[:first_start] + first + continued + t[draw_execute_start:]

report_anchor = '''\tRTExpLogStatsMaybe();
}

// used in place of vertex/uniform caching when direct memory access is possible'''
report_block = '''\tRTExpLogStatsMaybe();
\tVkDescriptorStatsReportDraw();
}

// used in place of vertex/uniform caching when direct memory access is possible'''
t = replace_once(t, report_anchor, report_block, "descriptor summary draw hook")

p.write_text(t, encoding="utf-8", newline="\n")
print("[vk-descriptor-stats] classified first/continued main/geometry descriptor binds")
