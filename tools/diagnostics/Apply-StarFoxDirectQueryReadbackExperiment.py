from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# Preserve the runtime-PASS direct-readback behavior for Star Fox Zero JP and
# Bayonetta 2 JP, while adding observation-only metadata around the existing
# mapped vkCmdCopyQueryPoolResults path. Other titles remain unchanged.

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

# Record the exact memory-type selection inputs and resolved memory-type flags
# for the persistent query-result buffer. The allocation requests themselves are
# unchanged from the runtime-PASS path.
renderer_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
renderer = renderer_path.read_text(encoding="utf-8")
old_allocation = '''\t// occlusion query result buffer
\tif (!memoryManager->CreateBuffer(OCCLUSION_QUERY_POOL_SIZE * sizeof(uint64), VK_BUFFER_USAGE_TRANSFER_DST_BIT, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT | VK_MEMORY_PROPERTY_HOST_CACHED_BIT, m_occlusionQueries.bufferQueryResults, m_occlusionQueries.memoryQueryResults))
\t{
\t\tmemoryManager->CreateBuffer(OCCLUSION_QUERY_POOL_SIZE * sizeof(uint64), VK_BUFFER_USAGE_TRANSFER_DST_BIT, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT | VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_CACHED_BIT, m_occlusionQueries.bufferQueryResults, m_occlusionQueries.memoryQueryResults);
\t}
\tbufferPtr = nullptr;
'''
new_allocation = '''\t// occlusion query result buffer
\tconst VkMemoryPropertyFlags queryResultPrimaryProperties = VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT | VK_MEMORY_PROPERTY_HOST_CACHED_BIT;
\tconst VkMemoryPropertyFlags queryResultFallbackProperties = VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT | VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_CACHED_BIT;
\tVkMemoryPropertyFlags queryResultRequestedProperties = queryResultPrimaryProperties;
\tbool queryResultFallback = false;
\tif (!memoryManager->CreateBuffer(OCCLUSION_QUERY_POOL_SIZE * sizeof(uint64), VK_BUFFER_USAGE_TRANSFER_DST_BIT, queryResultPrimaryProperties, m_occlusionQueries.bufferQueryResults, m_occlusionQueries.memoryQueryResults))
\t{
\t\tqueryResultFallback = true;
\t\tqueryResultRequestedProperties = queryResultFallbackProperties;
\t\tmemoryManager->CreateBuffer(OCCLUSION_QUERY_POOL_SIZE * sizeof(uint64), VK_BUFFER_USAGE_TRANSFER_DST_BIT, queryResultFallbackProperties, m_occlusionQueries.bufferQueryResults, m_occlusionQueries.memoryQueryResults);
\t}
\tVkMemoryRequirements queryResultMemoryRequirements{};
\tvkGetBufferMemoryRequirements(m_logicalDevice, m_occlusionQueries.bufferQueryResults, &queryResultMemoryRequirements);
\tuint32 queryResultMemoryTypeIndex = 0xFFFFFFFFu;
\tconst bool queryResultMemoryTypeFound = memoryManager->FindMemoryType(queryResultMemoryRequirements.memoryTypeBits, queryResultRequestedProperties, queryResultMemoryTypeIndex);
\tVkPhysicalDeviceMemoryProperties queryResultMemoryProperties{};
\tvkGetPhysicalDeviceMemoryProperties(m_physicalDevice, &queryResultMemoryProperties);
\tVkMemoryPropertyFlags queryResultActualProperties = 0;
\tuint32 queryResultHeapIndex = 0xFFFFFFFFu;
\tif (queryResultMemoryTypeFound && queryResultMemoryTypeIndex < queryResultMemoryProperties.memoryTypeCount)
\t{
\t\tqueryResultActualProperties = queryResultMemoryProperties.memoryTypes[queryResultMemoryTypeIndex].propertyFlags;
\t\tqueryResultHeapIndex = queryResultMemoryProperties.memoryTypes[queryResultMemoryTypeIndex].heapIndex;
\t}
\tcemuLog_log(LogType::Force,
\t\t"[QUERY_MAP_META] found={} memoryType={} heap={} flags=0x{:08x} requested=0x{:08x} fallback={}",
\t\tqueryResultMemoryTypeFound ? 1 : 0, queryResultMemoryTypeIndex, queryResultHeapIndex,
\t\tstatic_cast<uint32>(queryResultActualProperties), static_cast<uint32>(queryResultRequestedProperties), queryResultFallback ? 1 : 0);
\tbufferPtr = nullptr;
'''
renderer = replace_once(renderer, old_allocation, new_allocation, "query-result buffer memory metadata")
for token in (
    "[QUERY_MAP_META]",
    "queryResultMemoryTypeIndex",
    "queryResultActualProperties",
    "queryResultPrimaryProperties",
    "queryResultFallbackProperties",
):
    if token not in renderer:
        raise RuntimeError(f"query-result memory metadata token missing: {token}")
renderer_path.write_text(renderer, encoding="utf-8", newline="\n")

query_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanQuery.cpp")
query = query_path.read_text(encoding="utf-8")
query = replace_once(
    query,
    '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h"\n',
    '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h"\n#include "Cafe/CafeSystem.h"\n',
    "target direct-readback CafeSystem include",
)

get_result_anchor = "bool LatteQueryObjectVk::getResult(uint64& numSamplesPassed)\n"
helper = '''static uint64 s_targetDirectQueryReadbackCount = 0;

static bool TargetDirectQueryReadbackEnabled()
{
\tconst uint64 titleId = CafeSystem::GetForegroundTitleId();
\treturn titleId == 0x00050000101AFF00ULL || // Star Fox Zero JP
\t\ttitleId == 0x000500001011B900ULL;   // Bayonetta 2 JP
}

'''
query = replace_once(
    query,
    get_result_anchor,
    helper + get_result_anchor,
    "target direct-readback helper insertion",
)

old_result_block = '''\t\tif (!m_rendererVk->HasCommandBufferFinished(it.m_finishCommandBuffer))
\t\t\tbreak;
\t\tm_acccumulatedSum += m_rendererVk->m_occlusionQueries.ptrQueryResults[it.queryIndex];
'''
new_result_block = '''\t\tconst bool commandBufferFinished = m_rendererVk->HasCommandBufferFinished(it.m_finishCommandBuffer);
\t\tif (!commandBufferFinished)
\t\t\tbreak;
\t\tconst uint64 mappedResultValue = m_rendererVk->m_occlusionQueries.ptrQueryResults[it.queryIndex];
\t\tuint64 fragmentResult = mappedResultValue;
\t\tif (TargetDirectQueryReadbackEnabled())
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
\t\t\tconst uint64 n = ++s_targetDirectQueryReadbackCount;
\t\t\tconst bool valueMismatch = directResult == VK_SUCCESS && directResultValue != mappedResultValue;
\t\t\tif (directResult == VK_SUCCESS)
\t\t\t\tfragmentResult = directResultValue;
\t\t\tif (n <= 128 || (n % 1000ULL) == 0 || directResult != VK_SUCCESS || valueMismatch)
\t\t\t{
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[QUERY_DIRECT] n={} title={:016x} queryIndex={} cmdBuffer={} cmdFinished={} vkResult={} direct={} mapped={} selected={} mismatch={}",
\t\t\t\t\tn, CafeSystem::GetForegroundTitleId(), it.queryIndex, it.m_finishCommandBuffer, commandBufferFinished ? 1 : 0,
\t\t\t\t\tstatic_cast<sint32>(directResult), directResultValue, mappedResultValue, fragmentResult, valueMismatch ? 1 : 0);
\t\t\t}
\t\t}
\t\tm_acccumulatedSum += fragmentResult;
'''
query = replace_once(query, old_result_block, new_result_block, "target direct-readback result selection and completion trace")

for token in (
    "[QUERY_DIRECT]",
    "vkGetQueryPoolResults(",
    "TargetDirectQueryReadbackEnabled()",
    "0x00050000101AFF00ULL",
    "0x000500001011B900ULL",
    "m_acccumulatedSum += fragmentResult;",
    "valueMismatch",
    "cmdBuffer={} cmdFinished={}",
    "const bool commandBufferFinished = m_rendererVk->HasCommandBufferFinished(it.m_finishCommandBuffer);",
):
    if token not in query:
        raise RuntimeError(f"target direct-readback token missing: {token}")

if "m_acccumulatedSum += m_rendererVk->m_occlusionQueries.ptrQueryResults[it.queryIndex];" in query:
    raise RuntimeError("old unconditional mapped-buffer accumulation path still present")
if "fragmentResult = directResultValue;" not in query:
    raise RuntimeError("runtime-PASS direct-readback result selection was lost")

query_path.write_text(query, encoding="utf-8", newline="\n")
print("Star Fox Zero + Bayonetta 2 direct-readback PASS path preserved; mapped/direct divergence metadata installed")
