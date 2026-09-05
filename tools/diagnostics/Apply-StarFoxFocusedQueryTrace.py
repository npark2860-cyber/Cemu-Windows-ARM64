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
state_block = state_anchor + "\tstatic uint64 s_starFoxFocusGetCount = 0;\n"
gx2 = replace_once(gx2, state_anchor, state_block, "Star Fox focus state")

get_anchor = '''\tuint32 GX2QueryGetOcclusionResult(GX2Query* query, uint64be* resultOut)
\t{
\t\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\t\tconst bool traceEnabled = QueryCompareTraceEnabled(traceTitleId);
'''
get_block = '''\tuint32 GX2QueryGetOcclusionResult(GX2Query* query, uint64be* resultOut)
\t{
\t\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\t\tconst bool traceEnabled = QueryCompareTraceEnabled(traceTitleId);
\t\tconst uint32 focusQueryMPTR = MEMPTR<GX2Query>(query).GetMPTR();
\t\tconst bool starFoxFocus = traceTitleId == 0x00050000101AFF00ULL && focusQueryMPTR == 0x460f9fc8;
\t\tif (starFoxFocus)
\t\t\t++s_starFoxFocusGetCount;
'''
gx2 = replace_once(gx2, get_anchor, get_block, "Star Fox focus GET entry")

ready_anchor = '''\t\t*resultOut = endValue - startValue;
\t\treturn GX2_TRUE;
'''
ready_block = '''\t\tif (starFoxFocus)
\t\t{
\t\t\tconst uint64 focusResult = endValue - startValue;
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[STARFOX_QUERY_FOCUS] GET_READY seq={} query={:08x} result={} class={} rawStart={:016x} rawEnd={:016x}",
\t\t\t\ts_starFoxFocusGetCount, focusQueryMPTR, focusResult,
\t\t\t\tfocusResult == 0 ? "ZERO" : "NONZERO", startValue, endValue);
\t\t}
\t\t*resultOut = endValue - startValue;
\t\treturn GX2_TRUE;
'''
gx2 = replace_once(gx2, ready_anchor, ready_block, "Star Fox focus ready result")

for token in ("[STARFOX_QUERY_FOCUS] GET_READY", FOCUS_QUERY, STARFOX_TITLE):
    if token not in gx2:
        raise RuntimeError(f"Star Fox focus GX2 token missing: {token}")

gx2_path.write_text(gx2, encoding="utf-8", newline="\n")

core_path = Path("src/Cafe/HW/Latte/Core/LatteQuery.cpp")
core = core_path.read_text(encoding="utf-8")
core_state_anchor = "static uint64 s_queryCompareFinishNonZeroCount = 0;\n"
core_state_block = core_state_anchor + "static uint64 s_starFoxFocusFinishCount = 0;\n"
core = replace_once(core, core_state_anchor, core_state_block, "Star Fox focus core state")

finish_anchor = '''\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\tif (QueryCompareCoreTraceEnabled(traceTitleId))
'''
finish_block = '''\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\tif (traceTitleId == 0x00050000101AFF00ULL && gx2Query->queryMPTR == 0x460f9fc8)
\t{
\t\tconst uint64 n = ++s_starFoxFocusFinishCount;
\t\tcemuLog_log(LogType::Force,
\t\t\t"[STARFOX_QUERY_FOCUS] FINISH seq={} query={:08x} startEvent={} endEvent={} sampleSum={} class={}",
\t\t\tn, gx2Query->queryMPTR, gx2Query->queryEventStart, gx2Query->queryEventEnd,
\t\t\tgx2Query->sampleSum, gx2Query->sampleSum == 0 ? "ZERO" : "NONZERO");
\t}
\tif (QueryCompareCoreTraceEnabled(traceTitleId))
'''
core = replace_once(core, finish_anchor, finish_block, "Star Fox focus FINISH")

for token in ("[STARFOX_QUERY_FOCUS] FINISH", FOCUS_QUERY, STARFOX_TITLE):
    if token not in core:
        raise RuntimeError(f"Star Fox focus core token missing: {token}")

core_path.write_text(core, encoding="utf-8", newline="\n")
print("Star Fox Zero focused query full trace installed; behavior unchanged")
