from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 anchor, found {count}')
    return text.replace(old, new, 1)


print('[rt-perf-experiments] Patching Vulkan render-target/synchronization experiments')
core_path = Path('src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp')
core = core_path.read_text(encoding='utf-8')

include_old = '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"\n'
include_new = include_old + '#include "diagnostics/RuntimeExperiments.h"\n#include "diagnostics/RuntimeDiagnostics.h"\n'
core = replace_once(core, include_old, include_new, 'VulkanRendererCore include anchor')

stats_old = 'extern bool hasValidFramebufferAttached;\n'
stats_new = r'''extern bool hasValidFramebufferAttached;

// Render-target/synchronization counters are collected only while at least one
// concrete RT diagnostic checkbox (or the legacy rt-stats env switch) is active.
static uint64 s_rtStatDraws = 0;
static uint64 s_rtStatBegin = 0;
static uint64 s_rtStatEnd = 0;
static uint64 s_rtStatInputBarrier = 0;
static uint64 s_rtStatLoadBarrier = 0;
static uint64 s_rtStatSelfDependency = 0;
static uint64 s_rtStatForcedSplit = 0;
static uint64 s_rtStatForcedInputSync = 0;
static uint64 s_rtStatForcedLoadSync = 0;
static uint64 s_rtStatPreBeginBarrier = 0;
static uint64 s_rtStatLoadWAW = 0;
static uint64 s_rtStatLoadRAW = 0;

static bool RTExpEnabled(std::string_view name)
{
\treturn RuntimeExperiments::Enabled(name) || RuntimeExperiments::Enabled("rt-safe-all");
}

static bool RTDiagStatsEnabled()
{
\treturn RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::RenderPassBeginEnd) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PipelineBarriers) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::RAWDependency) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::WAWDependency) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SelfDependency) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::RenderPassSplit) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SynchronizationSummary) ||
\t\tRuntimeExperiments::Enabled("rt-stats");
}

static void RTExpLogStatsMaybe()
{
\tif (!RTDiagStatsEnabled())
\t\treturn;
\t++s_rtStatDraws;
\tif ((s_rtStatDraws % 100000ULL) != 0)
\t\treturn;

\tconst bool legacyStats = RuntimeExperiments::Enabled("rt-stats");
\tif (legacyStats || RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SynchronizationSummary))
\t{
\t\tcemuLog_log(LogType::Force,
\t\t\t"[RT_STATS] draws={} begin={} end={} inputBarrier={} loadBarrier={} selfDep={} forcedSplit={} forcedInputSync={} forcedLoadSync={} preBeginBarrier={} loadWAW={} loadRAW={}",
\t\t\ts_rtStatDraws, s_rtStatBegin, s_rtStatEnd, s_rtStatInputBarrier, s_rtStatLoadBarrier,
\t\t\ts_rtStatSelfDependency, s_rtStatForcedSplit, s_rtStatForcedInputSync, s_rtStatForcedLoadSync,
\t\t\ts_rtStatPreBeginBarrier, s_rtStatLoadWAW, s_rtStatLoadRAW);
\t}
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::RenderPassBeginEnd))
\t\tcemuLog_log(LogType::Force, "[RT_PASS] draws={} begin={} end={}", s_rtStatDraws, s_rtStatBegin, s_rtStatEnd);
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PipelineBarriers))
\t\tcemuLog_log(LogType::Force, "[RT_BARRIER] draws={} input={} load={} preBegin={}", s_rtStatDraws, s_rtStatInputBarrier, s_rtStatLoadBarrier, s_rtStatPreBeginBarrier);
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::RAWDependency))
\t\tcemuLog_log(LogType::Force, "[RT_RAW] draws={} loadRAW={}", s_rtStatDraws, s_rtStatLoadRAW);
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::WAWDependency))
\t\tcemuLog_log(LogType::Force, "[RT_WAW] draws={} loadWAW={}", s_rtStatDraws, s_rtStatLoadWAW);
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SelfDependency))
\t\tcemuLog_log(LogType::Force, "[RT_SELF_DEP] draws={} count={}", s_rtStatDraws, s_rtStatSelfDependency);
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::RenderPassSplit))
\t\tcemuLog_log(LogType::Force, "[RT_PASS_SPLIT] draws={} forcedSplit={}", s_rtStatDraws, s_rtStatForcedSplit);
}
'''
core = replace_once(core, stats_old, stats_new, 'RT stats anchor')

input_force_old = '\t// barrier here\n\tif (writeFlushRequired)\n\t{\n\t\tVkMemoryBarrier memoryBarrier{};'
input_force_new = '''\tif (RTExpEnabled("rt-force-sync") && !writeFlushRequired)\n\t{\n\t\twriteFlushRequired = true;\n\t\tif (RTDiagStatsEnabled())\n\t\t\t++s_rtStatForcedInputSync;\n\t}\n\t// barrier here\n\tif (writeFlushRequired)\n\t{\n\t\tVkMemoryBarrier memoryBarrier{};'''
core = replace_once(core, input_force_old, input_force_new, 'input force-sync anchor')

input_barrier_old = '''\t\tVkDependencyFlags dependencyFlags = withinFeedbackLoopRenderPass ? VK_DEPENDENCY_BY_REGION_BIT : 0;\n\t\tvkCmdPipelineBarrier(m_state.currentCommandBuffer, srcStage, dstStage, dependencyFlags, 1, &memoryBarrier, 0, nullptr, 0, nullptr);\n\n\t\tperformanceMonitor.vk.numDrawBarriersPerFrame.increment();'''
input_barrier_new = '''\t\tif (RTExpEnabled("rt-strong-barrier"))\n\t\t{\n\t\t\tsrcStage = VK_PIPELINE_STAGE_ALL_COMMANDS_BIT;\n\t\t\tdstStage = VK_PIPELINE_STAGE_ALL_COMMANDS_BIT;\n\t\t\tmemoryBarrier.srcAccessMask = VK_ACCESS_MEMORY_WRITE_BIT;\n\t\t\tmemoryBarrier.dstAccessMask = VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT;\n\t\t}\n\n\t\tVkDependencyFlags dependencyFlags = withinFeedbackLoopRenderPass ? VK_DEPENDENCY_BY_REGION_BIT : 0;\n\t\tvkCmdPipelineBarrier(m_state.currentCommandBuffer, srcStage, dstStage, dependencyFlags, 1, &memoryBarrier, 0, nullptr, 0, nullptr);\n\n\t\tif (RTDiagStatsEnabled())\n\t\t\t++s_rtStatInputBarrier;\n\t\tperformanceMonitor.vk.numDrawBarriersPerFrame.increment();'''
core = replace_once(core, input_barrier_old, input_barrier_new, 'input barrier anchor')

load_scan_old = '''void VulkanRenderer::sync_RenderPassLoadTextures(CachedFBOVk* fboVk)\n{\n\tbool readFlushRequired = false;\n\t// always called after draw_inputTexturesChanged()\n\tfor (auto& tex : fboVk->GetTextures())\n\t{\n\t\tLatteTextureVk* texVk = (LatteTextureVk*)tex;\n\t\t// write-before-write\n\t\tif (texVk->m_vkFlushIndex_write == m_state.currentFlushIndex)\n\t\t\treadFlushRequired = true;\n\n\n\t\ttexVk->m_vkFlushIndex_write = m_state.currentFlushIndex;\n\t\t// todo - also check for write-before-write ?\n\t\tif (texVk->m_vkFlushIndex_read == m_state.currentFlushIndex)\n\t\t\treadFlushRequired = true;\n\t}\n\t// barrier here'''
load_scan_new = '''void VulkanRenderer::sync_RenderPassLoadTextures(CachedFBOVk* fboVk)\n{\n\tbool writeBeforeWrite = false;\n\tbool readBeforeWrite = false;\n\t// always called after draw_inputTexturesChanged()\n\tfor (auto& tex : fboVk->GetTextures())\n\t{\n\t\tLatteTextureVk* texVk = (LatteTextureVk*)tex;\n\t\tif (texVk->m_vkFlushIndex_write == m_state.currentFlushIndex)\n\t\t\twriteBeforeWrite = true;\n\n\t\ttexVk->m_vkFlushIndex_write = m_state.currentFlushIndex;\n\t\tif (texVk->m_vkFlushIndex_read == m_state.currentFlushIndex)\n\t\t\treadBeforeWrite = true;\n\t}\n\tif (RTDiagStatsEnabled())\n\t{\n\t\tif (writeBeforeWrite) ++s_rtStatLoadWAW;\n\t\tif (readBeforeWrite) ++s_rtStatLoadRAW;\n\t}\n\n\tbool readFlushRequired = readBeforeWrite || writeBeforeWrite;\n\tif (RuntimeExperiments::Enabled("perf-skip-waw-barrier"))\n\t\treadFlushRequired = readBeforeWrite;\n\tif (RuntimeExperiments::Enabled("perf-skip-rt-load-barrier"))\n\t\treadFlushRequired = false;\n\tif (RTExpEnabled("rt-force-sync") && !readFlushRequired)\n\t{\n\t\treadFlushRequired = true;\n\t\tif (RTDiagStatsEnabled())\n\t\t\t++s_rtStatForcedLoadSync;\n\t}\n\t// barrier here'''
core = replace_once(core, load_scan_old, load_scan_new, 'render-pass load scan anchor')

load_barrier_old = '''\t\tvkCmdPipelineBarrier(m_state.currentCommandBuffer, srcStage, dstStage, 0, 1, &memoryBarrier, 0, nullptr, 0, nullptr);\n\n\t\tperformanceMonitor.vk.numDrawBarriersPerFrame.increment();'''
load_barrier_new = '''\t\tif (RTExpEnabled("rt-strong-barrier"))\n\t\t{\n\t\t\tsrcStage = VK_PIPELINE_STAGE_ALL_COMMANDS_BIT;\n\t\t\tdstStage = VK_PIPELINE_STAGE_ALL_COMMANDS_BIT;\n\t\t\tmemoryBarrier.srcAccessMask = VK_ACCESS_MEMORY_WRITE_BIT;\n\t\t\tmemoryBarrier.dstAccessMask = VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT;\n\t\t}\n\n\t\tvkCmdPipelineBarrier(m_state.currentCommandBuffer, srcStage, dstStage, 0, 1, &memoryBarrier, 0, nullptr, 0, nullptr);\n\n\t\tif (RTDiagStatsEnabled())\n\t\t\t++s_rtStatLoadBarrier;\n\t\tperformanceMonitor.vk.numDrawBarriersPerFrame.increment();'''
core = replace_once(core, load_barrier_old, load_barrier_new, 'render-pass load barrier anchor')

split_old = '''\tbool feedbackLoopHandlesSelfDependency = UseAttachmentFeedbackLoop() && renderSelfDependencyInfo.HasSelfDependency() && !renderSelfDependencyInfo.HasVertexOrGeometrySelfDependency();\n\tbool selfDependencyNeedsPassSplit = renderSelfDependencyInfo.HasSelfDependency() && !feedbackLoopHandlesSelfDependency;\n\tbool overridePassReuse = selfDependencyNeedsPassSplit && (GetConfig().vk_accurate_barriers || m_state.activePipelineInfo->neverSkipAccurateBarrier);\n\n\tif (!overridePassReuse && m_state.activeRenderpassFBO == fboVk)'''
split_new = '''\tbool feedbackLoopHandlesSelfDependency = UseAttachmentFeedbackLoop() && renderSelfDependencyInfo.HasSelfDependency() && !renderSelfDependencyInfo.HasVertexOrGeometrySelfDependency();\n\tbool selfDependencyNeedsPassSplit = renderSelfDependencyInfo.HasSelfDependency() && !feedbackLoopHandlesSelfDependency;\n\tif (RTDiagStatsEnabled() && renderSelfDependencyInfo.HasSelfDependency())\n\t\t++s_rtStatSelfDependency;\n\n\tbool baseOverridePassReuse = selfDependencyNeedsPassSplit && (GetConfig().vk_accurate_barriers || m_state.activePipelineInfo->neverSkipAccurateBarrier);\n\tbool experimentSplit = selfDependencyNeedsPassSplit && RTExpEnabled("rt-selfdep-split");\n\tbool overridePassReuse = baseOverridePassReuse || experimentSplit;\n\tif (RuntimeExperiments::Enabled("perf-force-pass-reuse"))\n\t\toverridePassReuse = false;\n\tif (RTDiagStatsEnabled() && experimentSplit && !baseOverridePassReuse)\n\t\t++s_rtStatForcedSplit;\n\n\tif (!overridePassReuse && m_state.activeRenderpassFBO == fboVk)'''
core = replace_once(core, split_old, split_new, 'self-dependency split anchor')

prebegin_old = '''\tsync_RenderPassLoadTextures(fboVk);\n\n\tif (m_featureControl.deviceExtensions.dynamic_rendering)'''
prebegin_new = '''\tsync_RenderPassLoadTextures(fboVk);\n\n\tif (RTExpEnabled("rt-prebegin-barrier"))\n\t{\n\t\tVkMemoryBarrier memoryBarrier{};\n\t\tmemoryBarrier.sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER;\n\t\tmemoryBarrier.srcAccessMask = VK_ACCESS_MEMORY_WRITE_BIT;\n\t\tmemoryBarrier.dstAccessMask = VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT;\n\t\tvkCmdPipelineBarrier(m_state.currentCommandBuffer,\n\t\t\tVK_PIPELINE_STAGE_ALL_COMMANDS_BIT, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0,\n\t\t\t1, &memoryBarrier, 0, nullptr, 0, nullptr);\n\t\tif (RTDiagStatsEnabled())\n\t\t\t++s_rtStatPreBeginBarrier;\n\t\tperformanceMonitor.vk.numDrawBarriersPerFrame.increment();\n\t}\n\n\tif (m_featureControl.deviceExtensions.dynamic_rendering)'''
core = replace_once(core, prebegin_old, prebegin_new, 'pre-begin barrier anchor')

begin_old = '''\tperformanceMonitor.vk.numBeginRenderpassPerFrame.increment();\n}\n\nvoid VulkanRenderer::draw_endRenderPass()'''
begin_new = '''\tif (RTDiagStatsEnabled())\n\t\t++s_rtStatBegin;\n\tperformanceMonitor.vk.numBeginRenderpassPerFrame.increment();\n}\n\nvoid VulkanRenderer::draw_endRenderPass()'''
core = replace_once(core, begin_old, begin_new, 'render-pass begin stat anchor')

end_old = '''\tsync_RenderPassStoreTextures(m_state.activeRenderpassFBO);\n\tm_state.activeRenderpassFBO = nullptr;\n}'''
end_new = '''\tsync_RenderPassStoreTextures(m_state.activeRenderpassFBO);\n\tm_state.activeRenderpassFBO = nullptr;\n\tif (RTDiagStatsEnabled())\n\t\t++s_rtStatEnd;\n}'''
core = replace_once(core, end_old, end_new, 'render-pass end stat anchor')

draw_old = '''\tLatteGPUState.drawCallCounter++;\n}\n\n// used in place of vertex/uniform caching when direct memory access is possible'''
draw_new = '''\tLatteGPUState.drawCallCounter++;\n\tRTExpLogStatsMaybe();\n}\n\n// used in place of vertex/uniform caching when direct memory access is possible'''
core = replace_once(core, draw_old, draw_new, 'draw stats anchor')

core_path.write_text(core, encoding='utf-8', newline='')

print('[rt-perf-experiments] Patch summary')
print('  - independent UI diagnostics: render-pass, barriers, RAW, WAW, self-dependency, pass-split, sync-summary')
print('  - rt-force-sync')
print('  - rt-selfdep-split')
print('  - rt-strong-barrier')
print('  - rt-prebegin-barrier')
print('  - rt-safe-all (combines RT safety switches)')
print('  - legacy rt-stats')
print('  - perf-skip-waw-barrier')
print('  - perf-skip-rt-load-barrier')
print('  - perf-force-pass-reuse')