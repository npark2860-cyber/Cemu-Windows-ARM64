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

static bool VkDescriptorStatsEnvEnabled()
{
\tstatic const bool enabled = RuntimeExperiments::Enabled("vk-descriptor-stats");
\tif (enabled && !RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DescriptorStats))
\t\tRuntimeDiagnostics::SetEnabled(RuntimeDiagnostics::Flag::DescriptorStats, true);
\treturn enabled;
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
\t\t"[VK_DESCRIPTOR_STATS] draws={} lookups={} hits={} misses={} alloc={} update_writes={} bind_calls={}",
\t\ts_vkDescDiagDraws, hits + misses, hits, misses,
\t\tRuntimeDiagnostics::g_descriptorAlloc.load(std::memory_order_relaxed),
\t\tRuntimeDiagnostics::g_descriptorUpdateWrites.load(std::memory_order_relaxed),
\t\tRuntimeDiagnostics::g_descriptorBinds.load(std::memory_order_relaxed));
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

report_anchor = '''\tRTExpLogStatsMaybe();
}

// used in place of vertex/uniform caching when direct memory access is possible'''
report_block = '''\tRTExpLogStatsMaybe();
\tVkDescriptorStatsReportDraw();
}

// used in place of vertex/uniform caching when direct memory access is possible'''
t = replace_once(t, report_anchor, report_block, "descriptor summary draw hook")

p.write_text(t, encoding="utf-8", newline="\n")
print("[vk-descriptor-stats] bridged env launcher to existing DescriptorStats counters")
