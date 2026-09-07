from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# Observation-only experiment for Xenoblade Chronicles X.
# The production Star Fox Zero/Bayonetta 2 workaround remains unchanged.
# For XCX, read the already-finished Vulkan query directly and compare it with
# the mapped copy result, but NEVER select the direct value or retain/release
# fragments differently from baseline behavior.

query_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanQuery.cpp")
query = query_path.read_text(encoding="utf-8")

helper_anchor = '''static bool UseDirectQueryReadbackWorkaround()
{
\tconst uint64 titleId = CafeSystem::GetForegroundTitleId();
\treturn titleId == 0x00050000101AFF00ULL || // Star Fox Zero JP
\t\ttitleId == 0x000500001011B900ULL;   // Bayonetta 2 JP
}
'''
helper_new = helper_anchor + '''
static uint64 s_xcxDirectObserveCount = 0;
static uint64 s_xcxDirectObserveMismatchCount = 0;
static uint64 s_xcxDirectObserveNotReadyCount = 0;

static bool ObserveXCXDirectQueryReadback()
{
\tconst uint64 titleId = CafeSystem::GetForegroundTitleId();
\treturn titleId == 0x00050000101C4C00ULL || // XCX EU
\t\ttitleId == 0x00050000101C4D00ULL || // XCX US
\t\ttitleId == 0x0005000010116100ULL;   // XCX JP
}
'''
query = replace_once(query, helper_anchor, helper_new, "XCX direct-query observer helper")

sum_anchor = '''\t\tm_acccumulatedSum += fragmentResult;
\t\treleaseQueryIndex(it.queryIndex);
'''
observer = '''\t\tif (ObserveXCXDirectQueryReadback())
\t\t{
\t\t\tconst uint64 mappedResult = fragmentResult;
\t\t\tuint64 directResult = 0;
\t\t\tconst VkResult result = vkGetQueryPoolResults(
\t\t\t\tm_rendererVk->GetLogicalDevice(),
\t\t\t\tm_rendererVk->m_occlusionQueries.queryPool,
\t\t\t\tit.queryIndex,
\t\t\t\t1,
\t\t\t\tsizeof(directResult),
\t\t\t\t&directResult,
\t\t\t\tsizeof(uint64),
\t\t\t\tVK_QUERY_RESULT_64_BIT);
\t\t\tconst uint64 n = ++s_xcxDirectObserveCount;
\t\t\tconst bool mismatch = result == VK_SUCCESS && directResult != mappedResult;
\t\t\tif (mismatch)
\t\t\t\t++s_xcxDirectObserveMismatchCount;
\t\t\tif (result == VK_NOT_READY)
\t\t\t\t++s_xcxDirectObserveNotReadyCount;
\t\t\tif (n <= 128 || (n % 1000ULL) == 0 || result != VK_SUCCESS)
\t\t\t{
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[XCX_QUERY_DIRECT] n={} title={:016x} queryIndex={} vkResult={} direct={} mapped={} mismatch={} mismatchTotal={} notReadyTotal={}",
\t\t\t\t\tn, CafeSystem::GetForegroundTitleId(), it.queryIndex, static_cast<sint32>(result), directResult,
\t\t\t\t\tmappedResult, mismatch ? 1 : 0, s_xcxDirectObserveMismatchCount, s_xcxDirectObserveNotReadyCount);
\t\t\t}
\t\t}

\t\tm_acccumulatedSum += fragmentResult;
\t\treleaseQueryIndex(it.queryIndex);
'''
query = replace_once(query, sum_anchor, observer, "XCX direct-query observer insertion")

required = (
    "[XCX_QUERY_DIRECT]",
    "ObserveXCXDirectQueryReadback()",
    "0x00050000101C4C00ULL",
    "0x00050000101C4D00ULL",
    "0x0005000010116100ULL",
    "m_acccumulatedSum += fragmentResult;",
    "VK_QUERY_RESULT_64_BIT);",
)
for token in required:
    if token not in query:
        raise RuntimeError(f"XCX observer token missing: {token}")

# Safety: XCX must not be added to the production direct-selection workaround.
workaround_block = query.split("static bool UseDirectQueryReadbackWorkaround()", 1)[1].split("static uint64 s_xcxDirectObserveCount", 1)[0]
for xcx_id in ("101C4C00", "101C4D00", "10116100"):
    if xcx_id in workaround_block:
        raise RuntimeError(f"XCX title leaked into direct-selection workaround: {xcx_id}")

query_path.write_text(query, encoding="utf-8", newline="\n")
print("XCX Vulkan direct-query observer installed; mapped result remains authoritative and fragment behavior is unchanged")
