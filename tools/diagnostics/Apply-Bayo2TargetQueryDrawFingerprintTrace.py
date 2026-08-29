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
# Query core: expose only the five stable high-oscillation Bayo2 CPU query slots
# and add target-only GET records. Behavior is unchanged.
# Applied after Apply-Bayo2QueryFrameDrawCorrelationTrace.py.
# -----------------------------------------------------------------------------
core_path = Path("src/Cafe/HW/Latte/Core/LatteQuery.cpp")
core = core_path.read_text(encoding="utf-8")

target_helpers = r'''static sint32 Bayo2QueryTarget_GetIndex(MPTR queryMPTR)
{
\tswitch (queryMPTR)
\t{
\tcase 0x46a92ec8:
\t\treturn 0;
\tcase 0x46a936c8:
\t\treturn 1;
\tcase 0x46a93bc8:
\t\treturn 2;
\tcase 0x46a93a08:
\t\treturn 3;
\tcase 0x46a93708:
\t\treturn 4;
\tdefault:
\t\treturn -1;
\t}
}

uint32 Bayo2QueryTarget_GetActiveTargets(MPTR* queryMPTRs, uint64* generations, sint32* targetIndices, uint32 capacity)
{
\tif (!Bayo2QueryCorr_Enabled() || capacity == 0)
\t\treturn 0;

\tstd::lock_guard<std::mutex> lock(s_bayo2QueryCorrMutex);
\tuint32 count = 0;
\tfor (const auto& entry : s_bayo2QueryCorrBindingMeta)
\t{
\t\tLatteGX2QueryInformation* binding = entry.first;
\t\tif (binding == nullptr || binding->queryEnded)
\t\t\tcontinue;

\t\tconst sint32 targetIndex = Bayo2QueryTarget_GetIndex(binding->queryMPTR);
\t\tif (targetIndex < 0)
\t\t\tcontinue;

\t\tqueryMPTRs[count] = binding->queryMPTR;
\t\tgenerations[count] = entry.second.generation;
\t\ttargetIndices[count] = targetIndex;
\t\tcount++;
\t\tif (count >= capacity)
\t\t\tbreak;
\t}
\treturn count;
}

'''

core = replace_once(
    core,
    '''static bool Bayo2QueryCorr_Enabled()
{
\treturn CafeSystem::GetForegroundTitleId() == 0x000500001011B900ULL;
}

void Bayo2QueryCorr_LogFrameBoundary(uint64 frameSeq, uint64 drawSeq)
''',
    '''static bool Bayo2QueryCorr_Enabled()
{
\treturn CafeSystem::GetForegroundTitleId() == 0x000500001011B900ULL;
}

''' + target_helpers + '''void Bayo2QueryCorr_LogFrameBoundary(uint64 frameSeq, uint64 drawSeq)
''',
    "target helper insertion",
)

core = replace_once(
    core,
    '''\t\tcemuLog_log(LogType::Force,
\t\t\t"[BAYO2_QUERY_CORR] GET n={} query={:08x} gen={} prevGen={} transition={} result={} sampleSum={} resultMatchesFinish={} event={}..{} frame={}..{} draw={}..{} spanDraw={} finishFrame={} finishDraw={} prevResult={}",
\t\t\tn, queryMPTR, snapshot.generation, prevGeneration, transition,
\t\t\tresult, snapshot.sampleSum, result == snapshot.sampleSum ? 1 : 0,
\t\t\tsnapshot.eventStart, snapshot.eventEnd,
\t\t\tsnapshot.beginFrame, snapshot.endFrame,
\t\t\tsnapshot.beginDraw, snapshot.endDraw, spanDraw,
\t\t\tsnapshot.finishFrame, snapshot.finishDraw, prevResult);
\t}
}
''',
    '''\t\tcemuLog_log(LogType::Force,
\t\t\t"[BAYO2_QUERY_CORR] GET n={} query={:08x} gen={} prevGen={} transition={} result={} sampleSum={} resultMatchesFinish={} event={}..{} frame={}..{} draw={}..{} spanDraw={} finishFrame={} finishDraw={} prevResult={}",
\t\t\tn, queryMPTR, snapshot.generation, prevGeneration, transition,
\t\t\tresult, snapshot.sampleSum, result == snapshot.sampleSum ? 1 : 0,
\t\t\tsnapshot.eventStart, snapshot.eventEnd,
\t\t\tsnapshot.beginFrame, snapshot.endFrame,
\t\t\tsnapshot.beginDraw, snapshot.endDraw, spanDraw,
\t\t\tsnapshot.finishFrame, snapshot.finishDraw, prevResult);

\t\tconst sint32 targetIndex = Bayo2QueryTarget_GetIndex(queryMPTR);
\t\tif (newGeneration && targetIndex >= 0)
\t\t{
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[BAYO2_TARGET] GET target={} query={:08x} gen={} prevGen={} transition={} result={} sampleSum={} frame={}..{} draw={}..{} spanDraw={} finishFrame={} finishDraw={} prevResult={}",
\t\t\t\ttargetIndex, queryMPTR, snapshot.generation, prevGeneration, transition,
\t\t\t\tresult, snapshot.sampleSum,
\t\t\t\tsnapshot.beginFrame, snapshot.endFrame,
\t\t\t\tsnapshot.beginDraw, snapshot.endDraw, spanDraw,
\t\t\t\tsnapshot.finishFrame, snapshot.finishDraw, prevResult);
\t\t}
\t}
}
''',
    "target GET logging",
)
core_path.write_text(core, encoding="utf-8", newline="\n")


# -----------------------------------------------------------------------------
# Vulkan renderer: when one of the five target query bindings is actively
# bracketing a draw, log an exact graphics-pipeline/shader/RT/depth fingerprint.
# No GPU state or draw behavior is changed.
# -----------------------------------------------------------------------------
vk_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
vk = vk_path.read_text(encoding="utf-8")

vk_helpers = r'''uint64 Bayo2QueryCorr_GetFrameSeq();
uint64 Bayo2QueryCorr_GetDrawSeq();
uint32 Bayo2QueryTarget_GetActiveTargets(MPTR* queryMPTRs, uint64* generations, sint32* targetIndices, uint32 capacity);

static void Bayo2TargetTrace_LogDrawFingerprint(
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

\tconst auto* vertexShader = pipelineInfo->vertexShader;
\tconst auto* geometryShader = pipelineInfo->geometryShader;
\tconst auto* pixelShader = pipelineInfo->pixelShader;
\tuint32* ctx = LatteGPUState.contextNew.GetRawView();

\tconst uint64 vsBase = vertexShader ? vertexShader->baseHash : 0;
\tconst uint64 vsAux = vertexShader ? vertexShader->auxHash : 0;
\tconst uint64 gsBase = geometryShader ? geometryShader->baseHash : 0;
\tconst uint64 gsAux = geometryShader ? geometryShader->auxHash : 0;
\tconst uint64 psBase = pixelShader ? pixelShader->baseHash : 0;
\tconst uint64 psAux = pixelShader ? pixelShader->auxHash : 0;

\tconst uint32 primitive = ctx[mmVGT_PRIMITIVE_TYPE];
\tconst uint32 clip = ctx[Latte::REGADDR::PA_CL_CLIP_CNTL];
\tconst uint32 raster = LatteGPUState.contextNew.PA_SU_SC_MODE_CNTL.getRawValue();
\tconst uint32 depthControl = ctx[Latte::REGADDR::DB_DEPTH_CONTROL];
\tconst uint32 colorControl = ctx[Latte::REGADDR::CB_COLOR_CONTROL];
\tconst uint32 targetMask = ctx[Latte::REGADDR::CB_TARGET_MASK];

\tconst uint32 color0Base = ctx[mmCB_COLOR0_BASE];
\tconst uint32 color0Size = ctx[mmCB_COLOR0_SIZE];
\tconst uint32 color0Info = ctx[mmCB_COLOR0_INFO];
\tconst uint32 color0View = ctx[mmCB_COLOR0_VIEW];

\tconst uint32 depthBase = ctx[mmDB_DEPTH_BASE];
\tconst uint32 depthSize = ctx[mmDB_DEPTH_SIZE];
\tconst uint32 depthInfo = ctx[mmDB_DEPTH_INFO];
\tconst uint32 depthView = ctx[mmDB_DEPTH_VIEW];

\tconst uint64 frameSeq = Bayo2QueryCorr_GetFrameSeq();
\tconst uint64 drawSeq = Bayo2QueryCorr_GetDrawSeq();

\tfor (uint32 i = 0; i < targetCount; i++)
\t{
\t\tcemuLog_log(LogType::Force,
\t\t\t"[BAYO2_TARGET] DRAW target={} query={:08x} gen={} frame={} draw={} pipeline={:016x} minimal={:016x} "
\t\t\t"vs={:016x}/{:016x} gs={:016x}/{:016x} ps={:016x}/{:016x} "
\t\t\t"primitive={:08x} count={} instances={} baseVertex={} baseInstance={} indexType={} index={:08x} "
\t\t\t"clip={:08x} raster={:08x} depthCtrl={:08x} colorCtrl={:08x} targetMask={:08x} "
\t\t\t"color0={:08x}/{:08x}/{:08x}/{:08x} depth={:08x}/{:08x}/{:08x}/{:08x}",
\t\t\ttargetIndices[i], queryMPTRs[i], generations[i], frameSeq, drawSeq,
\t\t\tpipelineInfo->stateHash, pipelineInfo->minimalStateHash,
\t\t\tvsBase, vsAux, gsBase, gsAux, psBase, psAux,
\t\t\tprimitive, count, instanceCount, baseVertex, baseInstance, static_cast<uint32>(indexType), indexDataMPTR,
\t\t\tclip, raster, depthControl, colorControl, targetMask,
\t\t\tcolor0Base, color0Size, color0Info, color0View,
\t\t\tdepthBase, depthSize, depthInfo, depthView);
\t}
}

'''

vk = replace_once(
    vk,
    '''extern bool hasValidFramebufferAttached;

// includes only states that may change during minimal drawcalls
''',
    '''extern bool hasValidFramebufferAttached;

''' + vk_helpers + '''// includes only states that may change during minimal drawcalls
''',
    "Vulkan target helper insertion",
)

pipeline_anchor = '''\tPipelineInfo* pipeline_info = draw_getOrCreateGraphicsPipeline(count);
\tm_state.activePipelineInfo = pipeline_info;
'''
pipeline_replacement = '''\tPipelineInfo* pipeline_info = draw_getOrCreateGraphicsPipeline(count);
\tm_state.activePipelineInfo = pipeline_info;
\tBayo2TargetTrace_LogDrawFingerprint(pipeline_info, baseVertex, baseInstance, instanceCount, count, indexDataMPTR, indexType);
'''
vk = replace_count(
    vk,
    pipeline_anchor,
    pipeline_replacement,
    2,
    "Vulkan first/continued draw fingerprints",
)
vk_path.write_text(vk, encoding="utf-8", newline="\n")

print("Bayonetta 2 targeted query/draw fingerprint observation trace installed; behavior unchanged")
