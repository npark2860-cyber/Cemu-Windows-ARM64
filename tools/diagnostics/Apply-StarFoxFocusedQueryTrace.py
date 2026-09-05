from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# Observation-only full trace for one recurring Star Fox Zero JP CPU occlusion
# query slot seen switching between completed ZERO and NONZERO in Run #18.
# No query values, readiness, ordering, submission, render state or draw behavior
# are changed.
STARFOX_TITLE = "0x00050000101AFF00ULL"
FOCUS_QUERY = "0x460f9fc8"

gx2_path = Path("src/Cafe/OS/libs/gx2/GX2_Query.cpp")
gx2 = gx2_path.read_text(encoding="utf-8")

state_anchor = "\tstatic uint64 s_queryCompareConditionalEndCount = 0;\n"
state_block = state_anchor + '''\tstatic uint64 s_starFoxFocusGeneration = 0;
\tstatic uint64 s_starFoxFocusGetCount = 0;
\tstatic uint64 s_starFoxFocusNotReadyCount = 0;
'''
gx2 = replace_once(gx2, state_anchor, state_block, "Star Fox focus state")

begin_anchor = '''\t\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\t\tif (QueryCompareTraceEnabled(traceTitleId))
'''
begin_block = '''\t\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\t\tconst uint32 focusQueryMPTR = MEMPTR<GX2Query>(query).GetMPTR();
\t\tif (traceTitleId == 0x00050000101AFF00ULL && focusQueryMPTR == 0x460f9fc8)
\t\t{
\t\t\tconst uint64 gen = ++s_starFoxFocusGeneration;
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[STARFOX_QUERY_FOCUS] BEGIN gen={} title={:016x} type={} query={:08x}",
\t\t\t\tgen, traceTitleId, queryType, focusQueryMPTR);
\t\t}
\t\tif (QueryCompareTraceEnabled(traceTitleId))
'''
gx2 = replace_once(gx2, begin_anchor, begin_block, "Star Fox focus begin")

end_anchor = '''\tvoid GX2QueryEnd(uint32 queryType, GX2Query* query)
\t{
\t\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
'''
end_block = '''\tvoid GX2QueryEnd(uint32 queryType, GX2Query* query)
\t{
\t\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\t\tconst uint32 focusQueryMPTR = MEMPTR<GX2Query>(query).GetMPTR();
\t\tif (traceTitleId == 0x00050000101AFF00ULL && focusQueryMPTR == 0x460f9fc8)
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[STARFOX_QUERY_FOCUS] END gen={} title={:016x} type={} query={:08x}",
\t\t\t\ts_starFoxFocusGeneration, traceTitleId, queryType, focusQueryMPTR);
'''
gx2 = replace_once(gx2, end_anchor, end_block, "Star Fox focus end")

get_anchor = '''\t\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\t\tconst bool traceEnabled = QueryCompareTraceEnabled(traceTitleId);
\t\tif (traceEnabled)
'''
get_block = '''\t\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\t\tconst bool traceEnabled = QueryCompareTraceEnabled(traceTitleId);
\t\tconst uint32 focusQueryMPTR = MEMPTR<GX2Query>(query).GetMPTR();
\t\tconst bool starFoxFocus = traceTitleId == 0x00050000101AFF00ULL && focusQueryMPTR == 0x460f9fc8;
\t\tif (starFoxFocus)
\t\t\t++s_starFoxFocusGetCount;
\t\tif (traceEnabled)
'''
gx2 = replace_once(gx2, get_anchor, get_block, "Star Fox focus get entry")

cpu_nr_anchor = '''\t\t\treturn GX2_FALSE;
\t\t}

\t\tuint64 startValue = 0;
'''
cpu_nr_block = '''\t\t\tif (starFoxFocus)
\t\t\t{
\t\t\t\t++s_starFoxFocusNotReadyCount;
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[STARFOX_QUERY_FOCUS] GET_NOT_READY gen={} get={} nr={} query={:08x} reason=cpu-marker",
\t\t\t\t\ts_starFoxFocusGeneration, s_starFoxFocusGetCount, s_starFoxFocusNotReadyCount, focusQueryMPTR);
\t\t\t}
\t\t\treturn GX2_FALSE;
\t\t}

\t\tuint64 startValue = 0;
'''
gx2 = replace_once(gx2, cpu_nr_anchor, cpu_nr_block, "Star Fox focus CPU not-ready")

high_nr_anchor = '''\t\t\treturn GX2_FALSE;
\t\t}
\t\tif (traceEnabled)
'''
high_nr_block = '''\t\t\tif (starFoxFocus)
\t\t\t{
\t\t\t\t++s_starFoxFocusNotReadyCount;
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[STARFOX_QUERY_FOCUS] GET_NOT_READY gen={} get={} nr={} query={:08x} reason=high-bit rawStart={:016x} rawEnd={:016x}",
\t\t\t\t\ts_starFoxFocusGeneration, s_starFoxFocusGetCount, s_starFoxFocusNotReadyCount,
\t\t\t\t\tfocusQueryMPTR, startValue, endValue);
\t\t\t}
\t\t\treturn GX2_FALSE;
\t\t}
\t\tif (traceEnabled)
'''
gx2 = replace_once(gx2, high_nr_anchor, high_nr_block, "Star Fox focus high-bit not-ready")

ready_anchor = '''\t\t*resultOut = endValue - startValue;
\t\treturn GX2_TRUE;
'''
ready_block = '''\t\tif (starFoxFocus)
\t\t{
\t\t\tconst uint64 focusResult = endValue - startValue;
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[STARFOX_QUERY_FOCUS] GET_READY gen={} get={} query={:08x} result={} class={} rawStart={:016x} rawEnd={:016x} nr={}",
\t\t\t\ts_starFoxFocusGeneration, s_starFoxFocusGetCount, focusQueryMPTR, focusResult,
\t\t\t\tfocusResult == 0 ? "ZERO" : "NONZERO", startValue, endValue, s_starFoxFocusNotReadyCount);
\t\t}
\t\t*resultOut = endValue - startValue;
\t\treturn GX2_TRUE;
'''
gx2 = replace_once(gx2, ready_anchor, ready_block, "Star Fox focus ready result")

for token in ("[STARFOX_QUERY_FOCUS] BEGIN", "[STARFOX_QUERY_FOCUS] GET_READY", FOCUS_QUERY, STARFOX_TITLE):
    if token not in gx2:
        raise RuntimeError(f"Star Fox focus GX2 token missing: {token}")

gx2_path.write_text(gx2, encoding="utf-8", newline="\n")

core_path = Path("src/Cafe/HW/Latte/Core/LatteQuery.cpp")
core = core_path.read_text(encoding="utf-8")
core_state_anchor = "static uint64 s_queryCompareFinishNonZeroCount = 0;\n"
core_state_block = core_state_anchor + "static uint64 s_starFoxFocusFinishCount = 0;\n"
core = replace_once(core, core_state_anchor, core_state_block, "Star Fox focus core state")

finish_anchor = '''void LatteQuery_finishGX2Query(LatteGX2QueryInformation* gx2Query)
{
\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
'''
finish_block = '''void LatteQuery_finishGX2Query(LatteGX2QueryInformation* gx2Query)
{
\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\tif (traceTitleId == 0x00050000101AFF00ULL && gx2Query->queryMPTR == 0x460f9fc8)
\t{
\t\tconst uint64 n = ++s_starFoxFocusFinishCount;
\t\tcemuLog_log(LogType::Force,
\t\t\t"[STARFOX_QUERY_FOCUS] FINISH n={} query={:08x} startEvent={} endEvent={} sampleSum={} class={}",
\t\t\tn, gx2Query->queryMPTR, gx2Query->queryEventStart, gx2Query->queryEventEnd,
\t\t\tgx2Query->sampleSum, gx2Query->sampleSum == 0 ? "ZERO" : "NONZERO");
\t}
'''
core = replace_once(core, finish_anchor, finish_block, "Star Fox focus finish")

for token in ("[STARFOX_QUERY_FOCUS] FINISH", FOCUS_QUERY, STARFOX_TITLE):
    if token not in core:
        raise RuntimeError(f"Star Fox focus core token missing: {token}")

core_path.write_text(core, encoding="utf-8", newline="\n")
print("Star Fox Zero focused query full trace installed; behavior unchanged")
