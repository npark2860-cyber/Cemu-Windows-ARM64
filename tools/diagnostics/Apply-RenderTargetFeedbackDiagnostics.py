from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# Final seven diagnostics: make the remaining grey controls selectable only
# after concrete runtime consumers have been installed.
header_path = Path("src/diagnostics/RuntimeDiagnostics.h")
header = header_path.read_text(encoding="utf-8")
header = replace_once(
    header,
    '''    // Render-target / synchronization diagnostics
    case Flag::RenderPassBeginEnd:
''',
    '''    // Shader/render-target/feedback diagnostics
    case Flag::ShaderInterface:
    case Flag::FBOChanges:
    case Flag::AttachmentUsage:
    case Flag::LoadStoreBehavior:
    case Flag::RenderTargetAliasing:
    case Flag::FeedbackSupport:
    case Flag::FeedbackUse:

    // Render-target / synchronization diagnostics
    case Flag::RenderPassBeginEnd:
''',
    "final seven IsImplemented cases",
)
header_path.write_text(header, encoding="utf-8", newline="\n")

core_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
core = core_path.read_text(encoding="utf-8")

pipeline_anchor = '''PipelineInfo* VulkanRenderer::draw_createGraphicsPipeline(uint32 indexCount)
{
\tconst auto fetchShader = LatteSHRC_GetActiveFetchShader();
\tconst auto vertexShader = LatteSHRC_GetActiveVertexShader();
\tconst auto geometryShader = LatteSHRC_GetActiveGeometryShader();
\tconst auto pixelShader = LatteSHRC_GetActivePixelShader();
\tauto cachedFboVk = (CachedFBOVk*)m_state.activeFBO;

'''
pipeline_new = pipeline_anchor + '''\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ShaderInterface))
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
\t\t\t\t\tif (binding >= 0)
\t\t\t\t\t\t++uniformBufferCount;
\t\t\t\tuint32 attributeCount = 0;
\t\t\t\tfor (sint8 attr : shader->resourceMapping.attributeMapping)
\t\t\t\t\tif (attr >= 0)
\t\t\t\t\t\t++attributeCount;
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[SHADER_INTERFACE] n={} stage={} base={:016x} aux={:016x} set={} textures={} texBase={} uniformVars={} uniformBuffers={} tfStorage={} attributes={} outputParams=0x{:08x} pixelOutputs=0x{:08x} depthOut={} ringOut={} ringIn={}",
\t\t\t\t\tn, stage, shader->baseHash, shader->auxHash, (sint32)shader->resourceMapping.setIndex,
\t\t\t\t\t(sint32)shader->resourceMapping.textureUnitCount, (sint32)shader->resourceMapping.textureUnitBaseBindingPoint,
\t\t\t\t\t(sint32)shader->resourceMapping.uniformVarsBufferBindingPoint, uniformBufferCount,
\t\t\t\t\t(sint32)shader->resourceMapping.tfStorageBindingPoint, attributeCount, shader->outputParameterMask,
\t\t\t\t\tshader->pixelColorOutputMask, shader->depthMask ? 1 : 0, shader->ringParameterCount,
\t\t\t\t\tshader->ringParameterCountFromPrevStage);
\t\t\t};
\t\t\tlogInterface("vs", vertexShader);
\t\t\tlogInterface("gs", geometryShader);
\t\t\tlogInterface("ps", pixelShader);
\t\t}
\t}

'''
core = replace_once(core, pipeline_anchor, pipeline_new, "shader interface hook")

load_anchor = '''\tif (RTExpEnabled("rt-force-sync") && !readFlushRequired)
\t{
\t\treadFlushRequired = true;
\t\tif (RTDiagStatsEnabled())
\t\t\t++s_rtStatForcedLoadSync;
\t}
\t// barrier here
\tif (readFlushRequired)
'''
load_new = '''\tif (RTExpEnabled("rt-force-sync") && !readFlushRequired)
\t{
\t\treadFlushRequired = true;
\t\tif (RTDiagStatsEnabled())
\t\t\t++s_rtStatForcedLoadSync;
\t}
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::LoadStoreBehavior))
\t{
\t\tstatic std::atomic_uint64_t s_loadDiagSeq{0};
\t\tconst uint64_t n = s_loadDiagSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 200 || (n % 1000ULL) == 0)
\t\t\tcemuLog_log(LogType::Force, "[LOAD_STORE] phase=load n={} fbo={:016x} textures={} flush={} raw={} waw={} barrier={}",
\t\t\t\tn, fboVk->key, fboVk->GetTextures().size(), m_state.currentFlushIndex,
\t\t\t\treadBeforeWrite ? 1 : 0, writeBeforeWrite ? 1 : 0, readFlushRequired ? 1 : 0);
\t}
\t// barrier here
\tif (readFlushRequired)
'''
core = replace_once(core, load_anchor, load_new, "load/store load hook")

store_anchor = '''void VulkanRenderer::sync_RenderPassStoreTextures(CachedFBOVk* fboVk)
{
\tuint32 flushIndex = m_state.currentFlushIndex;
\tfor (auto& tex : fboVk->GetTextures())
\t{
\t\tLatteTextureVk* texVk = (LatteTextureVk*)tex;
\t\ttexVk->m_vkFlushIndex_write = flushIndex;
\t}
}
'''
store_new = '''void VulkanRenderer::sync_RenderPassStoreTextures(CachedFBOVk* fboVk)
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
\t\t\tcemuLog_log(LogType::Force, "[LOAD_STORE] phase=store n={} fbo={:016x} textures={} flush={}",
\t\t\t\tn, fboVk->key, fboVk->GetTextures().size(), flushIndex);
\t}
}
'''
core = replace_once(core, store_anchor, store_new, "load/store store hook")

feedback_anchor = '''\tif (RTDiagStatsEnabled() && experimentSplit && !baseOverridePassReuse)
\t\t++s_rtStatForcedSplit;

\tif (!overridePassReuse && m_state.activeRenderpassFBO == fboVk)
'''
feedback_new = '''\tif (RTDiagStatsEnabled() && experimentSplit && !baseOverridePassReuse)
\t\t++s_rtStatForcedSplit;

\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::FeedbackSupport))
\t{
\t\tstatic std::atomic_bool s_feedbackSupportLogged{false};
\t\tif (!s_feedbackSupportLogged.exchange(true, std::memory_order_relaxed))
\t\t{
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[FEEDBACK_SUPPORT] layout={} dynamicState={} active={}",
\t\t\t\tm_featureControl.deviceExtensions.attachment_feedback_loop_layout ? 1 : 0,
\t\t\t\tm_featureControl.deviceExtensions.attachment_feedback_loop_dynamic_state ? 1 : 0,
\t\t\t\tUseAttachmentFeedbackLoop() ? 1 : 0);
\t\t}
\t}
\tif (feedbackLoopHandlesSelfDependency && RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::FeedbackUse))
\t{
\t\tstatic std::atomic_uint64_t s_feedbackUseSeq{0};
\t\tconst uint64_t n = s_feedbackUseSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 200 || (n % 1000ULL) == 0)
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[FEEDBACK_USE] n={} fbo={:016x} aspect=0x{:x} vertexOrGeometry={} passSplit={}",
\t\t\t\tn, fboVk->key, (uint32)renderSelfDependencyInfo.GetAspectMask(),
\t\t\t\trenderSelfDependencyInfo.HasVertexOrGeometrySelfDependency() ? 1 : 0,
\t\t\t\tselfDependencyNeedsPassSplit ? 1 : 0);
\t}

\tif (!overridePassReuse && m_state.activeRenderpassFBO == fboVk)
'''
core = replace_once(core, feedback_anchor, feedback_new, "feedback support/use hooks")

new_pass_anchor = '''\tdraw_endRenderPass();
\tif (m_state.descriptorSetsChanged)
\t\tsync_inputTexturesChanged();

\t// assume that FBO changed, update self-dependency state
'''
new_pass_code = '''\tif (m_state.activeRenderpassFBO != fboVk && RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::FBOChanges))
\t{
\t\tstatic std::atomic_uint64_t s_fboChangeSeq{0};
\t\tconst uint64_t n = s_fboChangeSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 200 || (n % 1000ULL) == 0)
\t\t{
\t\t\tconst uint64_t prevKey = m_state.activeRenderpassFBO ? m_state.activeRenderpassFBO->key : 0;
\t\t\tconst auto extend = fboVk->GetExtend();
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[FBO_CHANGE] n={} prev={:016x} next={:016x} size={}x{} colors={} depth={}",
\t\t\t\tn, prevKey, fboVk->key, extend.width, extend.height,
\t\t\t\tfboVk->calculateNumColorBuffers(), fboVk->hasDepthBuffer() ? 1 : 0);
\t\t}
\t}

\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::AttachmentUsage))
\t{
\t\tstatic std::atomic_uint64_t s_attachmentUseSeq{0};
\t\tconst uint64_t n = s_attachmentUseSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 200 || (n % 1000ULL) == 0)
\t\t{
\t\t\tfor (uint32 i = 0; i < 8; ++i)
\t\t\t{
\t\t\t\tauto view = fboVk->colorBuffer[i].texture;
\t\t\t\tif (!view)
\t\t\t\t\tcontinue;
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[ATTACHMENT_USE] n={} fbo={:016x} kind=color slot={} addr={:08x} mip={}+{} slice={}+{} format=0x{:x} dim={}",
\t\t\t\t\tn, fboVk->key, i, view->baseTexture->physAddress, view->firstMip, view->numMip,
\t\t\t\t\tview->firstSlice, view->numSlice, (uint32)view->format, (uint32)view->dim);
\t\t\t}
\t\t\tauto depthView = fboVk->depthBuffer.texture;
\t\t\tif (depthView)
\t\t\t{
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[ATTACHMENT_USE] n={} fbo={:016x} kind=depth slot=0 addr={:08x} mip={}+{} slice={}+{} format=0x{:x} dim={} stencil={}",
\t\t\t\t\tn, fboVk->key, depthView->baseTexture->physAddress, depthView->firstMip, depthView->numMip,
\t\t\t\t\tdepthView->firstSlice, depthView->numSlice, (uint32)depthView->format, (uint32)depthView->dim,
\t\t\t\t\tfboVk->depthBuffer.hasStencil ? 1 : 0);
\t\t\t}
\t\t}
\t}

\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::RenderTargetAliasing))
\t{
\t\tauto logAlias = [fboVk](const char* aKind, uint32 aSlot, LatteTextureView* a,
\t\t\tconst char* bKind, uint32 bSlot, LatteTextureView* b)
\t\t{
\t\t\tif (!a || !b)
\t\t\t\treturn;
\t\t\tconst bool sameBase = a->baseTexture == b->baseTexture;
\t\t\tconst bool sameAddress = a->baseTexture->physAddress == b->baseTexture->physAddress;
\t\t\tconst auto aLow = a->baseTexture->texDataPtrLow;
\t\t\tconst auto aHigh = a->baseTexture->texDataPtrHigh;
\t\t\tconst auto bLow = b->baseTexture->texDataPtrLow;
\t\t\tconst auto bHigh = b->baseTexture->texDataPtrHigh;
\t\t\tconst bool memoryOverlap = aLow != 0 && aHigh != 0 && bLow != 0 && bHigh != 0 &&
\t\t\t\taLow <= bHigh && bLow <= aHigh;
\t\t\tif (!sameBase && !sameAddress && !memoryOverlap)
\t\t\t\treturn;
\t\t\tconst bool mipOverlap = a->firstMip < (b->firstMip + b->numMip) &&
\t\t\t\tb->firstMip < (a->firstMip + a->numMip);
\t\t\tconst bool sliceOverlap = a->firstSlice < (b->firstSlice + b->numSlice) &&
\t\t\t\tb->firstSlice < (a->firstSlice + a->numSlice);
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[RT_ALIAS] fbo={:016x} a={}{} b={}{} sameBase={} sameAddr={} memoryOverlap={} subresourceOverlap={} aAddr={:08x} bAddr={:08x} aMip={}+{} bMip={}+{} aSlice={}+{} bSlice={}+{}",
\t\t\t\tfboVk->key, aKind, aSlot, bKind, bSlot, sameBase ? 1 : 0, sameAddress ? 1 : 0,
\t\t\t\tmemoryOverlap ? 1 : 0, (sameBase && mipOverlap && sliceOverlap) ? 1 : 0,
\t\t\t\ta->baseTexture->physAddress, b->baseTexture->physAddress,
\t\t\t\ta->firstMip, a->numMip, b->firstMip, b->numMip,
\t\t\t\ta->firstSlice, a->numSlice, b->firstSlice, b->numSlice);
\t\t};
\t\tfor (uint32 i = 0; i < 8; ++i)
\t\t{
\t\t\tauto a = fboVk->colorBuffer[i].texture;
\t\t\tif (!a)
\t\t\t\tcontinue;
\t\t\tfor (uint32 j = i + 1; j < 8; ++j)
\t\t\t\tlogAlias("C", i, a, "C", j, fboVk->colorBuffer[j].texture);
\t\t\tlogAlias("C", i, a, "D", 0, fboVk->depthBuffer.texture);
\t\t}
\t}

''' + new_pass_anchor
core = replace_once(core, new_pass_anchor, new_pass_code, "FBO/attachment/alias hooks")

core_path.write_text(core, encoding="utf-8", newline="\n")

verify_path = Path("tools/diagnostics/Verify-DiagnosticCoverage.py")
verify = verify_path.read_text(encoding="utf-8")
verify = replace_once(
    verify,
    '''    "DumpEveryShader": [("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp", "Flag::DumpEveryShader"), ("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp", "[SHADER_DUMP_ALL]")],

    # Render-target / synchronization
''',
    '''    "DumpEveryShader": [("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp", "Flag::DumpEveryShader"), ("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp", "[SHADER_DUMP_ALL]")],
    "ShaderInterface": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::ShaderInterface"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[SHADER_INTERFACE]")],

    # Render-target / synchronization
    "FBOChanges": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::FBOChanges"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[FBO_CHANGE]")],
    "AttachmentUsage": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::AttachmentUsage"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[ATTACHMENT_USE]")],
    "LoadStoreBehavior": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::LoadStoreBehavior"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[LOAD_STORE]")],
    "RenderTargetAliasing": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::RenderTargetAliasing"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[RT_ALIAS]")],
    "FeedbackSupport": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::FeedbackSupport"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[FEEDBACK_SUPPORT]")],
    "FeedbackUse": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::FeedbackUse"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[FEEDBACK_USE]")],
''',
    "coverage verifier final seven hooks",
)
verify_path.write_text(verify, encoding="utf-8", newline="\n")

print("[rt-feedback-final] seven final diagnostics installed; all UI diagnostics now have concrete runtime consumers")
