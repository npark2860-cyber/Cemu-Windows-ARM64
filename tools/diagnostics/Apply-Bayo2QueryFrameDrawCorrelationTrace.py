from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# -----------------------------------------------------------------------------
# Latte command processor: monotonic frame/draw cursors for GPU-side correlation.
# -----------------------------------------------------------------------------
cp_path = Path("src/Cafe/HW/Latte/Core/LatteCommandProcessor.cpp")
cp = cp_path.read_text(encoding="utf-8")

cp_state_anchor = '''void LatteThread_HandleOSScreen();

void LatteThread_Exit();

class DrawPassContext
'''
cp_state_block = '''void LatteThread_HandleOSScreen();

void LatteThread_Exit();

// Observation-only Bayonetta 2 query/frame correlation cursors.
// These counters never gate draws or alter renderer/query state.
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
'''
cp = replace_once(cp, cp_state_anchor, cp_state_block, "command processor trace state")

indexed_draw_anchor = '''\t\t\tauto indexType = LatteGPUState.contextNew.VGT_DMA_INDEX_TYPE.get_INDEX_TYPE();
\t\t\tg_renderer->draw_execute(baseVertex, baseInstance, numInstances, count, physIndices, indexType, m_drawcallContext);
'''
indexed_draw_block = '''\t\t\tauto indexType = LatteGPUState.contextNew.VGT_DMA_INDEX_TYPE.get_INDEX_TYPE();
\t\t\t++s_bayo2QueryCorrDrawSeq;
\t\t\tg_renderer->draw_execute(baseVertex, baseInstance, numInstances, count, physIndices, indexType, m_drawcallContext);
'''
cp = replace_once(cp, indexed_draw_anchor, indexed_draw_block, "indexed draw cursor")

auto_draw_anchor = '''\t\telse
\t\t{
\t\t\tg_renderer->draw_execute(baseVertex, baseInstance, numInstances, count, MPTR_NULL, Latte::LATTE_VGT_DMA_INDEX_TYPE::E_INDEX_TYPE::AUTO, m_drawcallContext);
\t\t}
'''
auto_draw_block = '''\t\telse
\t\t{
\t\t\t++s_bayo2QueryCorrDrawSeq;
\t\t\tg_renderer->draw_execute(baseVertex, baseInstance, numInstances, count, MPTR_NULL, Latte::LATTE_VGT_DMA_INDEX_TYPE::E_INDEX_TYPE::AUTO, m_drawcallContext);
\t\t}
'''
cp = replace_once(cp, auto_draw_anchor, auto_draw_block, "auto draw cursor")

swap_anchor = '''LatteCMDPtr LatteCP_itHLESwapScanBuffer(LatteCMDPtr cmd, uint32 nWords)
{
\tcatchOpenGLError();
\tcemu_assert_debug(nWords == 1);
\tMPTR reserved1 = LatteReadCMD(); // reserved
\tLatteRenderTarget_itHLESwapScanBuffer();
'''
swap_block = '''LatteCMDPtr LatteCP_itHLESwapScanBuffer(LatteCMDPtr cmd, uint32 nWords)
{
\tcatchOpenGLError();
\tcemu_assert_debug(nWords == 1);
\tMPTR reserved1 = LatteReadCMD(); // reserved
\t++s_bayo2QueryCorrFrameSeq;
\tBayo2QueryCorr_LogFrameBoundary(s_bayo2QueryCorrFrameSeq, s_bayo2QueryCorrDrawSeq);
\tLatteRenderTarget_itHLESwapScanBuffer();
'''
cp = replace_once(cp, swap_anchor, swap_block, "swap frame cursor")
cp_path.write_text(cp, encoding="utf-8", newline="\n")


# -----------------------------------------------------------------------------
# Latte query core: generation assignment + begin/end/finish snapshots.
# This script is applied after Apply-Bayo2XCXQueryConsumptionTrace.py.
# -----------------------------------------------------------------------------
core_path = Path("src/Cafe/HW/Latte/Core/LatteQuery.cpp")
core = core_path.read_text(encoding="utf-8")

include_anchor = '#include "Cafe/CafeSystem.h"\n'
include_block = '''#include "Cafe/CafeSystem.h"

#include <mutex>
#include <unordered_map>
'''
core = replace_once(core, include_anchor, include_block, "correlation includes")

struct_anchor = '''\tuint64 queryEventEnd;
\tuint64 sampleSum;
\tbool queryEnded;
'''
struct_block = '''\tuint64 queryEventEnd;
\tuint64 sampleSum;

\t// Observation-only metadata. These fields do not participate in query logic.
\tuint64 traceGeneration;
\tuint64 traceBeginFrame;
\tuint64 traceBeginDraw;
\tuint64 traceEndFrame;
\tuint64 traceEndDraw;

\tbool queryEnded;
'''
core = replace_once(core, struct_anchor, struct_block, "query binding trace metadata")

state_anchor = '''LatteQueryObject* _currentlyActiveRendererQuery = {0};

uint64 LatteQuery_getNextEventId()
'''
state_block = '''LatteQueryObject* _currentlyActiveRendererQuery = {0};

uint64 Bayo2QueryCorr_GetFrameSeq();
uint64 Bayo2QueryCorr_GetDrawSeq();

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
\t\t"[BAYO2_QUERY_CORR] FRAME frame={} draw={} gets={} newGenGets={} zero={} nonzero={} z2nz={} nz2z={} repeat={} missingSnapshot={} finishedSlots={}",
\t\tframeSeq, drawSeq,
\t\ts_bayo2QueryCorrGetCount, s_bayo2QueryCorrNewGenerationGetCount,
\t\ts_bayo2QueryCorrZeroGetCount, s_bayo2QueryCorrNonZeroGetCount,
\t\ts_bayo2QueryCorrZeroToNonZeroCount, s_bayo2QueryCorrNonZeroToZeroCount,
\t\ts_bayo2QueryCorrRepeatGetCount, s_bayo2QueryCorrMissingSnapshotCount,
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
\t\t{
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[BAYO2_QUERY_CORR] GET_NO_SNAPSHOT n={} missing={} query={:08x} result={}",
\t\t\t\tn, missing, queryMPTR, result);
\t\t}
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
\t\t{
\t\t\ttransition = "0->0";
\t\t}
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
\t\t{
\t\t\ttransition = "NZ->NZ";
\t\t}
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

\tconst bool sampleRepeat =
\t\t!newGeneration &&
\t\t(s_bayo2QueryCorrRepeatGetCount <= 64 || (s_bayo2QueryCorrRepeatGetCount % 1000ULL) == 0);

\tif (newGeneration || sampleRepeat)
\t{
\t\tconst uint64 spanDraw =
\t\t\tsnapshot.endDraw >= snapshot.beginDraw ? snapshot.endDraw - snapshot.beginDraw : 0;

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

uint64 LatteQuery_getNextEventId()
'''
core = replace_once(core, state_anchor, state_block, "correlation state and helpers")

finish_anchor = '''void LatteQuery_finishGX2Query(LatteGX2QueryInformation* gx2Query)
{
\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
'''
finish_block = '''void LatteQuery_finishGX2Query(LatteGX2QueryInformation* gx2Query)
{
\tif (Bayo2QueryCorr_Enabled() && gx2Query->traceGeneration != 0)
\t{
\t\tBayo2QueryCorrSnapshot snapshot{};
\t\tsnapshot.generation = gx2Query->traceGeneration;
\t\tsnapshot.sampleSum = gx2Query->sampleSum;
\t\tsnapshot.eventStart = gx2Query->queryEventStart;
\t\tsnapshot.eventEnd = gx2Query->queryEventEnd;
\t\tsnapshot.beginFrame = gx2Query->traceBeginFrame;
\t\tsnapshot.beginDraw = gx2Query->traceBeginDraw;
\t\tsnapshot.endFrame = gx2Query->traceEndFrame;
\t\tsnapshot.endDraw = gx2Query->traceEndDraw;
\t\tsnapshot.finishFrame = Bayo2QueryCorr_GetFrameSeq();
\t\tsnapshot.finishDraw = Bayo2QueryCorr_GetDrawSeq();

\t\tstd::lock_guard<std::mutex> lock(s_bayo2QueryCorrMutex);
\t\ts_bayo2QueryCorrFinishedByPointer[gx2Query->queryMPTR] = snapshot;
\t}

\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
'''
core = replace_once(core, finish_anchor, finish_block, "finish snapshot")

begin_anchor = '''\tqueryBinding->queryEventStart = currentEventId;
\tqueryBinding->queryMPTR = queryMPTR;
\tlist_activeGX2Queries2.emplace_back(queryBinding);
'''
begin_block = '''\tqueryBinding->queryEventStart = currentEventId;
\tqueryBinding->queryMPTR = queryMPTR;
\tif (Bayo2QueryCorr_Enabled())
\t{
\t\tstd::lock_guard<std::mutex> lock(s_bayo2QueryCorrMutex);
\t\tqueryBinding->traceGeneration = ++s_bayo2QueryCorrGenerationByPointer[queryMPTR];
\t\tqueryBinding->traceBeginFrame = Bayo2QueryCorr_GetFrameSeq();
\t\tqueryBinding->traceBeginDraw = Bayo2QueryCorr_GetDrawSeq();
\t}
\tlist_activeGX2Queries2.emplace_back(queryBinding);
'''
core = replace_once(core, begin_anchor, begin_block, "begin generation snapshot")

end_anchor = '''\t\tif (it->queryMPTR == queryMPTR)
\t\t{
\t\t\tit->queryEventEnd = currentEventId;
\t\t\tit->queryEnded = true;
\t\t\tbreak;
\t\t}
'''
end_block = '''\t\tif (it->queryMPTR == queryMPTR)
\t\t{
\t\t\tit->queryEventEnd = currentEventId;
\t\t\tif (Bayo2QueryCorr_Enabled() && it->traceGeneration != 0)
\t\t\t{
\t\t\t\tit->traceEndFrame = Bayo2QueryCorr_GetFrameSeq();
\t\t\t\tit->traceEndDraw = Bayo2QueryCorr_GetDrawSeq();
\t\t\t}
\t\t\tit->queryEnded = true;
\t\t\tbreak;
\t\t}
'''
core = replace_once(core, end_anchor, end_block, "end range snapshot")

core_path.write_text(core, encoding="utf-8", newline="\n")


# -----------------------------------------------------------------------------
# GX2 CPU-side GET: attach the ready result to the latest finished generation.
# -----------------------------------------------------------------------------
gx2_path = Path("src/Cafe/OS/libs/gx2/GX2_Query.cpp")
gx2 = gx2_path.read_text(encoding="utf-8")

gx2_decl_anchor = '''#define _QUERY_REG_COUNT\t\t\t\t\t\t8 // each reg/result is 64bits, little endian

namespace GX2
'''
gx2_decl_block = '''#define _QUERY_REG_COUNT\t\t\t\t\t\t8 // each reg/result is 64bits, little endian

void Bayo2QueryCorr_LogGet(MPTR queryMPTR, uint64 result);

namespace GX2
'''
gx2 = replace_once(gx2, gx2_decl_anchor, gx2_decl_block, "GX2 correlation declaration")

get_anchor = '''\t\t*resultOut = endValue - startValue;
\t\treturn GX2_TRUE;
'''
get_block = '''\t\tconst uint64 bayo2QueryCorrResult = endValue - startValue;
\t\tBayo2QueryCorr_LogGet(MEMPTR<GX2Query>(query).GetMPTR(), bayo2QueryCorrResult);
\t\t*resultOut = endValue - startValue;
\t\treturn GX2_TRUE;
'''
gx2 = replace_once(gx2, get_anchor, get_block, "GX2 ready result correlation")

gx2_path.write_text(gx2, encoding="utf-8", newline="\n")
