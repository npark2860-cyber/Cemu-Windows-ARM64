from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


def replace_count(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} anchors, found {count}")
    return text.replace(old, new)


# -----------------------------------------------------------------------------
# Bayonetta 2 target0 PS unit11 depth-compare texture history trace.
#
# Observation-only. Run #16 showed one identical sampled-texture register / 4KiB
# prefix signature across all completed ZERO/NONZERO target0 generations. The one
# unresolved sampled input is PS unit11 at guest address 0xf57c8000: it is a
# GPU-updated depth texture and the guest-memory hash helper intentionally cannot
# read addresses >= 0x50000000. Record only the already-bound LatteTexture object
# bookkeeping once per target0 generation. No lookup, creation, readback or
# mutation is performed.
# -----------------------------------------------------------------------------
vk_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
vk = vk_path.read_text(encoding="utf-8")

helpers = '''static uint64 s_bayo2Target0DepthCompareHistoryLastGeneration = 0;

static void Bayo2Target0DepthCompareHistoryTrace_LogDraw(
\tPipelineInfo* pipelineInfo,
\tLatteTextureView* textureView,
\tuint32 baseVertex,
\tuint32 baseInstance,
\tuint32 instanceCount,
\tuint32 count,
\tMPTR indexDataMPTR,
\tLatte::LATTE_VGT_DMA_INDEX_TYPE::E_INDEX_TYPE indexType)
{
\tif (pipelineInfo == nullptr)
\t\treturn;

\tMPTR queryMPTRs[5]{};
\tuint64 generations[5]{};
\tsint32 targetIndices[5]{};
\tconst uint32 targetCount = Bayo2QueryTarget_GetActiveTargets(queryMPTRs, generations, targetIndices, 5);
\tif (targetCount == 0)
\t\treturn;

\tuint64 targetGeneration = 0;
\tbool target0Active = false;
\tfor (uint32 i = 0; i < targetCount; i++)
\t{
\t\tif (targetIndices[i] == 0 && queryMPTRs[i] == 0x46a92ec8)
\t\t{
\t\t\ttargetGeneration = generations[i];
\t\t\ttarget0Active = true;
\t\t\tbreak;
\t\t}
\t}
\tif (!target0Active || s_bayo2Target0DepthCompareHistoryLastGeneration == targetGeneration)
\t\treturn;
\ts_bayo2Target0DepthCompareHistoryLastGeneration = targetGeneration;

\tconst uint64 frameSeq = Bayo2QueryCorr_GetFrameSeq();
\tconst uint64 drawSeq = Bayo2QueryCorr_GetDrawSeq();
\tuint32* ctx = LatteGPUState.contextNew.GetRawView();
\tconst uint32 unit = 11;
\tconst uint32 reg = static_cast<uint32>(Latte::REGADDR::SQ_TEX_RESOURCE_WORD0_N_PS) + unit * 7;
\tconst MPTR registerPhys = static_cast<MPTR>(ctx[reg + 2] << 8);

\tif (textureView == nullptr || textureView->baseTexture == nullptr)
\t{
\t\tcemuLog_log(LogType::Force,
\t\t\t"[BAYO2_TARGET_DEPTHCOMPARE] query=46a92ec8 gen={} frame={} draw={} unit=11 registerPhys={:08x} bound=0",
\t\t\ttargetGeneration, frameSeq, drawSeq, registerPhys);
\t\treturn;
\t}

\tLatteTexture* tex = textureView->baseTexture;
\tcemuLog_log(LogType::Force,
\t\t"[BAYO2_TARGET_DEPTHCOMPARE] query=46a92ec8 gen={} frame={} draw={} unit=11 registerPhys={:08x} bound=1 "
\t\t"phys={:08x} mipPhys={:08x} isDepth={} stencil={} format={} tileMode={} swizzle={:08x} rtSwizzle={:08x} "
\t\t"size={}x{} pitch={} viewMip={}/{} viewSlice={}/{} dataDefined={} gpuUpdated={} readback={} reloadDynamic={} "
\t\t"writeEvent={} updateEvent={} updateFrame={} dataUpdateFrame={} reloadCount={} accessFrame={} unflushedDraw={} texDataHash2={:08x}",
\t\ttargetGeneration,
\t\tframeSeq,
\t\tdrawSeq,
\t\tregisterPhys,
\t\ttex->physAddress,
\t\ttex->physMipAddress,
\t\ttex->isDepth ? 1 : 0,
\t\ttex->hasStencil ? 1 : 0,
\t\tstatic_cast<uint32>(tex->format),
\t\tstatic_cast<uint32>(tex->tileMode),
\t\ttex->swizzle,
\t\ttex->lastRenderTargetSwizzle,
\t\ttex->width,
\t\ttex->height,
\t\ttex->pitch,
\t\ttextureView->firstMip,
\t\ttextureView->numMip,
\t\ttextureView->firstSlice,
\t\ttextureView->numSlice,
\t\ttex->isDataDefined ? 1 : 0,
\t\ttex->isUpdatedOnGPU ? 1 : 0,
\t\ttex->enableReadback ? 1 : 0,
\t\ttex->reloadFromDynamicTextures ? 1 : 0,
\t\ttex->lastWriteEventCounter,
\t\ttex->lastUpdateEventCounter,
\t\ttex->lastUpdateFrameCounter,
\t\ttex->lastDataUpdateFrameCounter,
\t\ttex->reloadCount,
\t\ttex->lastAccessFrameCount,
\t\ttex->lastUnflushedRTDrawcallIndex,
\t\ttex->texDataHash2);
}

'''
helpers = helpers.replace(chr(92) + "t", chr(9))

vk = replace_once(
    vk,
    "// includes only states that may change during minimal drawcalls\n",
    helpers + "// includes only states that may change during minimal drawcalls\n",
    "Vulkan target0 depth-compare history helper insertion",
)

old_call = "\tBayo2Target0TextureResourceTrace_LogDraw(pipeline_info, baseVertex, baseInstance, instanceCount, count, indexDataMPTR, indexType);\n"
new_call = old_call + "\tBayo2Target0DepthCompareHistoryTrace_LogDraw(pipeline_info, m_state.boundTexture[LATTE_CEMU_PS_TEX_UNIT_BASE + 11], baseVertex, baseInstance, instanceCount, count, indexDataMPTR, indexType);\n"
vk = replace_count(
    vk,
    old_call,
    new_call,
    2,
    "Vulkan target0 depth-compare history call sites",
)

for token in (
    "[BAYO2_TARGET_DEPTHCOMPARE]",
    "m_state.boundTexture[LATTE_CEMU_PS_TEX_UNIT_BASE + 11]",
    "lastWriteEventCounter",
    "lastUnflushedRTDrawcallIndex",
    "texDataHash2",
):
    if token not in vk:
        raise RuntimeError(f"target0 depth-compare history token missing after transform: {token}")

if vk.count("Bayo2Target0DepthCompareHistoryTrace_LogDraw(pipeline_info") != 2:
    raise RuntimeError("expected exactly two target0 depth-compare history trace call sites")

vk_path.write_text(vk, encoding="utf-8", newline="\n")
print("Bayonetta 2 target0 depth-compare texture history trace installed; behavior unchanged")
