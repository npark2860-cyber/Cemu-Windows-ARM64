from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


def ensure_include(text: str, anchor: str, include_line: str, label: str) -> str:
    if include_line in text:
        return text
    return replace_once(text, anchor, anchor + include_line, label)


# Complete the remaining 22 user-visible diagnostic checkboxes.
header_path = Path("src/diagnostics/RuntimeDiagnostics.h")
header = header_path.read_text(encoding="utf-8")
header = replace_once(
    header,
    '''    case Flag::FeedbackUse:

    // Render-target / synchronization diagnostics
''',
    '''    case Flag::FeedbackUse:
    case Flag::FeedbackFallback:
    case Flag::FeedbackSelfDependency:
    case Flag::ImageLayoutTransition:
    case Flag::FeedbackPassSplit:

    // Texture diagnostics
    case Flag::TextureLifecycle:
    case Flag::TextureViewLifecycle:
    case Flag::TextureCache:
    case Flag::TextureAliasing:
    case Flag::SurfaceInvalidation:
    case Flag::SuspiciousTextureState:

    // Input diagnostics
    case Flag::VPAD:
    case Flag::KPAD:
    case Flag::ControllerSlot:
    case Flag::PlayerIndex:
    case Flag::ChannelMapping:
    case Flag::ConnectDisconnect:
    case Flag::InputReadSummary:

    // Extended performance diagnostics
    case Flag::LatteThreadTiming:
    case Flag::PerfPipelineCache:
    case Flag::BarrierCount:
    case Flag::RenderPassCount:
    case Flag::UploadStallTiming:

    // Render-target / synchronization diagnostics
''',
    "remaining IsImplemented cases",
)
header_path.write_text(header, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Feedback-loop diagnostics + performance counters in VulkanRendererCore.cpp
# ---------------------------------------------------------------------------
core_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
core = core_path.read_text(encoding="utf-8")

core = replace_once(
    core,
    '''\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::RenderPassSplit) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SynchronizationSummary) ||
\t\tRuntimeExperiments::Enabled("rt-stats");
''',
    '''\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::RenderPassSplit) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SynchronizationSummary) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::BarrierCount) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::RenderPassCount) ||
\t\tRuntimeExperiments::Enabled("rt-stats");
''',
    "RT count diagnostics activation",
)

core = replace_once(
    core,
    '''\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::RenderPassSplit))
\t\tcemuLog_log(LogType::Force, "[RT_PASS_SPLIT] draws={} forcedSplit={}", s_rtStatDraws, s_rtStatForcedSplit);
}
''',
    '''\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::RenderPassSplit))
\t\tcemuLog_log(LogType::Force, "[RT_PASS_SPLIT] draws={} forcedSplit={}", s_rtStatDraws, s_rtStatForcedSplit);
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::BarrierCount))
\t\tcemuLog_log(LogType::Force, "[BARRIER_COUNT] draws={} total={} input={} load={} preBegin={}",
\t\t\ts_rtStatDraws, s_rtStatInputBarrier + s_rtStatLoadBarrier + s_rtStatPreBeginBarrier,
\t\t\ts_rtStatInputBarrier, s_rtStatLoadBarrier, s_rtStatPreBeginBarrier);
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::RenderPassCount))
\t\tcemuLog_log(LogType::Force, "[RENDERPASS_COUNT] draws={} begin={} end={}",
\t\t\ts_rtStatDraws, s_rtStatBegin, s_rtStatEnd);
}
''',
    "barrier/renderpass count logs",
)

cache_anchor = '''PipelineInfo* VulkanRenderer::draw_getOrCreateGraphicsPipeline(uint32 indexCount)
{
\tauto cache_object = draw_getCachedPipeline();
\tif (cache_object != nullptr)
\t{
'''
cache_new = '''PipelineInfo* VulkanRenderer::draw_getOrCreateGraphicsPipeline(uint32 indexCount)
{
\tauto cache_object = draw_getCachedPipeline();
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PerfPipelineCache))
\t{
\t\tstatic std::atomic_uint64_t s_perfPipelineLookup{0};
\t\tconst uint64_t n = s_perfPipelineLookup.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (cache_object)
\t\t\tRuntimeDiagnostics::g_pipelineCacheHits.fetch_add(1, std::memory_order_relaxed);
\t\telse
\t\t\tRuntimeDiagnostics::g_pipelineCacheMisses.fetch_add(1, std::memory_order_relaxed);
\t\tif (n <= 200 || (n % 10000ULL) == 0)
\t\t\tcemuLog_log(LogType::Force, "[PERF_PIPE_CACHE] n={} result={} hits={} misses={}",
\t\t\t\tn, cache_object ? "hit" : "miss",
\t\t\t\tRuntimeDiagnostics::g_pipelineCacheHits.load(std::memory_order_relaxed),
\t\t\t\tRuntimeDiagnostics::g_pipelineCacheMisses.load(std::memory_order_relaxed));
\t}
\tif (cache_object != nullptr)
\t{
'''
core = replace_once(core, cache_anchor, cache_new, "pipeline cache performance hook")

wait_anchor = '''\tauto waitWhileCondition = [&]<class TCondition>(TCondition&& condition) {
\t\twhile (condition())
\t\t{
'''
wait_new = '''\tauto waitWhileCondition = [&]<class TCondition>(TCondition&& condition) {
\t\tconst bool diagUploadStall = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::UploadStallTiming);
\t\tconst uint64_t diagWaitStart = diagUploadStall ? RuntimeDiagnostics::NowNs() : 0;
\t\tuint32_t diagWaitCount = 0;
\t\twhile (condition())
\t\t{
\t\t\t++diagWaitCount;
'''
core = replace_once(core, wait_anchor, wait_new, "upload stall timing start")

wait_end_anchor = '''\t\t\tWaitForNextFinishedCommandBuffer();
\t\t}
\t};
'''
wait_end_new = '''\t\t\tWaitForNextFinishedCommandBuffer();
\t\t}
\t\tif (diagUploadStall && diagWaitCount != 0)
\t\t{
\t\t\tconst uint64_t ns = RuntimeDiagnostics::NowNs() - diagWaitStart;
\t\t\tstatic std::atomic_uint64_t s_uploadStallSeq{0};
\t\t\tconst uint64_t n = s_uploadStallSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\t\tif (n <= 200 || (n % 1000ULL) == 0)
\t\t\t\tcemuLog_log(LogType::Force, "[UPLOAD_STALL] n={} waits={} ns={} uniformBytes={}",
\t\t\t\t\tn, diagWaitCount, ns, uniformSize);
\t\t}
\t};
'''
core = replace_once(core, wait_end_anchor, wait_end_new, "upload stall timing end")

feedback_decision_anchor = '''\tif (!overridePassReuse && m_state.activeRenderpassFBO == fboVk)
'''
feedback_decision_new = '''\tif (renderSelfDependencyInfo.HasSelfDependency() &&
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::FeedbackSelfDependency))
\t{
\t\tstatic std::atomic_uint64_t s_feedbackSelfSeq{0};
\t\tconst uint64_t n = s_feedbackSelfSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 200 || (n % 1000ULL) == 0)
\t\t\tcemuLog_log(LogType::Force, "[FEEDBACK_SELF_DEP] n={} fbo={:016x} aspect=0x{:x} nonPixel={} handled={}",
\t\t\t\tn, fboVk->key, (uint32)renderSelfDependencyInfo.GetAspectMask(),
\t\t\t\trenderSelfDependencyInfo.HasVertexOrGeometrySelfDependency() ? 1 : 0,
\t\t\t\tfeedbackLoopHandlesSelfDependency ? 1 : 0);
\t}
\tif (selfDependencyNeedsPassSplit &&
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::FeedbackFallback))
\t{
\t\tstatic std::atomic_uint64_t s_feedbackFallbackSeq{0};
\t\tconst uint64_t n = s_feedbackFallbackSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 200 || (n % 1000ULL) == 0)
\t\t\tcemuLog_log(LogType::Force, "[FEEDBACK_FALLBACK] n={} fbo={:016x} extensionActive={} nonPixel={} accurate={} neverSkip={}",
\t\t\t\tn, fboVk->key, UseAttachmentFeedbackLoop() ? 1 : 0,
\t\t\t\trenderSelfDependencyInfo.HasVertexOrGeometrySelfDependency() ? 1 : 0,
\t\t\t\tGetConfig().vk_accurate_barriers ? 1 : 0,
\t\t\t\tm_state.activePipelineInfo->neverSkipAccurateBarrier ? 1 : 0);
\t}
\tif (selfDependencyNeedsPassSplit && overridePassReuse &&
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::FeedbackPassSplit))
\t{
\t\tstatic std::atomic_uint64_t s_feedbackSplitSeq{0};
\t\tconst uint64_t n = s_feedbackSplitSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 200 || (n % 1000ULL) == 0)
\t\t\tcemuLog_log(LogType::Force, "[FEEDBACK_PASS_SPLIT] n={} fbo={:016x} base={} experiment={}",
\t\t\t\tn, fboVk->key, baseOverridePassReuse ? 1 : 0, experimentSplit ? 1 : 0);
\t}

\tif (!overridePassReuse && m_state.activeRenderpassFBO == fboVk)
'''
core = replace_once(core, feedback_decision_anchor, feedback_decision_new, "feedback fallback/self/split hooks")
core_path.write_text(core, encoding="utf-8", newline="\n")


renderer_h_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h")
renderer_h = renderer_h_path.read_text(encoding="utf-8")
layout_anchor = '''\t\timageMemBarrier.oldLayout = oldLayout;
\t\timageMemBarrier.newLayout = newLayout;

\t\tvkCmdPipelineBarrier(m_state.currentCommandBuffer,
'''
layout_new = '''\t\timageMemBarrier.oldLayout = oldLayout;
\t\timageMemBarrier.newLayout = newLayout;
\t\tif (oldLayout != newLayout && RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ImageLayoutTransition))
\t\t{
\t\t\tstatic std::atomic_uint64_t s_layoutTransitionSeq{0};
\t\t\tconst uint64_t n = s_layoutTransitionSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\t\tif (n <= 200 || (n % 1000ULL) == 0)
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[IMAGE_LAYOUT] n={} image=0x{:x} old={} new={} aspect=0x{:x} mip={}+{} layer={}+{}",
\t\t\t\t\tn, (uint64_t)imageVk, (uint32)oldLayout, (uint32)newLayout,
\t\t\t\t\t(uint32)subresourceRange.aspectMask, subresourceRange.baseMipLevel,
\t\t\t\t\tsubresourceRange.levelCount, subresourceRange.baseArrayLayer, subresourceRange.layerCount);
\t\t}

\t\tvkCmdPipelineBarrier(m_state.currentCommandBuffer,
'''
renderer_h = replace_once(renderer_h, layout_anchor, layout_new, "image layout transition hook")
renderer_h_path.write_text(renderer_h, encoding="utf-8", newline="\n")


tex_cache_path = Path("src/Cafe/HW/Latte/Core/LatteTextureCache.cpp")
tex_cache = tex_cache_path.read_text(encoding="utf-8")
tex_cache = ensure_include(
    tex_cache,
    '#include "Common/cpu_features.h"\n',
    '#include "diagnostics/RuntimeDiagnostics.h"\n',
    "texture cache diag include",
)

delete_anchor = '''void LatteTexture_Delete(LatteTexture* texture)
{
\tLatteTC_UnregisterTexture(texture);
'''
delete_new = '''void LatteTexture_Delete(LatteTexture* texture)
{
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::TextureLifecycle))
\t\tcemuLog_log(LogType::Force, "[TEXTURE_LIFECYCLE] DELETE addr={:08x} mipAddr={:08x} size={}x{}x{} mips={} format=0x{:x} gpuUpdated={} reloads={}",
\t\t\ttexture->physAddress, texture->physMipAddress, texture->width, texture->height, texture->depth,
\t\t\ttexture->mipLevels, (uint32)texture->format, texture->isUpdatedOnGPU ? 1 : 0, texture->reloadCount);
\tLatteTC_UnregisterTexture(texture);
'''
tex_cache = replace_once(tex_cache, delete_anchor, delete_new, "texture delete lifecycle")

force_anchor = '''\tif (hostTexture->forceInvalidate)
\t{
\t\tforce = true;
\t\tdebug_printf("Force invalidate 0x%08x\\n", hostTexture->physAddress);
'''
force_new = '''\tif (hostTexture->forceInvalidate)
\t{
\t\tforce = true;
\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SurfaceInvalidation))
\t\t\tcemuLog_log(LogType::Force, "[SURFACE_INVALIDATE] reason=forced addr={:08x} range={:08x}-{:08x} frame={}",
\t\t\t\thostTexture->physAddress, hostTexture->texDataPtrLow, hostTexture->texDataPtrHigh, LatteGPUState.frameCounter);
\t\tdebug_printf("Force invalidate 0x%08x\\n", hostTexture->physAddress);
'''
tex_cache = replace_once(tex_cache, force_anchor, force_new, "forced surface invalidation")

hash_anchor = '''\tif( texDataHash != hostTexture->texDataHash2 )
\t{
\t\thostTexture->texDataHash2 = texDataHash;
'''
hash_new = '''\tif( texDataHash != hostTexture->texDataHash2 )
\t{
\t\tconst uint32 oldHash = hostTexture->texDataHash2;
\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SurfaceInvalidation))
\t\t\tcemuLog_log(LogType::Force, "[SURFACE_INVALIDATE] reason=hash addr={:08x} old={:08x} new={:08x} gpuUpdated={} frame={}",
\t\t\t\thostTexture->physAddress, oldHash, texDataHash, hostTexture->isUpdatedOnGPU ? 1 : 0, LatteGPUState.frameCounter);
\t\thostTexture->texDataHash2 = texDataHash;
'''
tex_cache = replace_once(tex_cache, hash_anchor, hash_new, "hash surface invalidation")

alias_anchor = '''\t\t\t\tif (sliceMipInfo->lastDynamicUpdate < overlapData.destMipSliceInfo->lastDynamicUpdate)
\t\t\t\t{
\t\t\t\t\tisSliceMipOutdated = true;
'''
alias_new = '''\t\t\t\tif (sliceMipInfo->lastDynamicUpdate < overlapData.destMipSliceInfo->lastDynamicUpdate)
\t\t\t\t{
\t\t\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::TextureAliasing))
\t\t\t\t\t{
\t\t\t\t\t\tstatic std::atomic_uint64_t s_textureAliasSeq{0};
\t\t\t\t\t\tconst uint64_t n = s_textureAliasSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\t\t\t\t\tif (n <= 200 || (n % 1000ULL) == 0)
\t\t\t\t\t\t\tcemuLog_log(LogType::Force, "[TEXTURE_ALIAS] n={} addr={:08x} mip={} slice={} localUpdate={} overlapUpdate={}",
\t\t\t\t\t\t\t\tn, texture->physAddress, mipIndex, sliceIndex, sliceMipInfo->lastDynamicUpdate,
\t\t\t\t\t\t\t\toverlapData.destMipSliceInfo->lastDynamicUpdate);
\t\t\t\t\t}
\t\t\t\t\tisSliceMipOutdated = true;
'''
tex_cache = replace_once(tex_cache, alias_anchor, alias_new, "texture alias overlap hook")
tex_cache_path.write_text(tex_cache, encoding="utf-8", newline="\n")

tex_legacy_path = Path("src/Cafe/HW/Latte/Core/LatteTextureLegacy.cpp")
tex_legacy = tex_legacy_path.read_text(encoding="utf-8")
tex_legacy = ensure_include(
    tex_legacy,
    '#include "Cafe/HW/Latte/Renderer/Renderer.h"\n',
    '#include "diagnostics/RuntimeDiagnostics.h"\n',
    "texture legacy diag include",
)

create_anchor = '''\tLatteTC_RegisterTexture(tex);

\t// create initial view that maps to the whole texture
'''
create_new = '''\tLatteTC_RegisterTexture(tex);
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::TextureLifecycle))
\t\tcemuLog_log(LogType::Force, "[TEXTURE_LIFECYCLE] CREATE addr={:08x} mipAddr={:08x} size={}x{}x{} pitch={} mips={} format=0x{:x} dim={} isDepth={}",
\t\t\ttex->physAddress, tex->physMipAddress, tex->width, tex->height, tex->depth, tex->pitch,
\t\t\ttex->mipLevels, (uint32)tex->format, (uint32)tex->dim, tex->isDepth ? 1 : 0);

\t// create initial view that maps to the whole texture
'''
tex_legacy = replace_once(tex_legacy, create_anchor, create_new, "texture create lifecycle")

lookup_anchor = '''\t\tif (!textureView)
\t\t{
\t\t\t// view not found, create a new mapping which will also create a new texture if necessary
'''
lookup_new = '''\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::TextureCache))
\t\t{
\t\t\tstatic std::atomic_uint64_t s_textureCacheSeq{0};
\t\t\tconst uint64_t n = s_textureCacheSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\t\tif (n <= 200 || (n % 10000ULL) == 0)
\t\t\t\tcemuLog_log(LogType::Force, "[TEXTURE_CACHE] n={} result={} stage={} unit={} addr={:08x} mip={}+{} slice={}+{} format=0x{:x}",
\t\t\t\t\tn, textureView ? "hit" : "miss", (uint32)shaderContext->shaderType, textureIndex,
\t\t\t\t\tphysAddr, viewFirstMip, viewNumMips, viewFirstSlice, viewNumSlices, (uint32)format);
\t\t}
\t\tif (!textureView)
\t\t{
\t\t\t// view not found, create a new mapping which will also create a new texture if necessary
'''
tex_legacy = replace_once(tex_legacy, lookup_anchor, lookup_new, "texture cache hit/miss")

suspicious_anchor = '''\t\tif (textureView->baseTexture->swizzle != swizzle)
\t\t{
\t\t\tdebug_printf("BaseSwizzle diff prev %08x new %08x rt %08x tm %d\\n", textureView->baseTexture->swizzle, swizzle, textureView->baseTexture->lastRenderTargetSwizzle, textureView->baseTexture->tileMode);
'''
suspicious_new = '''\t\tif (textureView->baseTexture->swizzle != swizzle)
\t\t{
\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SuspiciousTextureState))
\t\t\t\tcemuLog_log(LogType::Force, "[SUSPICIOUS_TEXTURE] reason=swizzle addr={:08x} current={:08x} requested={:08x} lastRT={:08x} tile={}",
\t\t\t\t\ttextureView->baseTexture->physAddress, textureView->baseTexture->swizzle, swizzle,
\t\t\t\t\ttextureView->baseTexture->lastRenderTargetSwizzle, (uint32)textureView->baseTexture->tileMode);
\t\t\tdebug_printf("BaseSwizzle diff prev %08x new %08x rt %08x tm %d\\n", textureView->baseTexture->swizzle, swizzle, textureView->baseTexture->lastRenderTargetSwizzle, textureView->baseTexture->tileMode);
'''
tex_legacy = replace_once(tex_legacy, suspicious_anchor, suspicious_new, "suspicious texture swizzle")

mip_suspicious_anchor = '''\t\telse if ((viewFirstMip + viewNumMips) > 1 && (textureView->baseTexture->physMipAddress != physMipAddr))
\t\t{
\t\t\tdebug_printf("MipPhys/Swizzle change diff prev %08x new %08x tm %d\\n", textureView->baseTexture->physMipAddress, physMipAddr, textureView->baseTexture->tileMode);
'''
mip_suspicious_new = '''\t\telse if ((viewFirstMip + viewNumMips) > 1 && (textureView->baseTexture->physMipAddress != physMipAddr))
\t\t{
\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SuspiciousTextureState))
\t\t\t\tcemuLog_log(LogType::Force, "[SUSPICIOUS_TEXTURE] reason=mip_address addr={:08x} oldMip={:08x} newMip={:08x} firstMip={} count={} tile={}",
\t\t\t\t\ttextureView->baseTexture->physAddress, textureView->baseTexture->physMipAddress, physMipAddr,
\t\t\t\t\tviewFirstMip, viewNumMips, (uint32)textureView->baseTexture->tileMode);
\t\t\tdebug_printf("MipPhys/Swizzle change diff prev %08x new %08x tm %d\\n", textureView->baseTexture->physMipAddress, physMipAddr, textureView->baseTexture->tileMode);
'''
tex_legacy = replace_once(tex_legacy, mip_suspicious_anchor, mip_suspicious_new, "suspicious texture mip address")
tex_legacy_path.write_text(tex_legacy, encoding="utf-8", newline="\n")

view_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/LatteTextureViewVk.cpp")
view = view_path.read_text(encoding="utf-8")
view = ensure_include(
    view,
    '#include "Cafe/HW/Latte/Core/LattePerformanceMonitor.h"\n',
    '#include "diagnostics/RuntimeDiagnostics.h"\n',
    "texture view diag include",
)

view_ctor_anchor = '''\tm_uniqueId = VulkanRenderer::GetInstance()->GenUniqueId();
}

LatteTextureViewVk::~LatteTextureViewVk()
{
'''
view_ctor_new = '''\tm_uniqueId = VulkanRenderer::GetInstance()->GenUniqueId();
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::TextureViewLifecycle))
\t\tcemuLog_log(LogType::Force, "[TEXTURE_VIEW] CREATE id={} addr={:08x} mip={}+{} slice={}+{} format=0x{:x} dim={}",
\t\t\tm_uniqueId, baseTexture->physAddress, firstMip, numMip, firstSlice, numSlice, (uint32)format, (uint32)dim);
}

LatteTextureViewVk::~LatteTextureViewVk()
{
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::TextureViewLifecycle))
\t\tcemuLog_log(LogType::Force, "[TEXTURE_VIEW] DELETE id={} addr={:08x} mip={}+{} slice={}+{}",
\t\t\tm_uniqueId, baseTexture->physAddress, firstMip, numMip, firstSlice, numSlice);
'''
view = replace_once(view, view_ctor_anchor, view_ctor_new, "texture view lifecycle")
view_path.write_text(view, encoding="utf-8", newline="\n")


vpad_path = Path("src/Cafe/OS/libs/vpad/vpad.cpp")
vpad = vpad_path.read_text(encoding="utf-8")
vpad = ensure_include(
    vpad,
    '#include "WindowSystem.h"\n',
    '#include "diagnostics/RuntimeDiagnostics.h"\n',
    "VPAD diag include",
)
vpad_read_anchor = '''\t\tconst auto controller = InputManager::instance().get_vpad_controller(channel);
\t\tif (!controller)
'''
vpad_read_new = '''\t\tconst auto controller = InputManager::instance().get_vpad_controller(channel);
\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::VPAD) ||
\t\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ChannelMapping) ||
\t\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::InputReadSummary))
\t\t{
\t\t\tstatic std::atomic_uint64_t s_vpadReadSeq{0};
\t\t\tconst uint64_t n = s_vpadReadSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\t\tif (n <= 200 || (n % 10000ULL) == 0)
\t\t\t{
\t\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::VPAD))
\t\t\t\t\tcemuLog_log(LogType::Force, "[VPAD_DIAG] n={} channel={} length={} connected={} focus={}",
\t\t\t\t\t\tn, channel, length, controller ? 1 : 0, WindowSystem::InputConfigWindowHasFocus() ? 1 : 0);
\t\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ChannelMapping))
\t\t\t\t\tcemuLog_log(LogType::Force, "[CHANNEL_MAPPING] api=VPAD channel={} player={}",
\t\t\t\t\t\tchannel, controller ? (sint32)controller->player_index() : -1);
\t\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::InputReadSummary))
\t\t\t\t\tcemuLog_log(LogType::Force, "[INPUT_SUMMARY] api=VPAD n={} channel={} connected={}",
\t\t\t\t\t\tn, channel, controller ? 1 : 0);
\t\t\t}
\t\t}
\t\tif (!controller)
'''
vpad = replace_once(vpad, vpad_read_anchor, vpad_read_new, "VPAD read/channel hook")
vpad_path.write_text(vpad, encoding="utf-8", newline="\n")

pad_path = Path("src/Cafe/OS/libs/padscore/padscore.cpp")
pad = pad_path.read_text(encoding="utf-8")
pad = ensure_include(
    pad,
    '#include "input/InputManager.h"\n',
    '#include "diagnostics/RuntimeDiagnostics.h"\n',
    "KPAD diag include",
)
kpad_anchor = '''\tconst auto controller = InputManager::instance().get_wpad_controller(channel);
\tif (!controller)
'''
kpad_new = '''\tconst auto controller = InputManager::instance().get_wpad_controller(channel);
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::KPAD) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ChannelMapping) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::InputReadSummary))
\t{
\t\tstatic std::atomic_uint64_t s_kpadReadSeq{0};
\t\tconst uint64_t n = s_kpadReadSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 200 || (n % 10000ULL) == 0)
\t\t{
\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::KPAD))
\t\t\t\tcemuLog_log(LogType::Force, "[KPAD_DIAG] n={} channel={} length={} connected={} initialized={}",
\t\t\t\t\tn, channel, length, controller ? 1 : 0, g_kpadIsInited ? 1 : 0);
\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ChannelMapping))
\t\t\t\tcemuLog_log(LogType::Force, "[CHANNEL_MAPPING] api=KPAD channel={} player={}",
\t\t\t\t\tchannel, controller ? (sint32)controller->player_index() : -1);
\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::InputReadSummary))
\t\t\t\tcemuLog_log(LogType::Force, "[INPUT_SUMMARY] api=KPAD n={} channel={} connected={}",
\t\t\t\t\tn, channel, controller ? 1 : 0);
\t\t}
\t}
\tif (!controller)
'''
pad = replace_once(pad, kpad_anchor, kpad_new, "KPAD read/channel hook")

disconnect_anchor = '''\t\t\t\t\t\tcemuLog_log(LogType::InputAPI, "Calling WPADConnectCallback({}, {})", i, WPAD_ERR_NO_CONTROLLER);
\t\t\t\t\t\tPPCCoreCallback(g_padscore.controller_data[i].connectCallback, i, WPAD_ERR_NO_CONTROLLER);
'''
disconnect_new = '''\t\t\t\t\t\tcemuLog_log(LogType::InputAPI, "Calling WPADConnectCallback({}, {})", i, WPAD_ERR_NO_CONTROLLER);
\t\t\t\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ConnectDisconnect))
\t\t\t\t\t\t\tcemuLog_log(LogType::Force, "[CONNECT_STATE] api=WPAD channel={} state=disconnect", i);
\t\t\t\t\t\tPPCCoreCallback(g_padscore.controller_data[i].connectCallback, i, WPAD_ERR_NO_CONTROLLER);
'''
disconnect_count = pad.count(disconnect_anchor)
if disconnect_count != 1:
    raise RuntimeError(f"WPAD disconnect anchor: expected 1, found {disconnect_count}")
pad = pad.replace(disconnect_anchor, disconnect_new, 1)

connect_ok_anchor = '''\t\t\t\t\t\tcemuLog_log(LogType::InputAPI, "Calling WPADConnectCallback({}, {})", i, WPAD_ERR_NONE);
\t\t\t\t\t\tPPCCoreCallback(g_padscore.controller_data[i].connectCallback, i, WPAD_ERR_NONE);
'''
connect_ok_new = '''\t\t\t\t\t\tcemuLog_log(LogType::InputAPI, "Calling WPADConnectCallback({}, {})", i, WPAD_ERR_NONE);
\t\t\t\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ConnectDisconnect))
\t\t\t\t\t\t\tcemuLog_log(LogType::Force, "[CONNECT_STATE] api=WPAD channel={} state=connect", i);
\t\t\t\t\t\tPPCCoreCallback(g_padscore.controller_data[i].connectCallback, i, WPAD_ERR_NONE);
'''
pad = replace_once(pad, connect_ok_anchor, connect_ok_new, "WPAD connect state")
pad_path.write_text(pad, encoding="utf-8", newline="\n")

input_path = Path("src/input/InputManager.cpp")
inp = input_path.read_text(encoding="utf-8")
inp = ensure_include(
    inp,
    '#include "util/EventService.h"\n',
    '#include "diagnostics/RuntimeDiagnostics.h"\n',
    "InputManager diag include",
)

player_anchor = '''EmulatedControllerPtr InputManager::set_controller(EmulatedControllerPtr controller)
{
\tauto prev_controller = delete_controller(controller->player_index());
'''
player_new = '''EmulatedControllerPtr InputManager::set_controller(EmulatedControllerPtr controller)
{
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PlayerIndex))
\t\tcemuLog_log(LogType::Force, "[PLAYER_INDEX] action=set player={} type={}",
\t\t\tcontroller->player_index(), (uint32)controller->type());
\tauto prev_controller = delete_controller(controller->player_index());
'''
inp = replace_once(inp, player_anchor, player_new, "player index set")

slot_vpad_anchor = '''\tcase EmulatedController::Type::VPAD:
\t\tfor (auto& pad : m_vpad)
\t\t{
\t\t\tif (!pad)
\t\t\t{
\t\t\t\tpad.swap(controller);
\t\t\t\treturn prev_controller;
'''
slot_vpad_new = '''\tcase EmulatedController::Type::VPAD:
\t\tfor (size_t slot = 0; slot < m_vpad.size(); ++slot)
\t\t{
\t\t\tauto& pad = m_vpad[slot];
\t\t\tif (!pad)
\t\t\t{
\t\t\t\tconst size_t player = controller->player_index();
\t\t\t\tpad.swap(controller);
\t\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ControllerSlot))
\t\t\t\t\tcemuLog_log(LogType::Force, "[CONTROLLER_SLOT] api=VPAD slot={} player={}", slot, player);
\t\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ConnectDisconnect))
\t\t\t\t\tcemuLog_log(LogType::Force, "[CONNECT_STATE] api=VPAD slot={} player={} state=assigned", slot, player);
\t\t\t\treturn prev_controller;
'''
inp = replace_once(inp, slot_vpad_anchor, slot_vpad_new, "VPAD controller slot")

slot_wpad_anchor = '''\tdefault:
\t\tfor (auto& pad : m_wpad)
\t\t{
\t\t\tif (!pad)
\t\t\t{
\t\t\t\tpad.swap(controller);
\t\t\t\treturn prev_controller;
'''
slot_wpad_new = '''\tdefault:
\t\tfor (size_t slot = 0; slot < m_wpad.size(); ++slot)
\t\t{
\t\t\tauto& pad = m_wpad[slot];
\t\t\tif (!pad)
\t\t\t{
\t\t\t\tconst size_t player = controller->player_index();
\t\t\t\tpad.swap(controller);
\t\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ControllerSlot))
\t\t\t\t\tcemuLog_log(LogType::Force, "[CONTROLLER_SLOT] api=WPAD slot={} player={}", slot, player);
\t\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ConnectDisconnect))
\t\t\t\t\tcemuLog_log(LogType::Force, "[CONNECT_STATE] api=WPAD slot={} player={} state=assigned", slot, player);
\t\t\t\treturn prev_controller;
'''
inp = replace_once(inp, slot_wpad_anchor, slot_wpad_new, "WPAD controller slot")
input_path.write_text(inp, encoding="utf-8", newline="\n")


cp_path = Path("src/Cafe/HW/Latte/Core/LatteCommandProcessor.cpp")
cp = cp_path.read_text(encoding="utf-8")
cp = ensure_include(
    cp,
    '#include "Cafe/CafeSystem.h"\n',
    '#include "diagnostics/RuntimeDiagnostics.h"\n',
    "Latte CP diag include",
)
draw_start_anchor = '''\tvoid executeDraw(uint32 count, bool isAutoIndex, MPTR physIndices)
\t{
\t\tuint32 baseVertex = LatteGPUState.contextRegister[mmSQ_VTX_BASE_VTX_LOC];
'''
draw_start_new = '''\tvoid executeDraw(uint32 count, bool isAutoIndex, MPTR physIndices)
\t{
\t\tconst bool diagLatteTiming = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::LatteThreadTiming);
\t\tconst uint64_t diagLatteStart = diagLatteTiming ? RuntimeDiagnostics::NowNs() : 0;
\t\tuint32 baseVertex = LatteGPUState.contextRegister[mmSQ_VTX_BASE_VTX_LOC];
'''
cp = replace_once(cp, draw_start_anchor, draw_start_new, "LatteThread draw timing start")
draw_end_anchor = '''\t\tperformanceMonitor.cycle[performanceMonitor.cycleIndex].drawCallCounter++;
'''
draw_end_new = '''\t\tif (diagLatteTiming)
\t\t{
\t\t\tstatic std::atomic_uint64_t s_latteDrawSeq{0};
\t\t\tconst uint64_t n = s_latteDrawSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\t\tconst uint64_t ns = RuntimeDiagnostics::NowNs() - diagLatteStart;
\t\t\tif (n <= 200 || (n % 10000ULL) == 0)
\t\t\t\tcemuLog_log(LogType::Force, "[LATTE_THREAD_TIMING] n={} drawNs={} indices={} instances={} autoIndex={}",
\t\t\t\t\tn, ns, count, numInstances, isAutoIndex ? 1 : 0);
\t\t}
\t\tperformanceMonitor.cycle[performanceMonitor.cycleIndex].drawCallCounter++;
'''
cp = replace_once(cp, draw_end_anchor, draw_end_new, "LatteThread draw timing end")
cp_path.write_text(cp, encoding="utf-8", newline="\n")


verify_path = Path("tools/diagnostics/Verify-DiagnosticCoverage.py")
verify = verify_path.read_text(encoding="utf-8")
verify = replace_once(
    verify,
    '''    "FeedbackUse": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::FeedbackUse"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[FEEDBACK_USE]")],
''',
    '''    "FeedbackUse": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::FeedbackUse"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[FEEDBACK_USE]")],
    "FeedbackFallback": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::FeedbackFallback"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[FEEDBACK_FALLBACK]")],
    "FeedbackSelfDependency": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::FeedbackSelfDependency"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[FEEDBACK_SELF_DEP]")],
    "ImageLayoutTransition": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h", "Flag::ImageLayoutTransition"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h", "[IMAGE_LAYOUT]")],
    "FeedbackPassSplit": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::FeedbackPassSplit"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[FEEDBACK_PASS_SPLIT]")],

    # Texture
    "TextureLifecycle": [("src/Cafe/HW/Latte/Core/LatteTextureLegacy.cpp", "Flag::TextureLifecycle"), ("src/Cafe/HW/Latte/Core/LatteTextureCache.cpp", "[TEXTURE_LIFECYCLE]")],
    "TextureViewLifecycle": [("src/Cafe/HW/Latte/Renderer/Vulkan/LatteTextureViewVk.cpp", "Flag::TextureViewLifecycle"), ("src/Cafe/HW/Latte/Renderer/Vulkan/LatteTextureViewVk.cpp", "[TEXTURE_VIEW]")],
    "TextureCache": [("src/Cafe/HW/Latte/Core/LatteTextureLegacy.cpp", "Flag::TextureCache"), ("src/Cafe/HW/Latte/Core/LatteTextureLegacy.cpp", "[TEXTURE_CACHE]")],
    "TextureAliasing": [("src/Cafe/HW/Latte/Core/LatteTextureCache.cpp", "Flag::TextureAliasing"), ("src/Cafe/HW/Latte/Core/LatteTextureCache.cpp", "[TEXTURE_ALIAS]")],
    "SurfaceInvalidation": [("src/Cafe/HW/Latte/Core/LatteTextureCache.cpp", "Flag::SurfaceInvalidation"), ("src/Cafe/HW/Latte/Core/LatteTextureCache.cpp", "[SURFACE_INVALIDATE]")],
    "SuspiciousTextureState": [("src/Cafe/HW/Latte/Core/LatteTextureLegacy.cpp", "Flag::SuspiciousTextureState"), ("src/Cafe/HW/Latte/Core/LatteTextureLegacy.cpp", "[SUSPICIOUS_TEXTURE]")],

    # Input
    "VPAD": [("src/Cafe/OS/libs/vpad/vpad.cpp", "Flag::VPAD"), ("src/Cafe/OS/libs/vpad/vpad.cpp", "[VPAD_DIAG]")],
    "KPAD": [("src/Cafe/OS/libs/padscore/padscore.cpp", "Flag::KPAD"), ("src/Cafe/OS/libs/padscore/padscore.cpp", "[KPAD_DIAG]")],
    "ControllerSlot": [("src/input/InputManager.cpp", "Flag::ControllerSlot"), ("src/input/InputManager.cpp", "[CONTROLLER_SLOT]")],
    "PlayerIndex": [("src/input/InputManager.cpp", "Flag::PlayerIndex"), ("src/input/InputManager.cpp", "[PLAYER_INDEX]")],
    "ChannelMapping": [("src/Cafe/OS/libs/vpad/vpad.cpp", "Flag::ChannelMapping"), ("src/Cafe/OS/libs/vpad/vpad.cpp", "[CHANNEL_MAPPING]")],
    "ConnectDisconnect": [("src/input/InputManager.cpp", "Flag::ConnectDisconnect"), ("src/input/InputManager.cpp", "[CONNECT_STATE]")],
    "InputReadSummary": [("src/Cafe/OS/libs/vpad/vpad.cpp", "Flag::InputReadSummary"), ("src/Cafe/OS/libs/vpad/vpad.cpp", "[INPUT_SUMMARY]")],

    # Extended performance
    "LatteThreadTiming": [("src/Cafe/HW/Latte/Core/LatteCommandProcessor.cpp", "Flag::LatteThreadTiming"), ("src/Cafe/HW/Latte/Core/LatteCommandProcessor.cpp", "[LATTE_THREAD_TIMING]")],
    "PerfPipelineCache": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::PerfPipelineCache"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[PERF_PIPE_CACHE]")],
    "BarrierCount": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::BarrierCount"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[BARRIER_COUNT]")],
    "RenderPassCount": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::RenderPassCount"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[RENDERPASS_COUNT]")],
    "UploadStallTiming": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::UploadStallTiming"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[UPLOAD_STALL]")],
''',
    "coverage verifier remaining hooks",
)

ui_check = r'''
ui = text("src/gui/wxgui/MainWindow.cpp")
ui_match = re.search(r"static constexpr DiagItem kDiagItems\[\] = \{(.*?)\n\};", ui, re.S)
if not ui_match:
    raise RuntimeError("diagnostic coverage missing: UI kDiagItems")
ui_flags = re.findall(r"DiagFlag::([A-Za-z0-9_]+)", ui_match.group(1))
if len(ui_flags) != 77:
    raise RuntimeError(f"unexpected diagnostics UI inventory: expected 77, got {len(ui_flags)}")
if set(ui_flags) != implemented_cases:
    raise RuntimeError(f"UI/IsImplemented mismatch: ui-only={sorted(set(ui_flags)-implemented_cases)} implemented-only={sorted(implemented_cases-set(ui_flags))}")
print("[diag-verify] OK UI coverage 77/77")
'''
verify = replace_once(
    verify,
    '''print(f"[diag-verify] OK IsImplemented coverage count={len(implemented_cases)}")

for flag, checks in HOOKS.items():
''',
    '''print(f"[diag-verify] OK IsImplemented coverage count={len(implemented_cases)}")
''' + ui_check + '''
for flag, checks in HOOKS.items():
''',
    "UI 77 coverage assertion",
)
verify_path.write_text(verify, encoding="utf-8", newline="\n")

print("[complete-diagnostics] remaining 22 probes installed; verifier now requires UI coverage 77/77")
