from pathlib import Path

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)

def ensure_include(text, anchor, include_line, label):
    if include_line in text:
        return text
    return replace_once(text, anchor, anchor + include_line, label)

header_path = Path("src/diagnostics/RuntimeDiagnostics.h")
header = header_path.read_text(encoding="utf-8")
header = replace_once(
    header,
    """    // Render-target / synchronization diagnostics
    case Flag::RenderPassBeginEnd:
""",
    """    // Shader/render-target/feedback diagnostics
    case Flag::ShaderInterface:
    case Flag::FBOChanges:
    case Flag::AttachmentUsage:
    case Flag::LoadStoreBehavior:
    case Flag::RenderTargetAliasing:
    case Flag::FeedbackSupport:
    case Flag::FeedbackUse:

    // Render-target / synchronization diagnostics
    case Flag::RenderPassBeginEnd:
""",
    "graphics IsImplemented cases",
)
header_path.write_text(header, encoding="utf-8", newline="\n")

core_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
core = core_path.read_text(encoding="utf-8")
core = ensure_include(
    core,
    '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"\n',
    '#include "diagnostics/RuntimeDiagnostics.h"\n',
    "VulkanRendererCore diagnostics include",
)

core = replace_once(
    core,
    "extern bool hasValidFramebufferAttached;\n",
    """extern bool hasValidFramebufferAttached;

static uint64 s_rtStatDraws = 0;
static uint64 s_rtStatBegin = 0;
static uint64 s_rtStatEnd = 0;
static uint64 s_rtStatInputBarrier = 0;
static uint64 s_rtStatLoadBarrier = 0;
static uint64 s_rtStatSelfDependency = 0;
static uint64 s_rtStatForcedSplit = 0;
static uint64 s_rtStatLoadWAW = 0;
static uint64 s_rtStatLoadRAW = 0;
static uint64 s_rtStatPreBeginBarrier = 0;

static bool RTDiagStatsEnabled()
{
\treturn RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::RenderPassBeginEnd) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PipelineBarriers) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::RAWDependency) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::WAWDependency) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SelfDependency) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::RenderPassSplit) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SynchronizationSummary) ||
\t\tfalse;
}

static void RTDiagLogStatsMaybe()
{
\tif (!RTDiagStatsEnabled())
\t\treturn;
\t++s_rtStatDraws;
\tif ((s_rtStatDraws % 100000ULL) != 0)
\t\treturn;
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SynchronizationSummary))
\t\tcemuLog_log(LogType::Force, "[RT_STATS] draws={} begin={} end={} inputBarrier={} loadBarrier={} selfDep={} split={} loadWAW={} loadRAW={} preBeginBarrier={}",
\t\t\ts_rtStatDraws, s_rtStatBegin, s_rtStatEnd, s_rtStatInputBarrier, s_rtStatLoadBarrier,
\t\t\ts_rtStatSelfDependency, s_rtStatForcedSplit, s_rtStatLoadWAW, s_rtStatLoadRAW, s_rtStatPreBeginBarrier);
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
\t\tcemuLog_log(LogType::Force, "[RT_PASS_SPLIT] draws={} count={}", s_rtStatDraws, s_rtStatForcedSplit);
}
""",
    "RT diagnostic counters",
)

pipeline_anchor = """PipelineInfo* VulkanRenderer::draw_createGraphicsPipeline(uint32 indexCount)
{
\tconst auto fetchShader = LatteSHRC_GetActiveFetchShader();
\tconst auto vertexShader = LatteSHRC_GetActiveVertexShader();
\tconst auto geometryShader = LatteSHRC_GetActiveGeometryShader();
\tconst auto pixelShader = LatteSHRC_GetActivePixelShader();
\tauto cachedFboVk = (CachedFBOVk*)m_state.activeFBO;

"""
pipeline_new = pipeline_anchor + """\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ShaderInterface))
\t{
\t\tstatic std::atomic_uint64_t s_shaderInterfaceSeq{0};
\t\tconst uint64_t n = s_shaderInterfaceSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 200 || (n % 1000ULL) == 0)
\t\t{
\t\t\tauto logInterface = [n](const char* stage, LatteDecompilerShader* shader)
\t\t\t{
\t\t\t\tif (!shader)
\t\t\t\t\treturn;
\t\t\t\tuint32 uniformBufferCount = 0;
\t\t\t\tfor (sint8 binding : shader->resourceMapping.uniformBuffersBindingPoint)
\t\t\t\t\tif (binding >= 0) ++uniformBufferCount;
\t\t\t\tuint32 attributeCount = 0;
\t\t\t\tfor (sint8 attr : shader->resourceMapping.attributeMapping)
\t\t\t\t\tif (attr >= 0) ++attributeCount;
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[SHADER_INTERFACE] n={} stage={} base={:016x} aux={:016x} set={} textures={} uniformBuffers={} attributes={} outputParams=0x{:08x} pixelOutputs=0x{:08x} depthOut={} ringOut={} ringIn={}",
\t\t\t\t\tn, stage, shader->baseHash, shader->auxHash, (sint32)shader->resourceMapping.setIndex,
\t\t\t\t\t(sint32)shader->resourceMapping.textureUnitCount, uniformBufferCount, attributeCount,
\t\t\t\t\tshader->outputParameterMask, shader->pixelColorOutputMask, shader->depthMask ? 1 : 0,
\t\t\t\t\tshader->ringParameterCount, shader->ringParameterCountFromPrevStage);
\t\t\t};
\t\t\tlogInterface("vs", vertexShader);
\t\t\tlogInterface("gs", geometryShader);
\t\t\tlogInterface("ps", pixelShader);
\t\t}
\t}

"""
core = replace_once(core, pipeline_anchor, pipeline_new, "shader interface diagnostics")

input_barrier = """\t\tVkDependencyFlags dependencyFlags = withinFeedbackLoopRenderPass ? VK_DEPENDENCY_BY_REGION_BIT : 0;
\t\tvkCmdPipelineBarrier(m_state.currentCommandBuffer, srcStage, dstStage, dependencyFlags, 1, &memoryBarrier, 0, nullptr, 0, nullptr);

\t\tperformanceMonitor.vk.numDrawBarriersPerFrame.increment();"""
input_new = """\t\tVkDependencyFlags dependencyFlags = withinFeedbackLoopRenderPass ? VK_DEPENDENCY_BY_REGION_BIT : 0;
\t\tvkCmdPipelineBarrier(m_state.currentCommandBuffer, srcStage, dstStage, dependencyFlags, 1, &memoryBarrier, 0, nullptr, 0, nullptr);

\t\tif (RTDiagStatsEnabled())
\t\t\t++s_rtStatInputBarrier;
\t\tperformanceMonitor.vk.numDrawBarriersPerFrame.increment();"""
core = replace_once(core, input_barrier, input_new, "input barrier diagnostics")

load_scan = """void VulkanRenderer::sync_RenderPassLoadTextures(CachedFBOVk* fboVk)
{
\tbool readFlushRequired = false;
\t// always called after draw_inputTexturesChanged()
\tfor (auto& tex : fboVk->GetTextures())
\t{
\t\tLatteTextureVk* texVk = (LatteTextureVk*)tex;
\t\t// write-before-write
\t\tif (texVk->m_vkFlushIndex_write == m_state.currentFlushIndex)
\t\t\treadFlushRequired = true;


\t\ttexVk->m_vkFlushIndex_write = m_state.currentFlushIndex;
\t\t// todo - also check for write-before-write ?
\t\tif (texVk->m_vkFlushIndex_read == m_state.currentFlushIndex)
\t\t\treadFlushRequired = true;
\t}
\t// barrier here"""
load_new = """void VulkanRenderer::sync_RenderPassLoadTextures(CachedFBOVk* fboVk)
{
\tbool writeBeforeWrite = false;
\tbool readBeforeWrite = false;
\t// always called after draw_inputTexturesChanged()
\tfor (auto& tex : fboVk->GetTextures())
\t{
\t\tLatteTextureVk* texVk = (LatteTextureVk*)tex;
\t\tif (texVk->m_vkFlushIndex_write == m_state.currentFlushIndex)
\t\t\twriteBeforeWrite = true;

\t\ttexVk->m_vkFlushIndex_write = m_state.currentFlushIndex;
\t\tif (texVk->m_vkFlushIndex_read == m_state.currentFlushIndex)
\t\t\treadBeforeWrite = true;
\t}
\tif (RTDiagStatsEnabled())
\t{
\t\tif (writeBeforeWrite) ++s_rtStatLoadWAW;
\t\tif (readBeforeWrite) ++s_rtStatLoadRAW;
\t}
\tbool readFlushRequired = readBeforeWrite || writeBeforeWrite;
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::LoadStoreBehavior))
\t{
\t\tstatic std::atomic_uint64_t s_loadDiagSeq{0};
\t\tconst uint64_t n = s_loadDiagSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 200 || (n % 1000ULL) == 0)
\t\t\tcemuLog_log(LogType::Force, "[LOAD_STORE] phase=load n={} fbo={:016x} textures={} flush={} raw={} waw={} barrier={}",
\t\t\t\tn, fboVk->key, fboVk->GetTextures().size(), m_state.currentFlushIndex,
\t\t\t\treadBeforeWrite ? 1 : 0, writeBeforeWrite ? 1 : 0, readFlushRequired ? 1 : 0);
\t}
\t// barrier here"""
core = replace_once(core, load_scan, load_new, "render-pass load diagnostics")

load_barrier = """\t\tvkCmdPipelineBarrier(m_state.currentCommandBuffer, srcStage, dstStage, 0, 1, &memoryBarrier, 0, nullptr, 0, nullptr);

\t\tperformanceMonitor.vk.numDrawBarriersPerFrame.increment();"""
load_barrier_new = """\t\tvkCmdPipelineBarrier(m_state.currentCommandBuffer, srcStage, dstStage, 0, 1, &memoryBarrier, 0, nullptr, 0, nullptr);

\t\tif (RTDiagStatsEnabled())
\t\t\t++s_rtStatLoadBarrier;
\t\tperformanceMonitor.vk.numDrawBarriersPerFrame.increment();"""
core = replace_once(core, load_barrier, load_barrier_new, "load barrier diagnostics")

store_anchor = """void VulkanRenderer::sync_RenderPassStoreTextures(CachedFBOVk* fboVk)
{
\tuint32 flushIndex = m_state.currentFlushIndex;
\tfor (auto& tex : fboVk->GetTextures())
\t{
\t\tLatteTextureVk* texVk = (LatteTextureVk*)tex;
\t\ttexVk->m_vkFlushIndex_write = flushIndex;
\t}
}
"""
store_new = """void VulkanRenderer::sync_RenderPassStoreTextures(CachedFBOVk* fboVk)
{
\tuint32 flushIndex = m_state.currentFlushIndex;
\tfor (auto& tex : fboVk->GetTextures())
\t{
\t\tLatteTextureVk* texVk = (LatteTextureVk*)tex;
\t\ttexVk->m_vkFlushIndex_write = flushIndex;
\t}
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::LoadStoreBehavior))
\t{
\t\tstatic std::atomic_uint64_t s_storeDiagSeq{0};
\t\tconst uint64_t n = s_storeDiagSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 200 || (n % 1000ULL) == 0)
\t\t\tcemuLog_log(LogType::Force, "[LOAD_STORE] phase=store n={} fbo={:016x} textures={} flush={}", n, fboVk->key, fboVk->GetTextures().size(), flushIndex);
\t}
}
"""
core = replace_once(core, store_anchor, store_new, "render-pass store diagnostics")

split_anchor = """\tbool feedbackLoopHandlesSelfDependency = UseAttachmentFeedbackLoop() && renderSelfDependencyInfo.HasSelfDependency() && !renderSelfDependencyInfo.HasVertexOrGeometrySelfDependency();
\tbool selfDependencyNeedsPassSplit = renderSelfDependencyInfo.HasSelfDependency() && !feedbackLoopHandlesSelfDependency;
\tbool overridePassReuse = selfDependencyNeedsPassSplit && (GetConfig().vk_accurate_barriers || m_state.activePipelineInfo->neverSkipAccurateBarrier);

\tif (!overridePassReuse && m_state.activeRenderpassFBO == fboVk)
"""
split_new = """\tbool feedbackLoopHandlesSelfDependency = UseAttachmentFeedbackLoop() && renderSelfDependencyInfo.HasSelfDependency() && !renderSelfDependencyInfo.HasVertexOrGeometrySelfDependency();
\tbool selfDependencyNeedsPassSplit = renderSelfDependencyInfo.HasSelfDependency() && !feedbackLoopHandlesSelfDependency;
\tif (RTDiagStatsEnabled() && renderSelfDependencyInfo.HasSelfDependency())
\t\t++s_rtStatSelfDependency;

\tbool baseOverridePassReuse = selfDependencyNeedsPassSplit && (GetConfig().vk_accurate_barriers || m_state.activePipelineInfo->neverSkipAccurateBarrier);
\tconstexpr bool experimentSplit = false;
\tbool overridePassReuse = baseOverridePassReuse;
\tif (RTDiagStatsEnabled() && baseOverridePassReuse)
\t\t++s_rtStatForcedSplit;

\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::FeedbackSupport))
\t{
\t\tstatic std::atomic_bool s_feedbackSupportLogged{false};
\t\tif (!s_feedbackSupportLogged.exchange(true, std::memory_order_relaxed))
\t\t\tcemuLog_log(LogType::Force, "[FEEDBACK_SUPPORT] layout={} dynamicState={} active={}",
\t\t\t\tm_featureControl.deviceExtensions.attachment_feedback_loop_layout ? 1 : 0,
\t\t\t\tm_featureControl.deviceExtensions.attachment_feedback_loop_dynamic_state ? 1 : 0,
\t\t\t\tUseAttachmentFeedbackLoop() ? 1 : 0);
\t}
\tif (feedbackLoopHandlesSelfDependency && RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::FeedbackUse))
\t{
\t\tstatic std::atomic_uint64_t s_feedbackUseSeq{0};
\t\tconst uint64_t n = s_feedbackUseSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 200 || (n % 1000ULL) == 0)
\t\t\tcemuLog_log(LogType::Force, "[FEEDBACK_USE] n={} fbo={:016x} aspect=0x{:x} vertexOrGeometry={} passSplit={}",
\t\t\t\tn, fboVk->key, (uint32)renderSelfDependencyInfo.GetAspectMask(),
\t\t\t\trenderSelfDependencyInfo.HasVertexOrGeometrySelfDependency() ? 1 : 0,
\t\t\t\tselfDependencyNeedsPassSplit ? 1 : 0);
\t}

\tif (!overridePassReuse && m_state.activeRenderpassFBO == fboVk)
"""
core = replace_once(core, split_anchor, split_new, "self-dependency diagnostics")

new_pass_anchor = """\tdraw_endRenderPass();
\tif (m_state.descriptorSetsChanged)
\t\tsync_inputTexturesChanged();

\t// assume that FBO changed, update self-dependency state
"""
new_pass_new = """\tif (m_state.activeRenderpassFBO != fboVk && RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::FBOChanges))
\t{
\t\tstatic std::atomic_uint64_t s_fboChangeSeq{0};
\t\tconst uint64_t n = s_fboChangeSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 200 || (n % 1000ULL) == 0)
\t\t{
\t\t\tconst uint64_t prevKey = m_state.activeRenderpassFBO ? m_state.activeRenderpassFBO->key : 0;
\t\t\tconst auto extend = fboVk->GetExtend();
\t\t\tcemuLog_log(LogType::Force, "[FBO_CHANGE] n={} prev={:016x} next={:016x} size={}x{} colors={} depth={}",
\t\t\t\tn, prevKey, fboVk->key, extend.width, extend.height, fboVk->calculateNumColorBuffers(), fboVk->hasDepthBuffer() ? 1 : 0);
\t\t}
\t}
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::AttachmentUsage))
\t{
\t\tstatic std::atomic_uint64_t s_attachmentSeq{0};
\t\tconst uint64_t n = s_attachmentSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 200 || (n % 1000ULL) == 0)
\t\t{
\t\t\tfor (uint32 i = 0; i < 8; ++i)
\t\t\t{
\t\t\t\tauto view = fboVk->colorBuffer[i].texture;
\t\t\t\tif (view)
\t\t\t\t\tcemuLog_log(LogType::Force, "[ATTACHMENT_USE] n={} fbo={:016x} kind=color slot={} addr={:08x} mip={}+{} slice={}+{} format=0x{:x}",
\t\t\t\t\t\tn, fboVk->key, i, view->baseTexture->physAddress, view->firstMip, view->numMip, view->firstSlice, view->numSlice, (uint32)view->format);
\t\t\t}
\t\t\tauto depthView = fboVk->depthBuffer.texture;
\t\t\tif (depthView)
\t\t\t\tcemuLog_log(LogType::Force, "[ATTACHMENT_USE] n={} fbo={:016x} kind=depth addr={:08x} mip={}+{} slice={}+{} format=0x{:x}",
\t\t\t\t\tn, fboVk->key, depthView->baseTexture->physAddress, depthView->firstMip, depthView->numMip, depthView->firstSlice, depthView->numSlice, (uint32)depthView->format);
\t\t}
\t}
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::RenderTargetAliasing))
\t{
\t\tauto logAlias = [fboVk](const char* aKind, uint32 aSlot, LatteTextureView* a, const char* bKind, uint32 bSlot, LatteTextureView* b)
\t\t{
\t\t\tif (!a || !b) return;
\t\t\tconst bool sameBase = a->baseTexture == b->baseTexture;
\t\t\tconst bool sameAddr = a->baseTexture->physAddress == b->baseTexture->physAddress;
\t\t\tconst auto aLow = a->baseTexture->texDataPtrLow, aHigh = a->baseTexture->texDataPtrHigh;
\t\t\tconst auto bLow = b->baseTexture->texDataPtrLow, bHigh = b->baseTexture->texDataPtrHigh;
\t\t\tconst bool memoryOverlap = aLow && aHigh && bLow && bHigh && aLow <= bHigh && bLow <= aHigh;
\t\t\tif (!sameBase && !sameAddr && !memoryOverlap) return;
\t\t\tconst bool mipOverlap = a->firstMip < (b->firstMip + b->numMip) && b->firstMip < (a->firstMip + a->numMip);
\t\t\tconst bool sliceOverlap = a->firstSlice < (b->firstSlice + b->numSlice) && b->firstSlice < (a->firstSlice + a->numSlice);
\t\t\tcemuLog_log(LogType::Force, "[RT_ALIAS] fbo={:016x} a={}{} b={}{} sameBase={} sameAddr={} memoryOverlap={} subresourceOverlap={} aAddr={:08x} bAddr={:08x}",
\t\t\t\tfboVk->key, aKind, aSlot, bKind, bSlot, sameBase ? 1 : 0, sameAddr ? 1 : 0, memoryOverlap ? 1 : 0,
\t\t\t\t(mipOverlap && sliceOverlap) ? 1 : 0, a->baseTexture->physAddress, b->baseTexture->physAddress);
\t\t};
\t\tfor (uint32 a = 0; a < 8; ++a)
\t\t\tfor (uint32 b = a + 1; b < 8; ++b)
\t\t\t\tlogAlias("c", a, fboVk->colorBuffer[a].texture, "c", b, fboVk->colorBuffer[b].texture);
\t\tfor (uint32 a = 0; a < 8; ++a)
\t\t\tlogAlias("c", a, fboVk->colorBuffer[a].texture, "d", 0, fboVk->depthBuffer.texture);
\t}

\tdraw_endRenderPass();
\tif (m_state.descriptorSetsChanged)
\t\tsync_inputTexturesChanged();

\t// assume that FBO changed, update self-dependency state
"""
core = replace_once(core, new_pass_anchor, new_pass_new, "FBO/attachment/alias diagnostics")

core = replace_once(
    core,
    "\tperformanceMonitor.vk.numBeginRenderpassPerFrame.increment();\n}\n\nvoid VulkanRenderer::draw_endRenderPass()",
    """\tif (RTDiagStatsEnabled())
\t\t++s_rtStatBegin;
\tperformanceMonitor.vk.numBeginRenderpassPerFrame.increment();
}

void VulkanRenderer::draw_endRenderPass()""",
    "render-pass begin diagnostics",
)

core = replace_once(
    core,
    "\tsync_RenderPassStoreTextures(m_state.activeRenderpassFBO);\n\tm_state.activeRenderpassFBO = nullptr;\n}",
    """\tsync_RenderPassStoreTextures(m_state.activeRenderpassFBO);
\tm_state.activeRenderpassFBO = nullptr;
\tif (RTDiagStatsEnabled())
\t\t++s_rtStatEnd;
}""",
    "render-pass end diagnostics",
)

core = replace_once(
    core,
    "\tLatteGPUState.drawCallCounter++;\n}\n\n// used in place of vertex/uniform caching when direct memory access is possible",
    """\tLatteGPUState.drawCallCounter++;
\tRTDiagLogStatsMaybe();
}

// used in place of vertex/uniform caching when direct memory access is possible""",
    "draw diagnostics",
)

core_path.write_text(core, encoding="utf-8", newline="\n")
print("[lean-rt] observation-only RT/synchronization/feedback diagnostics installed")
