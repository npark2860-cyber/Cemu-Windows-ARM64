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
# Query core: arm short observation windows only when one of the five targeted
# Bayo2 CPU query slots changes 0<->nonzero. Each trigger observes exactly the
# next three command-stream frames. Query values and visibility are untouched.
# Applied after Apply-Bayo2TargetQueryDrawFingerprintTrace.py.
# -----------------------------------------------------------------------------
core_path = Path("src/Cafe/HW/Latte/Core/LatteQuery.cpp")
core = core_path.read_text(encoding="utf-8")

watch_state = '''struct Bayo2TargetDownstreamWatchSnapshot
{
\tuint64 watchId{};
\tsint32 targetIndex{};
\tMPTR queryMPTR{};
\tuint64 triggerGeneration{};
\tuint64 triggerFrame{};
\tuint64 triggerDraw{};
\tuint64 result{};
\tuint64 previousResult{};
\tuint32 transitionCode{}; // 1 = 0->NZ, 2 = NZ->0
};

struct Bayo2TargetDownstreamWatch
{
\tbool active{};
\tBayo2TargetDownstreamWatchSnapshot snapshot{};
};

static Bayo2TargetDownstreamWatch s_bayo2TargetDownstreamWatches[32]{};
static uint64 s_bayo2TargetDownstreamNextWatchId = 0;
static uint64 s_bayo2TargetDownstreamDroppedWatchCount = 0;

static void Bayo2TargetDownstream_ArmLocked(
\tsint32 targetIndex,
\tMPTR queryMPTR,
\tuint64 generation,
\tuint64 triggerFrame,
\tuint64 triggerDraw,
\tuint32 transitionCode,
\tuint64 result,
\tuint64 previousResult)
{
\tfor (auto& watch : s_bayo2TargetDownstreamWatches)
\t{
\t\tif (watch.active && triggerFrame > watch.snapshot.triggerFrame + 3)
\t\t\twatch.active = false;
\t}

\tBayo2TargetDownstreamWatch* selected = nullptr;
\tfor (auto& watch : s_bayo2TargetDownstreamWatches)
\t{
\t\tif (!watch.active)
\t\t{
\t\t\tselected = &watch;
\t\t\tbreak;
\t\t}
\t}

\tif (selected == nullptr)
\t{
\t\tselected = &s_bayo2TargetDownstreamWatches[0];
\t\tfor (auto& watch : s_bayo2TargetDownstreamWatches)
\t\t{
\t\t\tif (watch.snapshot.triggerFrame < selected->snapshot.triggerFrame ||
\t\t\t\t(watch.snapshot.triggerFrame == selected->snapshot.triggerFrame && watch.snapshot.watchId < selected->snapshot.watchId))
\t\t\t\tselected = &watch;
\t\t}
\t\tconst uint64 dropped = ++s_bayo2TargetDownstreamDroppedWatchCount;
\t\tcemuLog_log(LogType::Force,
\t\t\t"[BAYO2_DOWNSTREAM] DROP dropped={} oldWatch={} oldTarget={} oldQuery={:08x} oldTriggerFrame={}",
\t\t\tdropped,
\t\t\tselected->snapshot.watchId,
\t\t\tselected->snapshot.targetIndex,
\t\t\tselected->snapshot.queryMPTR,
\t\t\tselected->snapshot.triggerFrame);
\t}

\tselected->active = true;
\tselected->snapshot.watchId = ++s_bayo2TargetDownstreamNextWatchId;
\tselected->snapshot.targetIndex = targetIndex;
\tselected->snapshot.queryMPTR = queryMPTR;
\tselected->snapshot.triggerGeneration = generation;
\tselected->snapshot.triggerFrame = triggerFrame;
\tselected->snapshot.triggerDraw = triggerDraw;
\tselected->snapshot.result = result;
\tselected->snapshot.previousResult = previousResult;
\tselected->snapshot.transitionCode = transitionCode;

\tcemuLog_log(LogType::Force,
\t\t"[BAYO2_DOWNSTREAM] TRIGGER watch={} target={} query={:08x} gen={} transition={} prevResult={} result={} triggerFrame={} triggerDraw={} observeFrames={}..{}",
\t\tselected->snapshot.watchId,
\t\ttargetIndex,
\t\tqueryMPTR,
\t\tgeneration,
\t\ttransitionCode == 1 ? "0->NZ" : "NZ->0",
\t\tpreviousResult,
\t\tresult,
\t\ttriggerFrame,
\t\ttriggerDraw,
\t\ttriggerFrame + 1,
\t\ttriggerFrame + 3);
}

uint32 Bayo2TargetDownstream_GetActiveWatches(
\tuint64 currentFrame,
\tBayo2TargetDownstreamWatchSnapshot* outWatches,
\tuint32 capacity)
{
\tif (!Bayo2QueryCorr_Enabled() || outWatches == nullptr || capacity == 0)
\t\treturn 0;

\tstd::lock_guard<std::mutex> lock(s_bayo2QueryCorrMutex);
\tuint32 count = 0;
\tfor (auto& watch : s_bayo2TargetDownstreamWatches)
\t{
\t\tif (!watch.active)
\t\t\tcontinue;
\t\tif (currentFrame > watch.snapshot.triggerFrame + 3)
\t\t{
\t\t\twatch.active = false;
\t\t\tcontinue;
\t\t}
\t\tif (currentFrame <= watch.snapshot.triggerFrame)
\t\t\tcontinue;
\n\t\toutWatches[count++] = watch.snapshot;
\t\tif (count >= capacity)
\t\t\tbreak;
\t}
\treturn count;
}

'''

core = replace_once(
    core,
    'void Bayo2QueryCorr_LogFrameBoundary(uint64 frameSeq, uint64 drawSeq)\n',
    watch_state + 'void Bayo2QueryCorr_LogFrameBoundary(uint64 frameSeq, uint64 drawSeq)\n',
    "downstream watch state insertion",
)

old_target_get = '''\t\tconst sint32 targetIndex = Bayo2QueryTarget_GetIndex(queryMPTR);
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
'''
new_target_get = '''\t\tconst sint32 targetIndex = Bayo2QueryTarget_GetIndex(queryMPTR);
\t\tif (newGeneration && targetIndex >= 0)
\t\t{
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[BAYO2_TARGET] GET target={} query={:08x} gen={} prevGen={} transition={} result={} sampleSum={} frame={}..{} draw={}..{} spanDraw={} finishFrame={} finishDraw={} prevResult={}",
\t\t\t\ttargetIndex, queryMPTR, snapshot.generation, prevGeneration, transition,
\t\t\t\tresult, snapshot.sampleSum,
\t\t\t\tsnapshot.beginFrame, snapshot.endFrame,
\t\t\t\tsnapshot.beginDraw, snapshot.endDraw, spanDraw,
\t\t\t\tsnapshot.finishFrame, snapshot.finishDraw, prevResult);

\t\t\tuint32 downstreamTransitionCode = 0;
\t\t\tif (prevGeneration != 0 && prevResult == 0 && result != 0)
\t\t\t\tdownstreamTransitionCode = 1;
\t\t\telse if (prevGeneration != 0 && prevResult != 0 && result == 0)
\t\t\t\tdownstreamTransitionCode = 2;
\t\t\tif (downstreamTransitionCode != 0)
\t\t\t{
\t\t\t\tBayo2TargetDownstream_ArmLocked(
\t\t\t\t\ttargetIndex,
\t\t\t\t\tqueryMPTR,
\t\t\t\t\tsnapshot.generation,
\t\t\t\t\tBayo2QueryCorr_GetFrameSeq(),
\t\t\t\t\tBayo2QueryCorr_GetDrawSeq(),
\t\t\t\t\tdownstreamTransitionCode,
\t\t\t\t\tresult,
\t\t\t\t\tprevResult);
\t\t\t}
\t\t}
'''
core = replace_once(core, old_target_get, new_target_get, "arm downstream watch on target transition")
core_path.write_text(core, encoding="utf-8", newline="\n")


# -----------------------------------------------------------------------------
# Vulkan renderer: for any armed transition, log every draw in exactly the next
# three frame windows. This is a read-only fingerprint of already-selected draw
# state and arguments; no renderer state or draw command is modified.
# -----------------------------------------------------------------------------
vk_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
vk = vk_path.read_text(encoding="utf-8")

vk_downstream_helpers = '''struct Bayo2TargetDownstreamWatchSnapshot
{
\tuint64 watchId{};
\tsint32 targetIndex{};
\tMPTR queryMPTR{};
\tuint64 triggerGeneration{};
\tuint64 triggerFrame{};
\tuint64 triggerDraw{};
\tuint64 result{};
\tuint64 previousResult{};
\tuint32 transitionCode{};
};

uint32 Bayo2TargetDownstream_GetActiveWatches(
\tuint64 currentFrame,
\tBayo2TargetDownstreamWatchSnapshot* outWatches,
\tuint32 capacity);

static void Bayo2TargetDownstreamTrace_LogDrawFingerprint(
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

\tconst uint64 frameSeq = Bayo2QueryCorr_GetFrameSeq();
\tBayo2TargetDownstreamWatchSnapshot watches[32]{};
\tconst uint32 watchCount = Bayo2TargetDownstream_GetActiveWatches(frameSeq, watches, 32);
\tif (watchCount == 0)
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

\tconst uint64 drawSeq = Bayo2QueryCorr_GetDrawSeq();
\tfor (uint32 i = 0; i < watchCount; i++)
\t{
\t\tconst auto& watch = watches[i];
\t\tconst uint64 frameOffset = frameSeq - watch.triggerFrame;
\t\tcemuLog_log(LogType::Force,
\t\t\t"[BAYO2_DOWNSTREAM] DRAW watch={} target={} query={:08x} triggerGen={} transition={} prevResult={} result={} "
\t\t\t"triggerFrame={} triggerDraw={} observedFrame={} frameOffset={} draw={} pipeline={:016x} minimal={:016x} "
\t\t\t"vs={:016x}/{:016x} gs={:016x}/{:016x} ps={:016x}/{:016x} "
\t\t\t"primitive={:08x} count={} instances={} baseVertex={} baseInstance={} indexType={} index={:08x} "
\t\t\t"clip={:08x} raster={:08x} depthCtrl={:08x} colorCtrl={:08x} targetMask={:08x} "
\t\t\t"color0={:08x}/{:08x}/{:08x}/{:08x} depth={:08x}/{:08x}/{:08x}/{:08x}",
\t\t\twatch.watchId,
\t\t\twatch.targetIndex,
\t\t\twatch.queryMPTR,
\t\t\twatch.triggerGeneration,
\t\t\twatch.transitionCode == 1 ? "0->NZ" : "NZ->0",
\t\t\twatch.previousResult,
\t\t\twatch.result,
\t\t\twatch.triggerFrame,
\t\t\twatch.triggerDraw,
\t\t\tframeSeq,
\t\t\tframeOffset,
\t\t\tdrawSeq,
\t\t\tpipelineInfo->stateHash,
\t\t\tpipelineInfo->minimalStateHash,
\t\t\tvsBase,
\t\t\tvsAux,
\t\t\tgsBase,
\t\t\tgsAux,
\t\t\tpsBase,
\t\t\tpsAux,
\t\t\tprimitive,
\t\t\tcount,
\t\t\tinstanceCount,
\t\t\tbaseVertex,
\t\t\tbaseInstance,
\t\t\tstatic_cast<uint32>(indexType),
\t\t\tindexDataMPTR,
\t\t\tclip,
\t\t\traster,
\t\t\tdepthControl,
\t\t\tcolorControl,
\t\t\ttargetMask,
\t\t\tcolor0Base,
\t\t\tcolor0Size,
\t\t\tcolor0Info,
\t\t\tcolor0View,
\t\t\tdepthBase,
\t\t\tdepthSize,
\t\t\tdepthInfo,
\t\t\tdepthView);
\t}
}

'''

vk = replace_once(
    vk,
    '// includes only states that may change during minimal drawcalls\n',
    vk_downstream_helpers + '// includes only states that may change during minimal drawcalls\n',
    "Vulkan downstream helper insertion",
)

old_call = '''\tBayo2TargetTrace_LogDrawFingerprint(pipeline_info, baseVertex, baseInstance, instanceCount, count, indexDataMPTR, indexType);\n'''
new_call = old_call + '''\tBayo2TargetDownstreamTrace_LogDrawFingerprint(pipeline_info, baseVertex, baseInstance, instanceCount, count, indexDataMPTR, indexType);\n'''
vk = replace_count(
    vk,
    old_call,
    new_call,
    2,
    "Vulkan downstream draw fingerprint call sites",
)
vk_path.write_text(vk, encoding="utf-8", newline="\n")

print("Bayonetta 2 target transition -> next-three-frame downstream draw trace installed; behavior unchanged")
