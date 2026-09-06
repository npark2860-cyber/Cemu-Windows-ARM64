from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# Observation-only full trace for one recurring Star Fox Zero JP CPU occlusion
# query slot seen switching between completed ZERO and NONZERO.
#
# Run #18 and Run #21 showed the same logical slot as the 26th Star Fox query
# begin, while its guest MPTR shifted by 0x40 between runs. Capture the 26th
# query dynamically instead of hard-coding a guest address.
#
# No query values, readiness, ordering, submission, render state or draw
# behavior are changed.
STARFOX_TITLE = "0x00050000101AFF00ULL"
FOCUS_ORDINAL = 26

gx2_path = Path("src/Cafe/OS/libs/gx2/GX2_Query.cpp")
gx2 = gx2_path.read_text(encoding="utf-8")

state_anchor = "\tstatic uint64 s_queryCompareConditionalEndCount = 0;\n"
state_block = state_anchor + '''\tstatic uint64 s_starFoxFocusApiBeginCount = 0;
\tstatic uint64 s_starFoxFocusGetCount = 0;
\tstatic uint32 s_starFoxFocusQueryMPTR = 0;
'''
gx2 = replace_once(gx2, state_anchor, state_block, "Star Fox focus state")

begin_anchor = '''\tvoid GX2QueryBegin(uint32 queryType, GX2Query* query)
\t{
\t\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\t\tif (QueryCompareTraceEnabled(traceTitleId))
'''
begin_block = '''\tvoid GX2QueryBegin(uint32 queryType, GX2Query* query)
\t{
\t\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\t\tif (traceTitleId == 0x00050000101AFF00ULL)
\t\t{
\t\t\tconst uint64 focusOrdinal = ++s_starFoxFocusApiBeginCount;
\t\t\tif (focusOrdinal == 26)
\t\t\t{
\t\t\t\ts_starFoxFocusQueryMPTR = MEMPTR<GX2Query>(query).GetMPTR();
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[STARFOX_QUERY_FOCUS] CAPTURE_API ordinal={} query={:08x} type={}",
\t\t\t\t\tfocusOrdinal, s_starFoxFocusQueryMPTR, queryType);
\t\t\t}
\t\t}
\t\tif (QueryCompareTraceEnabled(traceTitleId))
'''
gx2 = replace_once(gx2, begin_anchor, begin_block, "Star Fox focus API capture")

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
\t\tconst bool starFoxFocus = traceTitleId == 0x00050000101AFF00ULL &&
\t\t\ts_starFoxFocusQueryMPTR != 0 && focusQueryMPTR == s_starFoxFocusQueryMPTR;
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

for token in (
    "[STARFOX_QUERY_FOCUS] CAPTURE_API",
    "[STARFOX_QUERY_FOCUS] GET_READY",
    STARFOX_TITLE,
    "focusOrdinal == 26",
):
    if token not in gx2:
        raise RuntimeError(f"Star Fox focus GX2 token missing: {token}")

gx2_path.write_text(gx2, encoding="utf-8", newline="\n")

core_path = Path("src/Cafe/HW/Latte/Core/LatteQuery.cpp")
core = core_path.read_text(encoding="utf-8")

core_state_anchor = "static uint64 s_queryCompareFinishNonZeroCount = 0;\n"
core_state_block = core_state_anchor + '''static uint64 s_starFoxFocusCoreBeginCount = 0;
static uint64 s_starFoxFocusFinishCount = 0;
static uint32 s_starFoxFocusCoreQueryMPTR = 0;
'''
core = replace_once(core, core_state_anchor, core_state_block, "Star Fox focus core state")

core_begin_anchor = '''void LatteQuery_BeginOcclusionQuery(MPTR queryMPTR)
{
\tif (checkQueriesCounter < 7)
'''
core_begin_block = '''void LatteQuery_BeginOcclusionQuery(MPTR queryMPTR)
{
\tconst uint64 starFoxFocusTitleId = CafeSystem::GetForegroundTitleId();
\tif (starFoxFocusTitleId == 0x00050000101AFF00ULL)
\t{
\t\tconst uint64 focusOrdinal = ++s_starFoxFocusCoreBeginCount;
\t\tif (focusOrdinal == 26)
\t\t{
\t\t\ts_starFoxFocusCoreQueryMPTR = queryMPTR;
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[STARFOX_QUERY_FOCUS] CAPTURE_CORE ordinal={} query={:08x}",
\t\t\t\tfocusOrdinal, s_starFoxFocusCoreQueryMPTR);
\t\t}
\t}
\tif (checkQueriesCounter < 7)
'''
core = replace_once(core, core_begin_anchor, core_begin_block, "Star Fox focus core capture")

finish_anchor = '''\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\tif (QueryCompareCoreTraceEnabled(traceTitleId))
'''
finish_block = '''\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\tif (traceTitleId == 0x00050000101AFF00ULL &&
\t\ts_starFoxFocusCoreQueryMPTR != 0 && gx2Query->queryMPTR == s_starFoxFocusCoreQueryMPTR)
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

for token in (
    "[STARFOX_QUERY_FOCUS] CAPTURE_CORE",
    "[STARFOX_QUERY_FOCUS] FINISH",
    STARFOX_TITLE,
    "focusOrdinal == 26",
):
    if token not in core:
        raise RuntimeError(f"Star Fox focus core token missing: {token}")

core_path.write_text(core, encoding="utf-8", newline="\n")
print("Star Fox Zero focused query ordinal-capture trace installed; behavior unchanged")
