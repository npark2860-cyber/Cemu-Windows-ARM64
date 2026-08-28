from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


path = Path("src/Cafe/HW/Latte/Core/LatteQuery.cpp")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    '#include "Cafe/HW/Latte/Renderer/Renderer.h"\n',
    '#include "Cafe/HW/Latte/Renderer/Renderer.h"\n#include "Cafe/CafeSystem.h"\n',
    "CafeSystem include",
)

state_anchor = 'LatteQueryObject* _currentlyActiveRendererQuery = {0};\n'
state_block = '''LatteQueryObject* _currentlyActiveRendererQuery = {0};

// Bayonetta 2 JP observation-only occlusion-query trace.
// This intentionally does not change query lifetime, ordering, results, or
// renderer behavior. It only establishes whether the nested GX2-query resume
// path and duplicate in-flight pointer condition are exercised at runtime.
static uint64 s_bayo2QueryBeginCount = 0;
static uint64 s_bayo2QueryEndCount = 0;
static uint64 s_bayo2QueryResumeCount = 0;
static uint64 s_bayo2ActiveInFlightInsertCount = 0;
static uint64 s_bayo2ActiveInFlightSeenCount = 0;
static uint64 s_bayo2DuplicatePointerCount = 0;

static bool Bayo2OcclusionTraceEnabled()
{
\treturn CafeSystem::GetForegroundTitleId() == 0x000500001011B900ULL;
}

static bool Bayo2OcclusionTraceSample(uint64 n)
{
\treturn n <= 256 || (n % 1000ULL) == 0;
}

static size_t Bayo2CountInFlightPointer(LatteQueryObject* queryObject)
{
\tsize_t count = 0;
\tfor (auto* it : list_queriesInFlight)
\t\tif (it == queryObject)
\t\t\t++count;
\treturn count;
}
'''
text = replace_once(text, state_anchor, state_block, "trace state")

update_anchor = '''\t\tLatteQueryObject* queryObject = list_queriesInFlight[i];
\t\tcemu_assert_debug(queryObject->queryEnded);
\t\tif( queryObject->queryEnded == false )
\t\t\tcontinue;
'''
update_block = '''\t\tLatteQueryObject* queryObject = list_queriesInFlight[i];
\t\tif (Bayo2OcclusionTraceEnabled() && !queryObject->queryEnded)
\t\t{
\t\t\tconst uint64 n = ++s_bayo2ActiveInFlightSeenCount;
\t\t\tif (Bayo2OcclusionTraceSample(n))
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[BAYO2_OCCLUSION] ACTIVE_IN_FLIGHT n={} ptr={} index={} listSize={} activeGX2={} begin={} end={} resume={} insert={} dup={}",
\t\t\t\t\tn, (void*)queryObject, i, list_queriesInFlight.size(), list_activeGX2Queries2.size(),
\t\t\t\t\ts_bayo2QueryBeginCount, s_bayo2QueryEndCount, s_bayo2QueryResumeCount,
\t\t\t\t\ts_bayo2ActiveInFlightInsertCount, s_bayo2DuplicatePointerCount);
\t\t}
\t\tcemu_assert_debug(queryObject->queryEnded);
\t\tif( queryObject->queryEnded == false )
\t\t\tcontinue;
'''
text = replace_once(text, update_anchor, update_block, "active in-flight observation")

end_active_anchor = '''\tif (_currentlyActiveRendererQuery != nullptr)
\t{
\t\tLatteQuery_end(_currentlyActiveRendererQuery, currentEventId);
\t\tlist_queriesInFlight.emplace_back(_currentlyActiveRendererQuery);
\t\t_currentlyActiveRendererQuery = nullptr;
\t}
'''
end_active_block = '''\tif (_currentlyActiveRendererQuery != nullptr)
\t{
\t\tLatteQuery_end(_currentlyActiveRendererQuery, currentEventId);
\t\tif (Bayo2OcclusionTraceEnabled())
\t\t{
\t\t\tconst size_t existing = Bayo2CountInFlightPointer(_currentlyActiveRendererQuery);
\t\t\tif (existing != 0)
\t\t\t{
\t\t\t\tconst uint64 n = ++s_bayo2DuplicatePointerCount;
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[BAYO2_OCCLUSION] DUPLICATE_APPEND n={} ptr={} existing={} event={} listSize={} activeGX2={}",
\t\t\t\t\tn, (void*)_currentlyActiveRendererQuery, existing, currentEventId,
\t\t\t\t\tlist_queriesInFlight.size(), list_activeGX2Queries2.size());
\t\t\t}
\t\t}
\t\tlist_queriesInFlight.emplace_back(_currentlyActiveRendererQuery);
\t\t_currentlyActiveRendererQuery = nullptr;
\t}
'''
text = replace_once(text, end_active_anchor, end_active_block, "duplicate append observation")

begin_event_anchor = '''\tuint64 currentEventId = LatteQuery_getNextEventId();
\t// end any currently active query
'''
begin_event_block = '''\tuint64 currentEventId = LatteQuery_getNextEventId();
\tif (Bayo2OcclusionTraceEnabled())
\t{
\t\tconst uint64 n = ++s_bayo2QueryBeginCount;
\t\tif (Bayo2OcclusionTraceSample(n))
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[BAYO2_OCCLUSION] GX2_BEGIN n={} query={:08x} event={} activeBefore={} inFlight={}",
\t\t\t\tn, queryMPTR, currentEventId, list_activeGX2Queries2.size(), list_queriesInFlight.size());
\t}
\t// end any currently active query
'''
text = replace_once(text, begin_event_anchor, begin_event_block, "GX2 begin observation")

end_event_anchor = '''\tuint64 currentEventId = LatteQuery_getNextEventId();
\t// mark query binding as ended
'''
end_event_block = '''\tuint64 currentEventId = LatteQuery_getNextEventId();
\tif (Bayo2OcclusionTraceEnabled())
\t{
\t\tconst uint64 n = ++s_bayo2QueryEndCount;
\t\tif (Bayo2OcclusionTraceSample(n))
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[BAYO2_OCCLUSION] GX2_END n={} query={:08x} event={} activeBefore={} inFlight={}",
\t\t\t\tn, queryMPTR, currentEventId, list_activeGX2Queries2.size(), list_queriesInFlight.size());
\t}
\t// mark query binding as ended
'''
text = replace_once(text, end_event_anchor, end_event_block, "GX2 end observation")

resume_anchor = '''\tif (hasActiveGX2Query)
\t{
\t\tLatteQueryObject* queryObject = LatteQuery_createSamplePassedQuery();
\t\tLatteQuery_begin(queryObject, currentEventId);
\t\tlist_queriesInFlight.emplace_back(queryObject);
\t\t_currentlyActiveRendererQuery = queryObject;
\t\tcatchOpenGLError();
\t}
'''
resume_block = '''\tif (hasActiveGX2Query)
\t{
\t\tif (Bayo2OcclusionTraceEnabled())
\t\t{
\t\t\tconst uint64 n = ++s_bayo2QueryResumeCount;
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[BAYO2_OCCLUSION] NESTED_RESUME n={} event={} activeGX2={} inFlight={}",
\t\t\t\tn, currentEventId, list_activeGX2Queries2.size(), list_queriesInFlight.size());
\t\t}
\t\tLatteQueryObject* queryObject = LatteQuery_createSamplePassedQuery();
\t\tLatteQuery_begin(queryObject, currentEventId);
\t\tif (Bayo2OcclusionTraceEnabled())
\t\t{
\t\t\tconst uint64 n = ++s_bayo2ActiveInFlightInsertCount;
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[BAYO2_OCCLUSION] ACTIVE_INSERT n={} ptr={} ended={} event={} listBefore={} activeGX2={}",
\t\t\t\tn, (void*)queryObject, queryObject->queryEnded ? 1 : 0, currentEventId,
\t\t\t\tlist_queriesInFlight.size(), list_activeGX2Queries2.size());
\t\t}
\t\tlist_queriesInFlight.emplace_back(queryObject);
\t\t_currentlyActiveRendererQuery = queryObject;
\t\tcatchOpenGLError();
\t}
'''
text = replace_once(text, resume_anchor, resume_block, "nested resume observation")

path.write_text(text, encoding="utf-8", newline="\n")

# Static invariants: observation markers must exist and the suspicious original
# append remains present. This script must not perform a behavior fix.
patched = path.read_text(encoding="utf-8")
for marker in (
    "[BAYO2_OCCLUSION] GX2_BEGIN",
    "[BAYO2_OCCLUSION] GX2_END",
    "[BAYO2_OCCLUSION] NESTED_RESUME",
    "[BAYO2_OCCLUSION] ACTIVE_INSERT",
    "[BAYO2_OCCLUSION] ACTIVE_IN_FLIGHT",
    "[BAYO2_OCCLUSION] DUPLICATE_APPEND",
):
    if marker not in patched:
        raise RuntimeError(f"missing marker: {marker}")

if "list_queriesInFlight.emplace_back(queryObject);" not in patched:
    raise RuntimeError("behavior-changing fix detected: original nested append missing")

print("Bayonetta 2 occlusion-query observation trace installed; behavior unchanged")
