from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# -----------------------------------------------------------------------------
# Command processor: monotonic frame/draw cursors only.
# -----------------------------------------------------------------------------
cp_path = Path("src/Cafe/HW/Latte/Core/LatteCommandProcessor.cpp")
cp = cp_path.read_text(encoding="utf-8")

cp = replace_once(
    cp,
    '''void LatteThread_HandleOSScreen();

void LatteThread_Exit();

class DrawPassContext
''',
    '''void LatteThread_HandleOSScreen();

void LatteThread_Exit();

// Observation-only Bayonetta 2 query/frame correlation cursors.
static uint64 s_bayo2QueryCorrFrameSeq = 0;
static uint64 s_bayo2QueryCorrDrawSeq = 0;

uint64 Bayo2QueryCorr_GetFrameSeq()
{
\treturn s_bayo2QueryCorrFrameSeq;
}

uint64 Bayo2QueryCorr_GetDrawSeq()
{
\treturn s_bayo2QueryCorrDrawSeq;
}

void Bayo2QueryCorr_LogFrameBoundary(uint64 frameSeq, uint64 drawSeq);

class DrawPassContext
''',
    "command processor state",
)

cp = replace_once(
    cp,
    '''\t\t\tauto indexType = LatteGPUState.contextNew.VGT_DMA_INDEX_TYPE.get_INDEX_TYPE();
\t\t\tg_renderer->draw_execute(baseVertex, baseInstance, numInstances, count, physIndices, indexType, m_drawcallContext);
''',
    '''\t\t\tauto indexType = LatteGPUState.contextNew.VGT_DMA_INDEX_TYPE.get_INDEX_TYPE();
\t\t\t++s_bayo2QueryCorrDrawSeq;
\t\t\tg_renderer->draw_execute(baseVertex, baseInstance, numInstances, count, physIndices, indexType, m_drawcallContext);
''',
    "indexed draw cursor",
)

cp = replace_once(
    cp,
    '''\t\telse
\t\t{
\t\t\tg_renderer->draw_execute(baseVertex, baseInstance, numInstances, count, MPTR_NULL, Latte::LATTE_VGT_DMA_INDEX_TYPE::E_INDEX_TYPE::AUTO, m_drawcallContext);
\t\t}
''',
    '''\t\telse
\t\t{
\t\t\t++s_bayo2QueryCorrDrawSeq;
\t\t\tg_renderer->draw_execute(baseVertex, baseInstance, numInstances, count, MPTR_NULL, Latte::LATTE_VGT_DMA_INDEX_TYPE::E_INDEX_TYPE::AUTO, m_drawcallContext);
\t\t}
''',
    "auto draw cursor",
)

cp = replace_once(
    cp,
    '''LatteCMDPtr LatteCP_itHLESwapScanBuffer(LatteCMDPtr cmd, uint32 nWords)
{
\tcatchOpenGLError();
\tcemu_assert_debug(nWords == 1);
\tMPTR reserved1 = LatteReadCMD(); // reserved
\tLatteRenderTarget_itHLESwapScanBuffer();
''',
    '''LatteCMDPtr LatteCP_itHLESwapScanBuffer(LatteCMDPtr cmd, uint32 nWords)
{
\tcatchOpenGLError();
\tcemu_assert_debug(nWords == 1);
\tMPTR reserved1 = LatteReadCMD(); // reserved
\t++s_bayo2QueryCorrFrameSeq;
\tBayo2QueryCorr_LogFrameBoundary(s_bayo2QueryCorrFrameSeq, s_bayo2QueryCorrDrawSeq);
\tLatteRenderTarget_itHLESwapScanBuffer();
''',
    "swap frame cursor",
)
cp_path.write_text(cp, encoding="utf-8", newline="\n")


# -----------------------------------------------------------------------------
# Latte query core: pointer generations and begin/end/finish snapshots.
# Applied after Apply-Bayo2XCXQueryConsumptionTrace.py.
# -----------------------------------------------------------------------------
core_path = Path("src/Cafe/HW/Latte/Core/LatteQuery.cpp")
core = core_path.read_text(encoding="utf-8")

core = replace_once(
    core,
    '#include "Cafe/CafeSystem.h"\n',
    '#include "Cafe/CafeSystem.h"\n\n#include <mutex>\n#include <unordered_map>\n',
    "correlation includes",
)

corr_state = '''uint64 Bayo2QueryCorr_GetFrameSeq();
uint64 Bayo2QueryCorr_GetDrawSeq();

struct Bayo2QueryCorrBindingMeta
{
\tuint64 generation{};
\tuint64 beginFrame{};
\tuint64 beginDraw{};
\tuint64 endFrame{};
\tuint64 endDraw{};
};

struct Bayo2QueryCorrSnapshot
{
\tuint64 generation{};
\tuint64 sampleSum{};
\tuint64 eventStart{};
\tuint64 eventEnd{};
\tuint64 beginFrame{};
\tuint64 beginDraw{};
\tuint64 endFrame{};
\tuint64 endDraw{};
\tuint64 finishFrame{};
\tuint64 finishDraw{};
};

struct Bayo2QueryCorrLastGet
{
\tbool valid{};
\tuint64 generation{};
\tuint64 result{};
};

static std::mutex s_bayo2QueryCorrMutex;
static std::unordered_map<MPTR, uint64> s_bayo2QueryCorrGenerationByPointer;
static std::unordered_map<LatteGX2QueryInformation*, Bayo2QueryCorrBindingMeta> s_bayo2QueryCorrBindingMeta;
static std::unordered_map<MPTR, Bayo2QueryCorrSnapshot> s_bayo2QueryCorrFinishedByPointer;
static std::unordered_map<MPTR, Bayo2QueryCorrLastGet> s_bayo2QueryCorrLastGetByPointer;
static uint64 s_bayo2QueryCorrGetCount = 0;
static uint64 s_bayo2QueryCorrNewGenerationGetCount = 0;
static uint64 s_bayo2QueryCorrZeroGetCount = 0;
static uint64 s_bayo2QueryCorrNonZeroGetCount = 0;
static uint64 s_bayo2QueryCorrZeroToNonZeroCount = 0;
static uint64 s_bayo2QueryCorrNonZeroToZeroCount = 0;
static uint64 s_bayo2QueryCorrRepeatGetCount = 0;
static uint64 s_bayo2QueryCorrMissingSnapshotCount = 0;
static uint64 s_bayo2QueryCorrOverwrittenUnconsumedCount = 0;

static bool Bayo2QueryCorr_Enabled()
{
\treturn CafeSystem::GetForegroundTitleId() == 0x000500001011B900ULL;
}

void Bayo2QueryCorr_LogFrameBoundary(uint64 frameSeq, uint64 drawSeq)
{
\tif (!Bayo2QueryCorr_Enabled())
\t\treturn;

\tstd::lock_guard<std::mutex> lock(s_bayo2QueryCorrMutex);
\tcemuLog_log(LogType::Force,
\t\t"[BAYO2_QUERY_CORR] FRAME frame={} draw={} gets={} newGenGets={} zero={} nonzero={} z2nz={} nz2z={} repeat={} missingSnapshot={} overwrittenUnconsumed={} finishedSlots={}",
\t\tframeSeq, drawSeq,
\t\ts_bayo2QueryCorrGetCount, s_bayo2QueryCorrNewGenerationGetCount,
\t\ts_bayo2QueryCorrZeroGetCount, s_bayo2QueryCorrNonZeroGetCount,
\t\ts_bayo2QueryCorrZeroToNonZeroCount, s_bayo2QueryCorrNonZeroToZeroCount,
\t\ts_bayo2QueryCorrRepeatGetCount, s_bayo2QueryCorrMissingSnapshotCount,
\t\ts_bayo2QueryCorrOverwrittenUnconsumedCount,
\t\ts_bayo2QueryCorrFinishedByPointer.size());
}

void Bayo2QueryCorr_LogGet(MPTR queryMPTR, uint64 result)
{
\tif (!Bayo2QueryCorr_Enabled())
\t\treturn;

\tstd::lock_guard<std::mutex> lock(s_bayo2QueryCorrMutex);
\tconst uint64 n = ++s_bayo2QueryCorrGetCount;
\tauto snapshotIt = s_bayo2QueryCorrFinishedByPointer.find(queryMPTR);
\tif (snapshotIt == s_bayo2QueryCorrFinishedByPointer.end())
\t{
\t\tconst uint64 missing = ++s_bayo2QueryCorrMissingSnapshotCount;
\t\tif (missing <= 64 || (missing % 1000ULL) == 0)
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[BAYO2_QUERY_CORR] GET_NO_SNAPSHOT n={} missing={} query={:08x} result={}",
\t\t\t\tn, missing, queryMPTR, result);
\t\treturn;
\t}

\tconst Bayo2QueryCorrSnapshot snapshot = snapshotIt->second;
\tauto& last = s_bayo2QueryCorrLastGetByPointer[queryMPTR];
\tconst char* transition = "FIRST";
\tuint64 prevGeneration = 0;
\tuint64 prevResult = 0;
\tbool newGeneration = true;

\tif (last.valid)
\t{
\t\tprevGeneration = last.generation;
\t\tprevResult = last.result;
\t\tif (last.generation == snapshot.generation)
\t\t{
\t\t\ttransition = "REPEAT";
\t\t\tnewGeneration = false;
\t\t\t++s_bayo2QueryCorrRepeatGetCount;
\t\t}
\t\telse if (last.result == 0 && result == 0)
\t\t\ttransition = "0->0";
\t\telse if (last.result == 0 && result != 0)
\t\t{
\t\t\ttransition = "0->NZ";
\t\t\t++s_bayo2QueryCorrZeroToNonZeroCount;
\t\t}
\t\telse if (last.result != 0 && result == 0)
\t\t{
\t\t\ttransition = "NZ->0";
\t\t\t++s_bayo2QueryCorrNonZeroToZeroCount;
\t\t}
\t\telse
\t\t\ttransition = "NZ->NZ";
\t}

\tif (newGeneration)
\t{
\t\t++s_bayo2QueryCorrNewGenerationGetCount;
\t\tif (result == 0)
\t\t\t++s_bayo2QueryCorrZeroGetCount;
\t\telse
\t\t\t++s_bayo2QueryCorrNonZeroGetCount;
\t\tlast.valid = true;
\t\tlast.generation = snapshot.generation;
\t\tlast.result = result;
\t}

\tconst bool sampleRepeat = !newGeneration &&
\t\t(s_bayo2QueryCorrRepeatGetCount <= 64 || (s_bayo2QueryCorrRepeatGetCount % 1000ULL) == 0);
\tif (newGeneration || sampleRepeat)
\t{
\t\tconst uint64 spanDraw = snapshot.endDraw >= snapshot.beginDraw ?
\t\t\tsnapshot.endDraw - snapshot.beginDraw : 0;
\t\tcemuLog_log(LogType::Force,
\t\t\t"[BAYO2_QUERY_CORR] GET n={} query={:08x} gen={} prevGen={} transition={} result={} sampleSum={} resultMatchesFinish={} event={}..{} frame={}..{} draw={}..{} spanDraw={} finishFrame={} finishDraw={} prevResult={}",
\t\t\tn, queryMPTR, snapshot.generation, prevGeneration, transition,
\t\t\tresult, snapshot.sampleSum, result == snapshot.sampleSum ? 1 : 0,
\t\t\tsnapshot.eventStart, snapshot.eventEnd,
\t\t\tsnapshot.beginFrame, snapshot.endFrame,
\t\t\tsnapshot.beginDraw, snapshot.endDraw, spanDraw,
\t\t\tsnapshot.finishFrame, snapshot.finishDraw, prevResult);
\t}
}

'''
core = replace_once(
    core,
    'uint64 LatteQuery_getNextEventId()\n',
    corr_state + 'uint64 LatteQuery_getNextEventId()\n',
    "correlation state before event allocator",
)

core = replace_once(
    core,
    '''void LatteQuery_finishGX2Query(LatteGX2QueryInformation* gx2Query)
{
\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
''',
    '''void LatteQuery_finishGX2Query(LatteGX2QueryInformation* gx2Query)
{
\tif (Bayo2QueryCorr_Enabled())
\t{
\t\tstd::lock_guard<std::mutex> lock(s_bayo2QueryCorrMutex);
\t\tauto metaIt = s_bayo2QueryCorrBindingMeta.find(gx2Query);
\t\tif (metaIt != s_bayo2QueryCorrBindingMeta.end())
\t\t{
\t\t\tconst auto meta = metaIt->second;
\t\t\tBayo2QueryCorrSnapshot snapshot{};
\t\t\tsnapshot.generation = meta.generation;
\t\t\tsnapshot.sampleSum = gx2Query->sampleSum;
\t\t\tsnapshot.eventStart = gx2Query->queryEventStart;
\t\t\tsnapshot.eventEnd = gx2Query->queryEventEnd;
\t\t\tsnapshot.beginFrame = meta.beginFrame;
\t\t\tsnapshot.beginDraw = meta.beginDraw;
\t\t\tsnapshot.endFrame = meta.endFrame;
\t\t\tsnapshot.endDraw = meta.endDraw;
\t\t\tsnapshot.finishFrame = Bayo2QueryCorr_GetFrameSeq();
\t\t\tsnapshot.finishDraw = Bayo2QueryCorr_GetDrawSeq();

\t\t\tauto oldIt = s_bayo2QueryCorrFinishedByPointer.find(gx2Query->queryMPTR);
\t\t\tif (oldIt != s_bayo2QueryCorrFinishedByPointer.end())
\t\t\t{
\t\t\t\tauto lastIt = s_bayo2QueryCorrLastGetByPointer.find(gx2Query->queryMPTR);
\t\t\t\tif (lastIt == s_bayo2QueryCorrLastGetByPointer.end() ||
\t\t\t\t\t!lastIt->second.valid || lastIt->second.generation != oldIt->second.generation)
\t\t\t\t\t++s_bayo2QueryCorrOverwrittenUnconsumedCount;
\t\t\t}
\t\t\ts_bayo2QueryCorrFinishedByPointer[gx2Query->queryMPTR] = snapshot;
\t\t\ts_bayo2QueryCorrBindingMeta.erase(metaIt);
\t\t}
\t}

\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
''',
    "finish snapshot",
)

core = replace_once(
    core,
    '''\tqueryBinding->queryEventStart = currentEventId;
\tqueryBinding->queryMPTR = queryMPTR;
\tlist_activeGX2Queries2.emplace_back(queryBinding);
''',
    '''\tqueryBinding->queryEventStart = currentEventId;
\tqueryBinding->queryMPTR = queryMPTR;
\tif (Bayo2QueryCorr_Enabled())
\t{
\t\tstd::lock_guard<std::mutex> lock(s_bayo2QueryCorrMutex);
\t\tauto& meta = s_bayo2QueryCorrBindingMeta[queryBinding];
\t\tmeta.generation = ++s_bayo2QueryCorrGenerationByPointer[queryMPTR];
\t\tmeta.beginFrame = Bayo2QueryCorr_GetFrameSeq();
\t\tmeta.beginDraw = Bayo2QueryCorr_GetDrawSeq();
\t}
\tlist_activeGX2Queries2.emplace_back(queryBinding);
''',
    "begin generation snapshot",
)

core = replace_once(
    core,
    '''\t\tif (it->queryMPTR == queryMPTR)
\t\t{
\t\t\tit->queryEventEnd = currentEventId;
\t\t\tit->queryEnded = true;
\t\t\tbreak;
\t\t}
''',
    '''\t\tif (it->queryMPTR == queryMPTR)
\t\t{
\t\t\tit->queryEventEnd = currentEventId;
\t\t\tif (Bayo2QueryCorr_Enabled())
\t\t\t{
\t\t\t\tstd::lock_guard<std::mutex> lock(s_bayo2QueryCorrMutex);
\t\t\t\tauto metaIt = s_bayo2QueryCorrBindingMeta.find(it);
\t\t\t\tif (metaIt != s_bayo2QueryCorrBindingMeta.end())
\t\t\t\t{
\t\t\t\t\tmetaIt->second.endFrame = Bayo2QueryCorr_GetFrameSeq();
\t\t\t\t\tmetaIt->second.endDraw = Bayo2QueryCorr_GetDrawSeq();
\t\t\t\t}
\t\t\t}
\t\t\tit->queryEnded = true;
\t\t\tbreak;
\t\t}
''',
    "end range snapshot",
)
core_path.write_text(core, encoding="utf-8", newline="\n")


# -----------------------------------------------------------------------------
# GX2 CPU-side GET: correlate only after the original ready checks pass.
# -----------------------------------------------------------------------------
gx2_path = Path("src/Cafe/OS/libs/gx2/GX2_Query.cpp")
gx2 = gx2_path.read_text(encoding="utf-8")

gx2 = replace_once(
    gx2,
    '''#define _QUERY_REG_COUNT\t\t\t\t\t\t8 // each reg/result is 64bits, little endian

namespace GX2
''',
    '''#define _QUERY_REG_COUNT\t\t\t\t\t\t8 // each reg/result is 64bits, little endian

void Bayo2QueryCorr_LogGet(MPTR queryMPTR, uint64 result);

namespace GX2
''',
    "GX2 correlation declaration",
)

gx2 = replace_once(
    gx2,
    '''\t\t*resultOut = endValue - startValue;
\t\treturn GX2_TRUE;
''',
    '''\t\tconst uint64 bayo2QueryCorrResult = endValue - startValue;
\t\tBayo2QueryCorr_LogGet(MEMPTR<GX2Query>(query).GetMPTR(), bayo2QueryCorrResult);
\t\t*resultOut = endValue - startValue;
\t\treturn GX2_TRUE;
''',
    "GX2 ready result correlation",
)
gx2_path.write_text(gx2, encoding="utf-8", newline="\n")

print("Bayonetta 2 query frame/draw correlation observation trace installed; behavior unchanged")
