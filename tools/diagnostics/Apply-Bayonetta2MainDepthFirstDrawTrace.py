from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 anchor, found {count}")
    return text.replace(old, new, 1)


path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    '#include "Cafe/GameProfile/GameProfile.h"\n',
    '#include "Cafe/GameProfile/GameProfile.h"\n#include "Cafe/CafeSystem.h"\n',
    "CafeSystem include",
)

text = replace_once(
    text,
    'extern bool hasValidFramebufferAttached;\n',
    '''extern bool hasValidFramebufferAttached;

// Bayonetta 2 JP observation-only trace.
// Records the first main-depth draw while a same-address smaller-pitch alias is newer.
// No render, depth, texture-cache, synchronization or pipeline behavior is changed.
static uint64 s_bayo2MainDepthFirstDrawCount = 0;
static uint64 s_bayo2MainDepthLastLoggedAliasEvent = 0;
''',
    "trace state",
)

anchor = '''void VulkanRenderer::draw_execute(uint32 baseVertex, uint32 baseInstance, uint32 instanceCount, uint32 count, MPTR indexDataMPTR, Latte::LATTE_VGT_DMA_INDEX_TYPE::E_INDEX_TYPE indexType, const LatteDrawcallContext& drawcallContext)
{
\tif (drawcallContext.isFirst)
'''

replacement = '''void VulkanRenderer::draw_execute(uint32 baseVertex, uint32 baseInstance, uint32 instanceCount, uint32 count, MPTR indexDataMPTR, Latte::LATTE_VGT_DMA_INDEX_TYPE::E_INDEX_TYPE indexType, const LatteDrawcallContext& drawcallContext)
{
\tif (CafeSystem::GetForegroundTitleId() == 0x000500001011B900ULL && m_state.activeFBO)
\t{
\t\tauto* fbo = (CachedFBOVk*)m_state.activeFBO;
\t\tif (fbo->depthBuffer.texture && fbo->depthBuffer.texture->baseTexture)
\t\t{
\t\t\tLatteTextureView* depthView = fbo->depthBuffer.texture;
\t\t\tLatteTexture* depth = depthView->baseTexture;
\t\t\tif (depth->physAddress == 0xF5442800u && depth->isDepth && depth->width == 1280 && depth->height == 720 && depth->pitch == 1280 && depth->sliceMipInfo)
\t\t\t{
\t\t\t\tauto* selfInfo = depth->sliceMipInfo + depth->GetSliceMipArrayIndex(depthView->firstSlice, depthView->firstMip);
\t\t\t\tuint64 newestOtherEvent = 0;
\t\t\t\tLatteTexture* newestOther = nullptr;
\t\t\t\tstd::vector<LatteTexture*> aliases;
\t\t\t\tLatteTC_LookupTexturesByPhysAddr(depth->physAddress, aliases);
\t\t\t\tfor (auto* alias : aliases)
\t\t\t\t{
\t\t\t\t\tif (!alias || alias == depth || !alias->isDepth || alias->format != depth->format || !alias->sliceMipInfo)
\t\t\t\t\t\tcontinue;
\t\t\t\t\tauto* aliasInfo = alias->sliceMipInfo + alias->GetSliceMipArrayIndex(0, 0);
\t\t\t\t\tif (aliasInfo->lastDynamicUpdate > newestOtherEvent)
\t\t\t\t\t{
\t\t\t\t\t\tnewestOtherEvent = aliasInfo->lastDynamicUpdate;
\t\t\t\t\t\tnewestOther = alias;
\t\t\t\t\t}
\t\t\t\t}

\t\t\t\tif (newestOther && newestOtherEvent > selfInfo->lastDynamicUpdate && newestOtherEvent != s_bayo2MainDepthLastLoggedAliasEvent)
\t\t\t\t{
\t\t\t\t\ts_bayo2MainDepthLastLoggedAliasEvent = newestOtherEvent;
\t\t\t\t\tconst uint64 n = ++s_bayo2MainDepthFirstDrawCount;
\t\t\t\t\tconst auto& depthControl = LatteGPUState.contextNew.DB_DEPTH_CONTROL;
\t\t\t\t\tconst bool zEnable = depthControl.get_Z_ENABLE();
\t\t\t\t\tconst bool zWrite = depthControl.get_Z_WRITE_ENABLE();
\t\t\t\t\tconst auto zFunc = depthControl.get_Z_FUNC();
\t\t\t\t\tconst bool stencilEnable = depthControl.get_STENCIL_ENABLE();
\t\t\t\t\tconst bool backStencilEnable = depthControl.get_BACK_STENCIL_ENABLE();
\t\t\t\t\tconst auto stencilFuncF = depthControl.get_STENCIL_FUNC_F();
\t\t\t\t\tconst auto stencilFuncB = depthControl.get_STENCIL_FUNC_B();
\t\t\t\t\tconst bool priorDepthAffectsPass = zEnable && (uint32)zFunc != 7u;

\t\t\t\t\tauto* fetchShader = LatteSHRC_GetActiveFetchShader();
\t\t\t\t\tauto* vertexShader = LatteSHRC_GetActiveVertexShader();
\t\t\t\t\tauto* geometryShader = LatteSHRC_GetActiveGeometryShader();
\t\t\t\t\tauto* pixelShader = LatteSHRC_GetActivePixelShader();
\t\t\t\t\tuint64 minimalHash = 0;
\t\t\t\t\tuint64 pipelineHash = 0;
\t\t\t\t\tif (fetchShader && vertexShader && fbo->GetRenderPassObj())
\t\t\t\t\t{
\t\t\t\t\t\tminimalHash = draw_calculateMinimalGraphicsPipelineHash(fetchShader, LatteGPUState.contextNew);
\t\t\t\t\t\tpipelineHash = draw_calculateGraphicsPipelineHash(fetchShader, vertexShader, geometryShader, pixelShader, fbo->GetRenderPassObj(), LatteGPUState.contextNew);
\t\t\t\t\t}

\t\t\t\t\tconst uint32* raw = LatteGPUState.contextNew.GetRawView();
\t\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\t"[BAYO2_MAIN_DEPTH_FIRST_DRAW] n={} draw={} selfEvent={} newestAliasEvent={} alias={}x{} pitch={} priorDepthAffects={} zEnable={} zWrite={} zFunc={} stencilEnable={} backStencil={} stencilFuncF={} stencilFuncB={} dbDepthControl=0x{:08x} stencilRefMask=0x{:08x} stencilRefMaskBF=0x{:08x} primitive={} count={} instances={} firstSeq={} indexType={} minimalHash={:016x} pipelineHash={:016x} vs={:016x} ps={:016x} psAux={:016x} gs={:016x}",
\t\t\t\t\t\tn, LatteGPUState.drawCallCounter, selfInfo->lastDynamicUpdate, newestOtherEvent,
\t\t\t\t\t\tnewestOther->width, newestOther->height, newestOther->pitch,
\t\t\t\t\t\tpriorDepthAffectsPass ? 1 : 0, zEnable ? 1 : 0, zWrite ? 1 : 0, (uint32)zFunc,
\t\t\t\t\t\tstencilEnable ? 1 : 0, backStencilEnable ? 1 : 0, (uint32)stencilFuncF, (uint32)stencilFuncB,
\t\t\t\t\t\traw[Latte::REGADDR::DB_DEPTH_CONTROL], raw[mmDB_STENCILREFMASK], raw[mmDB_STENCILREFMASK_BF],
\t\t\t\t\t\t(uint32)LatteGPUState.contextNew.VGT_PRIMITIVE_TYPE.get_PRIMITIVE_MODE(), count, instanceCount,
\t\t\t\t\t\tdrawcallContext.isFirst ? 1 : 0, (uint32)indexType, minimalHash, pipelineHash,
\t\t\t\t\t\tvertexShader ? vertexShader->baseHash : 0ULL,
\t\t\t\t\t\tpixelShader ? pixelShader->baseHash : 0ULL,
\t\t\t\t\t\tpixelShader ? pixelShader->auxHash : 0ULL,
\t\t\t\t\t\tgeometryShader ? geometryShader->baseHash : 0ULL);
\t\t\t\t}
\t\t\t}
\t\t}
\t}

\tif (drawcallContext.isFirst)
'''

text = replace_once(text, anchor, replacement, "draw_execute observation hook")

required = [
    "[BAYO2_MAIN_DEPTH_FIRST_DRAW]",
    "priorDepthAffectsPass",
    "LatteTC_LookupTexturesByPhysAddr",
    "CafeSystem::GetForegroundTitleId() == 0x000500001011B900ULL",
    "raw[Latte::REGADDR::DB_DEPTH_CONTROL]",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"missing generated marker: {marker}")

for forbidden in [
    "BAYO2_MAIN_DEPTH_FORCE",
    "LatteTexture_ReloadData(",
    "LatteTexture_SyncSlice(",
    "texture_copyImageSubData(",
    "vkCmdClearAttachments(",
    "vkCmdCopyImage(",
]:
    if forbidden in replacement:
        raise RuntimeError(f"behavior-changing call detected in inserted trace: {forbidden}")

path.write_text(text, encoding="utf-8", newline="\n")
