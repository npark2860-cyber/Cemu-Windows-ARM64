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
# Bayonetta 2 target0 producer depth identity/history trace.
#
# Observation-only. Cemu's GX2SetDepthBuffer writes DB_DEPTH_BASE=0 and keeps
# the actual guest depth address in DB_HTILE_DATA_BASE (address >> 8). Previous
# target traces therefore did not observe the actual depth surface identity.
# This trace records DB_HTILE_DATA_BASE plus the currently bound Latte depth
# texture bookkeeping once per target0 generation. No readback or mutation.
# -----------------------------------------------------------------------------
vk_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
vk = vk_path.read_text(encoding="utf-8")

helpers = '''static uint64 s_bayo2Target0DepthIdentityLastGeneration = 0;

static void Bayo2Target0DepthIdentityTrace_LogDraw(
\tPipelineInfo* pipelineInfo,
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
\tif (!target0Active || s_bayo2Target0DepthIdentityLastGeneration == targetGeneration)
\t\treturn;
\ts_bayo2Target0DepthIdentityLastGeneration = targetGeneration;

\tuint32* ctx = LatteGPUState.contextNew.GetRawView();
\tconst uint32 htileReg = ctx[mmDB_HTILE_DATA_BASE];
\tconst MPTR htilePhysRaw = static_cast<MPTR>(htileReg << 8);
\tconst uint32 depthSize = ctx[mmDB_DEPTH_SIZE];
\tconst uint32 depthInfo = ctx[mmDB_DEPTH_INFO];
\tconst uint32 depthViewReg = ctx[mmDB_DEPTH_VIEW];
\tconst uint32 depthCtrl = ctx[Latte::REGADDR::DB_DEPTH_CONTROL];
\tconst uint64 frameSeq = Bayo2QueryCorr_GetFrameSeq();
\tconst uint64 drawSeq = Bayo2QueryCorr_GetDrawSeq();

\tLatteTextureView* depthView = LatteMRT::GetDepthAttachment();
\tLatteTexture* depthTexture = depthView ? depthView->baseTexture : nullptr;
\tif (depthTexture == nullptr)
\t{
\t\tcemuLog_log(LogType::Force,
\t\t\t"[BAYO2_TARGET_DEPTH] query=46a92ec8 gen={} frame={} draw={} htile={:08x} physRaw={:08x} depthSize={:08x} depthInfo={:08x} depthViewReg={:08x} depthCtrl={:08x} bound=0",
\t\t\ttargetGeneration, frameSeq, drawSeq, htileReg, htilePhysRaw, depthSize, depthInfo, depthViewReg, depthCtrl);
\t\treturn;
\t}

\tcemuLog_log(LogType::Force,
\t\t"[BAYO2_TARGET_DEPTH] query=46a92ec8 gen={} frame={} draw={} htile={:08x} physRaw={:08x} depthSize={:08x} depthInfo={:08x} depthViewReg={:08x} depthCtrl={:08x} "
\t\t"bound=1 phys={:08x} mipPhys={:08x} format={} tileMode={} swizzle={:08x} size={}x{} pitch={} viewMip={}/{} viewSlice={}/{} "
\t\t"gpuUpdated={} readback={} writeEvent={} updateEvent={} updateFrame={} dataUpdateFrame={} reloadCount={} accessFrame={} unflushedDraw={}",
\t\ttargetGeneration,
\t\tframeSeq,
\t\tdrawSeq,
\t\thtileReg,
\t\thtilePhysRaw,
\t\tdepthSize,
\t\tdepthInfo,
\t\tdepthViewReg,
\t\tdepthCtrl,
\t\tdepthTexture->physAddress,
\t\tdepthTexture->physMipAddress,
\t\tstatic_cast<uint32>(depthTexture->format),
\t\tstatic_cast<uint32>(depthTexture->tileMode),
\t\tdepthTexture->swizzle,
\t\tdepthTexture->width,
\t\tdepthTexture->height,
\t\tdepthTexture->pitch,
\t\tdepthView->firstMip,
\t\tdepthView->numMip,
\t\tdepthView->firstSlice,
\t\tdepthView->numSlice,
\t\tdepthTexture->isUpdatedOnGPU ? 1 : 0,
\t\tdepthTexture->enableReadback ? 1 : 0,
\t\tdepthTexture->lastWriteEventCounter,
\t\tdepthTexture->lastUpdateEventCounter,
\t\tdepthTexture->lastUpdateFrameCounter,
\t\tdepthTexture->lastDataUpdateFrameCounter,
\t\tdepthTexture->reloadCount,
\t\tdepthTexture->lastAccessFrameCount,
\t\tdepthTexture->lastUnflushedRTDrawcallIndex);
}

'''
helpers = helpers.replace(chr(92) + "t", chr(9))

vk = replace_once(
    vk,
    "// includes only states that may change during minimal drawcalls\n",
    helpers + "// includes only states that may change during minimal drawcalls\n",
    "Vulkan target0 depth identity helper insertion",
)

old_call = "\tBayo2Target0UniformDeltaTrace_LogDraw(pipeline_info, baseVertex, baseInstance, instanceCount, count, indexDataMPTR, indexType);\n"
new_call = old_call + "\tBayo2Target0DepthIdentityTrace_LogDraw(pipeline_info, baseVertex, baseInstance, instanceCount, count, indexDataMPTR, indexType);\n"
vk = replace_count(
    vk,
    old_call,
    new_call,
    2,
    "Vulkan target0 depth identity call sites",
)

for token in (
    "[BAYO2_TARGET_DEPTH]",
    "mmDB_HTILE_DATA_BASE",
    "LatteMRT::GetDepthAttachment()",
    "lastWriteEventCounter",
    "lastUpdateEventCounter",
):
    if token not in vk:
        raise RuntimeError(f"target0 depth identity token missing after transform: {token}")

if vk.count("Bayo2Target0DepthIdentityTrace_LogDraw(pipeline_info") != 2:
    raise RuntimeError("expected exactly two target0 depth identity trace call sites")

vk_path.write_text(vk, encoding="utf-8", newline="\n")
print("Bayonetta 2 target0 depth identity/history trace installed; behavior unchanged")

# Apply target0 exact index-buffer content observation trace.
index_content_path = Path("tools/diagnostics/Apply-Bayo2Target0IndexContentTrace.py")
exec(compile(index_content_path.read_text(encoding="utf-8"), str(index_content_path), "exec"))
