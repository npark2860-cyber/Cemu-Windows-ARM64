from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


def sample_count(n: int) -> bool:
    return n <= 128 or (n % 1000) == 0


# -----------------------------------------------------------------------------
# GX2 API side: observe query type and guest-visible consumption.
# -----------------------------------------------------------------------------
gx2_path = Path("src/Cafe/OS/libs/gx2/GX2_Query.cpp")
gx2 = gx2_path.read_text(encoding="utf-8")

state_anchor = "\tstatic_assert(sizeof(GX2Query) == 0x40);\n"
state_block = '''\tstatic_assert(sizeof(GX2Query) == 0x40);

\t// Observation-only comparison trace for Bayonetta 2 JP and Xenoblade
\t// Chronicles X. No query values, return codes, lifetime, or ordering are
\t// modified by this block.
\tstatic uint64 s_queryCompareBeginCount = 0;
\tstatic uint64 s_queryCompareEndCount = 0;
\tstatic uint64 s_queryCompareGetCount = 0;
\tstatic uint64 s_queryCompareGetNotReadyCount = 0;
\tstatic uint64 s_queryCompareGetZeroCount = 0;
\tstatic uint64 s_queryCompareGetNonZeroCount = 0;
\tstatic uint64 s_queryCompareConditionalBeginCount = 0;
\tstatic uint64 s_queryCompareConditionalEndCount = 0;

\tstatic bool QueryCompareTraceEnabled(uint64 titleId)
\t{
\t\treturn titleId == 0x000500001011B900ULL || // Bayonetta 2 JP
\t\t\ttitleId == 0x00050000101C4C00ULL || // XCX EU
\t\t\ttitleId == 0x00050000101C4D00ULL || // XCX US
\t\t\ttitleId == 0x0005000010116100ULL;   // XCX JP
\t}

\tstatic bool QueryCompareTraceSample(uint64 n)
\t{
\t\treturn n <= 128 || (n % 1000ULL) == 0;
\t}
'''
gx2 = replace_once(gx2, state_anchor, state_block, "GX2 trace state")

begin_anchor = '''\tvoid GX2QueryBegin(uint32 queryType, GX2Query* query)
\t{
'''
begin_block = '''\tvoid GX2QueryBegin(uint32 queryType, GX2Query* query)
\t{
\t\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\t\tif (QueryCompareTraceEnabled(traceTitleId))
\t\t{
\t\t\tconst uint64 n = ++s_queryCompareBeginCount;
\t\t\tif (QueryCompareTraceSample(n))
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[QUERY_COMPARE] API_BEGIN n={} title={:016x} type={} query={:08x}",
\t\t\t\t\tn, traceTitleId, queryType, MEMPTR<GX2Query>(query).GetMPTR());
\t\t}
'''
gx2 = replace_once(gx2, begin_anchor, begin_block, "GX2 begin trace")

end_anchor = '''\tvoid GX2QueryEnd(uint32 queryType, GX2Query* query)
\t{
\t\tGX2ReserveCmdSpace(2);
'''
end_block = '''\tvoid GX2QueryEnd(uint32 queryType, GX2Query* query)
\t{
\t\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\t\tif (QueryCompareTraceEnabled(traceTitleId))
\t\t{
\t\t\tconst uint64 n = ++s_queryCompareEndCount;
\t\t\tif (QueryCompareTraceSample(n))
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[QUERY_COMPARE] API_END n={} title={:016x} type={} query={:08x}",
\t\t\t\t\tn, traceTitleId, queryType, MEMPTR<GX2Query>(query).GetMPTR());
\t\t}
\t\tGX2ReserveCmdSpace(2);
'''
gx2 = replace_once(gx2, end_anchor, end_block, "GX2 end trace")

get_anchor = '''\tuint32 GX2QueryGetOcclusionResult(GX2Query* query, uint64be* resultOut)
\t{
'''
get_block = '''\tuint32 GX2QueryGetOcclusionResult(GX2Query* query, uint64be* resultOut)
\t{
\t\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\t\tconst bool traceEnabled = QueryCompareTraceEnabled(traceTitleId);
\t\tif (traceEnabled)
\t\t\t++s_queryCompareGetCount;
'''
gx2 = replace_once(gx2, get_anchor, get_block, "GX2 get trace entry")

cpu_not_ready_anchor = '''\t\tif (query->reg[LATTE_GC_NUM_RB * 4 + 1] == _swapEndianU32('OCPU') && query->reg[LATTE_GC_NUM_RB * 4 + 0] == 0)
\t\t{
\t\t\t// CPU query result not ready
\t\t\treturn GX2_FALSE;
\t\t}
'''
cpu_not_ready_block = '''\t\tif (query->reg[LATTE_GC_NUM_RB * 4 + 1] == _swapEndianU32('OCPU') && query->reg[LATTE_GC_NUM_RB * 4 + 0] == 0)
\t\t{
\t\t\t// CPU query result not ready
\t\t\tif (traceEnabled)
\t\t\t{
\t\t\t\tconst uint64 n = ++s_queryCompareGetNotReadyCount;
\t\t\t\tif (QueryCompareTraceSample(n))
\t\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\t"[QUERY_COMPARE] GET_NOT_READY n={} calls={} title={:016x} query={:08x} reason=cpu-marker rawStart={:016x} rawEnd={:016x}",
\t\t\t\t\t\tn, s_queryCompareGetCount, traceTitleId, MEMPTR<GX2Query>(query).GetMPTR(),
\t\t\t\t\t\t*(uint64*)(query->reg + 0), *(uint64*)(query->reg + 2));
\t\t\t}
\t\t\treturn GX2_FALSE;
\t\t}
'''
gx2 = replace_once(gx2, cpu_not_ready_anchor, cpu_not_ready_block, "CPU not-ready trace")

high_bit_anchor = '''\t\tif ((startValue & 0x8000000000000000ULL) || (endValue & 0x8000000000000000ULL))
\t\t{
\t\t\treturn GX2_FALSE;
\t\t}
\t\t*resultOut = endValue - startValue;
'''
high_bit_block = '''\t\tif ((startValue & 0x8000000000000000ULL) || (endValue & 0x8000000000000000ULL))
\t\t{
\t\t\tif (traceEnabled)
\t\t\t{
\t\t\t\tconst uint64 n = ++s_queryCompareGetNotReadyCount;
\t\t\t\tif (QueryCompareTraceSample(n))
\t\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\t"[QUERY_COMPARE] GET_NOT_READY n={} calls={} title={:016x} query={:08x} reason=high-bit rawStart={:016x} rawEnd={:016x}",
\t\t\t\t\t\tn, s_queryCompareGetCount, traceTitleId, MEMPTR<GX2Query>(query).GetMPTR(), startValue, endValue);
\t\t\t}
\t\t\treturn GX2_FALSE;
\t\t}
\t\tif (traceEnabled)
\t\t{
\t\t\tconst uint64 resultValue = endValue - startValue;
\t\t\tif (resultValue == 0)
\t\t\t{
\t\t\t\tconst uint64 n = ++s_queryCompareGetZeroCount;
\t\t\t\tif (QueryCompareTraceSample(n))
\t\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\t"[QUERY_COMPARE] GET_READY_ZERO n={} calls={} title={:016x} query={:08x} rawStart={:016x} rawEnd={:016x} notReady={} nonzero={}",
\t\t\t\t\t\tn, s_queryCompareGetCount, traceTitleId, MEMPTR<GX2Query>(query).GetMPTR(), startValue, endValue,
\t\t\t\t\t\ts_queryCompareGetNotReadyCount, s_queryCompareGetNonZeroCount);
\t\t\t}
\t\t\telse
\t\t\t{
\t\t\t\tconst uint64 n = ++s_queryCompareGetNonZeroCount;
\t\t\t\tif (QueryCompareTraceSample(n))
\t\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\t"[QUERY_COMPARE] GET_READY_NONZERO n={} calls={} title={:016x} query={:08x} result={} rawStart={:016x} rawEnd={:016x} notReady={} zero={}",
\t\t\t\t\t\tn, s_queryCompareGetCount, traceTitleId, MEMPTR<GX2Query>(query).GetMPTR(), resultValue, startValue, endValue,
\t\t\t\t\t\ts_queryCompareGetNotReadyCount, s_queryCompareGetZeroCount);
\t\t\t}
\t\t}
\t\t*resultOut = endValue - startValue;
'''
gx2 = replace_once(gx2, high_bit_anchor, high_bit_block, "ready result trace")

cond_begin_anchor = '''\tvoid GX2QueryBeginConditionalRender(uint32 queryType, GX2Query* query, uint32 dontWaitBool, uint32 pixelsMustPassBool)
\t{
\t\tGX2ReserveCmdSpace(3);
'''
cond_begin_block = '''\tvoid GX2QueryBeginConditionalRender(uint32 queryType, GX2Query* query, uint32 dontWaitBool, uint32 pixelsMustPassBool)
\t{
\t\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\t\tif (QueryCompareTraceEnabled(traceTitleId))
\t\t{
\t\t\tconst uint64 n = ++s_queryCompareConditionalBeginCount;
\t\t\tif (QueryCompareTraceSample(n))
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[QUERY_COMPARE] CONDITIONAL_BEGIN n={} title={:016x} type={} query={:08x} dontWait={} pixelsMustPass={}",
\t\t\t\t\tn, traceTitleId, queryType, MEMPTR<GX2Query>(query).GetMPTR(), dontWaitBool, pixelsMustPassBool);
\t\t}
\t\tGX2ReserveCmdSpace(3);
'''
gx2 = replace_once(gx2, cond_begin_anchor, cond_begin_block, "conditional begin trace")

cond_end_anchor = '''\tvoid GX2QueryEndConditionalRender()
\t{
\t\tGX2ReserveCmdSpace(3);
'''
cond_end_block = '''\tvoid GX2QueryEndConditionalRender()
\t{
\t\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\t\tif (QueryCompareTraceEnabled(traceTitleId))
\t\t{
\t\t\tconst uint64 n = ++s_queryCompareConditionalEndCount;
\t\t\tif (QueryCompareTraceSample(n))
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[QUERY_COMPARE] CONDITIONAL_END n={} title={:016x}", n, traceTitleId);
\t\t}
\t\tGX2ReserveCmdSpace(3);
'''
gx2 = replace_once(gx2, cond_end_anchor, cond_end_block, "conditional end trace")

gx2_path.write_text(gx2, encoding="utf-8", newline="\n")

# -----------------------------------------------------------------------------
# Latte core side: observe when actual renderer results become guest-visible.
# -----------------------------------------------------------------------------
core_path = Path("src/Cafe/HW/Latte/Core/LatteQuery.cpp")
core = core_path.read_text(encoding="utf-8")
core = replace_once(
    core,
    '#include "Cafe/HW/Latte/Renderer/Renderer.h"\n',
    '#include "Cafe/HW/Latte/Renderer/Renderer.h"\n#include "Cafe/CafeSystem.h"\n',
    "CafeSystem include",
)

core_state_anchor = 'LatteQueryObject* _currentlyActiveRendererQuery = {0};\n'
core_state_block = '''LatteQueryObject* _currentlyActiveRendererQuery = {0};

// Observation-only renderer-result side of the Bayonetta 2 / XCX comparison.
static uint64 s_queryCompareFinishCount = 0;
static uint64 s_queryCompareFinishZeroCount = 0;
static uint64 s_queryCompareFinishNonZeroCount = 0;

static bool QueryCompareCoreTraceEnabled(uint64 titleId)
{
\treturn titleId == 0x000500001011B900ULL ||
\t\ttitleId == 0x00050000101C4C00ULL ||
\t\ttitleId == 0x00050000101C4D00ULL ||
\t\ttitleId == 0x0005000010116100ULL;
}

static bool QueryCompareCoreTraceSample(uint64 n)
{
\treturn n <= 128 || (n % 1000ULL) == 0;
}
'''
core = replace_once(core, core_state_anchor, core_state_block, "core trace state")

finish_anchor = '''void LatteQuery_finishGX2Query(LatteGX2QueryInformation* gx2Query)
{
\tuint32* queryObjectData = (uint32*)memory_getPointerFromVirtualOffset(gx2Query->queryMPTR);
'''
finish_block = '''void LatteQuery_finishGX2Query(LatteGX2QueryInformation* gx2Query)
{
\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\tif (QueryCompareCoreTraceEnabled(traceTitleId))
\t{
\t\t++s_queryCompareFinishCount;
\t\tif (gx2Query->sampleSum == 0)
\t\t{
\t\t\tconst uint64 n = ++s_queryCompareFinishZeroCount;
\t\t\tif (QueryCompareCoreTraceSample(n))
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[QUERY_COMPARE] FINISH_ZERO n={} total={} title={:016x} query={:08x} startEvent={} endEvent={} sampleSum=0 nonzero={}",
\t\t\t\t\tn, s_queryCompareFinishCount, traceTitleId, gx2Query->queryMPTR,
\t\t\t\t\tgx2Query->queryEventStart, gx2Query->queryEventEnd, s_queryCompareFinishNonZeroCount);
\t\t}
\t\telse
\t\t{
\t\t\tconst uint64 n = ++s_queryCompareFinishNonZeroCount;
\t\t\tif (QueryCompareCoreTraceSample(n))
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[QUERY_COMPARE] FINISH_NONZERO n={} total={} title={:016x} query={:08x} startEvent={} endEvent={} sampleSum={} zero={}",
\t\t\t\t\tn, s_queryCompareFinishCount, traceTitleId, gx2Query->queryMPTR,
\t\t\t\t\tgx2Query->queryEventStart, gx2Query->queryEventEnd, gx2Query->sampleSum,
\t\t\t\t\ts_queryCompareFinishZeroCount);
\t\t}
\t}
\tuint32* queryObjectData = (uint32*)memory_getPointerFromVirtualOffset(gx2Query->queryMPTR);
'''
core = replace_once(core, finish_anchor, finish_block, "finish result trace")

core_path.write_text(core, encoding="utf-8", newline="\n")

# Static postconditions: markers must exist and baseline result/lifetime behavior
# must still be present verbatim.
patched_gx2 = gx2_path.read_text(encoding="utf-8")
patched_core = core_path.read_text(encoding="utf-8")
for marker in (
    "[QUERY_COMPARE] API_BEGIN",
    "[QUERY_COMPARE] API_END",
    "[QUERY_COMPARE] GET_NOT_READY",
    "[QUERY_COMPARE] GET_READY_ZERO",
    "[QUERY_COMPARE] GET_READY_NONZERO",
    "[QUERY_COMPARE] CONDITIONAL_BEGIN",
    "[QUERY_COMPARE] CONDITIONAL_END",
):
    if marker not in patched_gx2:
        raise RuntimeError(f"missing GX2 marker: {marker}")
for marker in ("[QUERY_COMPARE] FINISH_ZERO", "[QUERY_COMPARE] FINISH_NONZERO"):
    if marker not in patched_core:
        raise RuntimeError(f"missing core marker: {marker}")

required_baseline = (
    "*resultOut = endValue - startValue;",
    "return GX2_TRUE;",
    "return GX2_FALSE;",
    "*(uint64*)(queryInfo->reg + 2) = 0x100000;",
)
for token in required_baseline:
    if token not in patched_gx2:
        raise RuntimeError(f"baseline GX2 behavior token missing: {token}")

for token in (
    "*(uint64*)(queryObjectData + 2) = gx2Query->sampleSum;",
    "it->sampleSum += numSamplesPassed;",
):
    if token not in patched_core:
        raise RuntimeError(f"baseline core behavior token missing: {token}")

print("Bayonetta 2 / XCX query-consumption observation trace installed; behavior unchanged")
