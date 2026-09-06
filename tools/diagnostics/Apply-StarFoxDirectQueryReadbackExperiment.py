from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# One-variable behavior experiment for Star Fox Zero JP only.
# Bypass Cemu's vkCmdCopyQueryPoolResults -> persistently mapped buffer result
# consumption and instead fetch the completed Vulkan occlusion-query result with
# vkGetQueryPoolResults after the owning command buffer has finished.
# Other titles retain the existing path unchanged.

api_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanAPI.h")
api = api_path.read_text(encoding="utf-8")
api_anchor = "VKFUNC_DEVICE(vkCmdCopyQueryPoolResults);\n"
api_get_query_results = "VKFUNC_DEVICE(vkGetQueryPoolResults);\n"
api_get_query_results_count = api.count(api_get_query_results)
if api_get_query_results_count == 0:
    api = replace_once(
        api,
        api_anchor,
        api_anchor + api_get_query_results,
        "Vulkan query direct-readback function loader",
    )
elif api_get_query_results_count != 1:
    raise RuntimeError(
        f"Vulkan query direct-readback loader expected at most one existing declaration, found {api_get_query_results_count}"
    )
if api.count(api_get_query_results) != 1:
    raise RuntimeError("Vulkan query direct-readback loader declaration count is not exactly one")
api_path.write_text(api, encoding="utf-8", newline="\n")

query_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanQuery.cpp")
query = query_path.read_text(encoding="utf-8")
query = replace_once(
    query,
    '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h"\n',
    '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h"\n#include "Cafe/CafeSystem.h"\n',
    "Star Fox direct-readback CafeSystem include",
)

get_result_anchor = "bool LatteQueryObjectVk::getResult(uint64& numSamplesPassed)\n"
helper = '''static uint64 s_starFoxDirectQueryReadbackCount = 0;

static bool StarFoxDirectQueryReadbackEnabled()
{
\treturn CafeSystem::GetForegroundTitleId() == 0x00050000101AFF00ULL;
}

'''
query = replace_once(
    query,
    get_result_anchor,
    helper + get_result_anchor,
    "Star Fox direct-readback helper insertion",
)

old_sum = "\t\tm_acccumulatedSum += m_rendererVk->m_occlusionQueries.ptrQueryResults[it.queryIndex];\n"
new_sum = '''\t\tconst uint64 mappedResultValue = m_rendererVk->m_occlusionQueries.ptrQueryResults[it.queryIndex];
\t\tuint64 fragmentResult = mappedResultValue;
\t\tif (StarFoxDirectQueryReadbackEnabled())
\t\t{
\t\t\tuint64 directResultValue = 0;
\t\t\tconst VkResult directResult = vkGetQueryPoolResults(
\t\t\t\tm_rendererVk->GetLogicalDevice(),
\t\t\t\tm_rendererVk->m_occlusionQueries.queryPool,
\t\t\t\tit.queryIndex,
\t\t\t\t1,
\t\t\t\tsizeof(directResultValue),
\t\t\t\t&directResultValue,
\t\t\t\tsizeof(uint64),
\t\t\t\tVK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT);
\t\t\tconst uint64 n = ++s_starFoxDirectQueryReadbackCount;
\t\t\tconst bool valueMismatch = directResult == VK_SUCCESS && directResultValue != mappedResultValue;
\t\t\tif (directResult == VK_SUCCESS)
\t\t\t\tfragmentResult = directResultValue;
\t\t\tif (n <= 128 || (n % 1000ULL) == 0 || directResult != VK_SUCCESS || valueMismatch)
\t\t\t{
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[STARFOX_QUERY_DIRECT] n={} queryIndex={} vkResult={} direct={} mapped={} selected={} mismatch={}",
\t\t\t\t\tn, it.queryIndex, static_cast<sint32>(directResult), directResultValue,
\t\t\t\t\tmappedResultValue, fragmentResult, valueMismatch ? 1 : 0);
\t\t\t}
\t\t}
\t\tm_acccumulatedSum += fragmentResult;
'''
query = replace_once(query, old_sum, new_sum, "Star Fox direct-readback result selection")

for token in (
    "[STARFOX_QUERY_DIRECT]",
    "vkGetQueryPoolResults(",
    "StarFoxDirectQueryReadbackEnabled()",
    "0x00050000101AFF00ULL",
    "m_acccumulatedSum += fragmentResult;",
    "valueMismatch",
):
    if token not in query:
        raise RuntimeError(f"Star Fox direct-readback token missing: {token}")

if "m_acccumulatedSum += m_rendererVk->m_occlusionQueries.ptrQueryResults[it.queryIndex];" in query:
    raise RuntimeError("old unconditional mapped-buffer accumulation path still present")

query_path.write_text(query, encoding="utf-8", newline="\n")
print("Star Fox Zero direct Vulkan query readback experiment installed; other titles unchanged")
