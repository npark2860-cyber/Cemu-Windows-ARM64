from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# Preserve the runtime-PASS direct-readback behavior for Star Fox Zero JP and
# Bayonetta 2 JP. For those targets only, isolate vkCmdCopyQueryPoolResults from
# HOST_VISIBLE memory by copying query results into a DEVICE_LOCAL intermediate
# buffer first, then vkCmdCopyBuffer into the existing mapped host buffer.

api_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanAPI.h")
api = api_path.read_text(encoding="utf-8")
api_anchor = "VKFUNC_DEVICE(vkCmdCopyQueryPoolResults);\n"
api_get_query_results = "VKFUNC_DEVICE(vkGetQueryPoolResults);\n"
api_count = api.count(api_get_query_results)
if api_count == 0:
    api = replace_once(api, api_anchor, api_anchor + api_get_query_results, "Vulkan query direct-readback loader")
elif api_count != 1:
    raise RuntimeError(f"vkGetQueryPoolResults loader expected at most once, found {api_count}")
if "VKFUNC_DEVICE(vkCmdCopyBuffer);" not in api:
    raise RuntimeError("vkCmdCopyBuffer loader missing")
api_path.write_text(api, encoding="utf-8", newline="\n")

# Add an 8 KiB DEVICE_LOCAL intermediate buffer alongside the existing mapped
# query-result buffer. The original mapped buffer remains the CPU-read target.
header_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h")
header = header_path.read_text(encoding="utf-8")
old_query_fields = '''\t\tVkBuffer bufferQueryResults;\n\t\tVkDeviceMemory memoryQueryResults;\n\t\tuint64* ptrQueryResults;\n'''
new_query_fields = '''\t\tVkBuffer bufferQueryResults;\n\t\tVkDeviceMemory memoryQueryResults;\n\t\tVkBuffer bufferQueryResultsIntermediate;\n\t\tVkDeviceMemory memoryQueryResultsIntermediate;\n\t\tuint64* ptrQueryResults;\n'''
header = replace_once(header, old_query_fields, new_query_fields, "query intermediate buffer fields")
header_path.write_text(header, encoding="utf-8", newline="\n")

renderer_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
renderer = renderer_path.read_text(encoding="utf-8")
old_allocation = '''\t// occlusion query result buffer\n\tif (!memoryManager->CreateBuffer(OCCLUSION_QUERY_POOL_SIZE * sizeof(uint64), VK_BUFFER_USAGE_TRANSFER_DST_BIT, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT | VK_MEMORY_PROPERTY_HOST_CACHED_BIT, m_occlusionQueries.bufferQueryResults, m_occlusionQueries.memoryQueryResults))\n\t{\n\t\tmemoryManager->CreateBuffer(OCCLUSION_QUERY_POOL_SIZE * sizeof(uint64), VK_BUFFER_USAGE_TRANSFER_DST_BIT, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT | VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_CACHED_BIT, m_occlusionQueries.bufferQueryResults, m_occlusionQueries.memoryQueryResults);\n\t}\n\tbufferPtr = nullptr;\n'''
new_allocation = '''\t// occlusion query result buffer\n\tconst VkMemoryPropertyFlags queryResultPrimaryProperties = VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT | VK_MEMORY_PROPERTY_HOST_CACHED_BIT;\n\tconst VkMemoryPropertyFlags queryResultFallbackProperties = VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT | VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_CACHED_BIT;\n\tVkMemoryPropertyFlags queryResultRequestedProperties = queryResultPrimaryProperties;\n\tbool queryResultFallback = false;\n\tif (!memoryManager->CreateBuffer(OCCLUSION_QUERY_POOL_SIZE * sizeof(uint64), VK_BUFFER_USAGE_TRANSFER_DST_BIT, queryResultPrimaryProperties, m_occlusionQueries.bufferQueryResults, m_occlusionQueries.memoryQueryResults))\n\t{\n\t\tqueryResultFallback = true;\n\t\tqueryResultRequestedProperties = queryResultFallbackProperties;\n\t\tmemoryManager->CreateBuffer(OCCLUSION_QUERY_POOL_SIZE * sizeof(uint64), VK_BUFFER_USAGE_TRANSFER_DST_BIT, queryResultFallbackProperties, m_occlusionQueries.bufferQueryResults, m_occlusionQueries.memoryQueryResults);\n\t}\n\tVkMemoryRequirements queryResultMemoryRequirements{};\n\tvkGetBufferMemoryRequirements(m_logicalDevice, m_occlusionQueries.bufferQueryResults, &queryResultMemoryRequirements);\n\tuint32 queryResultMemoryTypeIndex = 0xFFFFFFFFu;\n\tconst bool queryResultMemoryTypeFound = memoryManager->FindMemoryType(queryResultMemoryRequirements.memoryTypeBits, queryResultRequestedProperties, queryResultMemoryTypeIndex);\n\tVkPhysicalDeviceMemoryProperties queryResultMemoryProperties{};\n\tvkGetPhysicalDeviceMemoryProperties(m_physicalDevice, &queryResultMemoryProperties);\n\tVkMemoryPropertyFlags queryResultActualProperties = 0;\n\tuint32 queryResultHeapIndex = 0xFFFFFFFFu;\n\tif (queryResultMemoryTypeFound && queryResultMemoryTypeIndex < queryResultMemoryProperties.memoryTypeCount)\n\t{\n\t\tqueryResultActualProperties = queryResultMemoryProperties.memoryTypes[queryResultMemoryTypeIndex].propertyFlags;\n\t\tqueryResultHeapIndex = queryResultMemoryProperties.memoryTypes[queryResultMemoryTypeIndex].heapIndex;\n\t}\n\tcemuLog_log(LogType::Force,\n\t\t"[QUERY_MAP_META] found={} memoryType={} heap={} flags=0x{:08x} requested=0x{:08x} fallback={}",\n\t\tqueryResultMemoryTypeFound ? 1 : 0, queryResultMemoryTypeIndex, queryResultHeapIndex,\n\t\tstatic_cast<uint32>(queryResultActualProperties), static_cast<uint32>(queryResultRequestedProperties), queryResultFallback ? 1 : 0);\n\n\tif (!memoryManager->CreateBuffer(\n\t\tOCCLUSION_QUERY_POOL_SIZE * sizeof(uint64),\n\t\tVK_BUFFER_USAGE_TRANSFER_DST_BIT | VK_BUFFER_USAGE_TRANSFER_SRC_BIT,\n\t\tVK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,\n\t\tm_occlusionQueries.bufferQueryResultsIntermediate,\n\t\tm_occlusionQueries.memoryQueryResultsIntermediate))\n\t{\n\t\tthrow std::runtime_error("failed to allocate device-local query-result intermediate buffer");\n\t}\n\tcemuLog_log(LogType::Force, "[QUERY_INTERMEDIATE] allocated=1 size={}", OCCLUSION_QUERY_POOL_SIZE * sizeof(uint64));\n\tbufferPtr = nullptr;\n'''
renderer = replace_once(renderer, old_allocation, new_allocation, "query-result host + intermediate allocation")

old_cleanup = '''\tmemoryManager->DeleteBuffer(m_xfbRingBuffer, m_xfbRingBufferMemory);\n\tmemoryManager->DeleteBuffer(m_occlusionQueries.bufferQueryResults, m_occlusionQueries.memoryQueryResults);\n\tmemoryManager->DeleteBuffer(m_bufferCache, m_bufferCacheMemory);\n'''
new_cleanup = '''\tmemoryManager->DeleteBuffer(m_xfbRingBuffer, m_xfbRingBufferMemory);\n\tmemoryManager->DeleteBuffer(m_occlusionQueries.bufferQueryResults, m_occlusionQueries.memoryQueryResults);\n\tmemoryManager->DeleteBuffer(m_occlusionQueries.bufferQueryResultsIntermediate, m_occlusionQueries.memoryQueryResultsIntermediate);\n\tmemoryManager->DeleteBuffer(m_bufferCache, m_bufferCacheMemory);\n'''
renderer = replace_once(renderer, old_cleanup, new_cleanup, "query intermediate buffer cleanup")
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
helper = '''static uint64 s_targetDirectQueryReadbackCount = 0;\n\nstatic bool TargetDirectQueryReadbackEnabled()\n{\n\tconst uint64 titleId = CafeSystem::GetForegroundTitleId();\n\treturn titleId == 0x00050000101AFF00ULL || // Star Fox Zero JP\n\t\ttitleId == 0x000500001011B900ULL;   // Bayonetta 2 JP\n}\n\n'''
query = replace_once(query, get_result_anchor, helper + get_result_anchor, "target direct-readback helper")

old_copy_block = '''\tvkCmdCopyQueryPoolResults(m_rendererVk->m_state.currentCommandBuffer, m_rendererVk->m_occlusionQueries.queryPool, queryIndex, 1, m_rendererVk->m_occlusionQueries.bufferQueryResults, queryIndex * sizeof(uint64), 8, VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT);\n\tlist_queryFragments.back().m_finishCommandBuffer = m_rendererVk->GetCurrentCommandBufferId();\n'''
new_copy_block = '''\tconst VkDeviceSize queryResultOffset = static_cast<VkDeviceSize>(queryIndex) * sizeof(uint64);\n\tif (TargetDirectQueryReadbackEnabled())\n\t{\n\t\tvkCmdCopyQueryPoolResults(\n\t\t\tm_rendererVk->m_state.currentCommandBuffer,\n\t\t\tm_rendererVk->m_occlusionQueries.queryPool,\n\t\t\tqueryIndex, 1,\n\t\t\tm_rendererVk->m_occlusionQueries.bufferQueryResultsIntermediate,\n\t\t\tqueryResultOffset, sizeof(uint64),\n\t\t\tVK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT);\n\n\t\tVkBufferMemoryBarrier intermediateBarrier{};\n\t\tintermediateBarrier.sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER;\n\t\tintermediateBarrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;\n\t\tintermediateBarrier.dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT;\n\t\tintermediateBarrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;\n\t\tintermediateBarrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;\n\t\tintermediateBarrier.buffer = m_rendererVk->m_occlusionQueries.bufferQueryResultsIntermediate;\n\t\tintermediateBarrier.offset = queryResultOffset;\n\t\tintermediateBarrier.size = sizeof(uint64);\n\t\tvkCmdPipelineBarrier(\n\t\t\tm_rendererVk->m_state.currentCommandBuffer,\n\t\t\tVK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT, 0,\n\t\t\t0, nullptr, 1, &intermediateBarrier, 0, nullptr);\n\n\t\tVkBufferCopy queryCopyRegion{};\n\t\tqueryCopyRegion.srcOffset = queryResultOffset;\n\t\tqueryCopyRegion.dstOffset = queryResultOffset;\n\t\tqueryCopyRegion.size = sizeof(uint64);\n\t\tvkCmdCopyBuffer(\n\t\t\tm_rendererVk->m_state.currentCommandBuffer,\n\t\t\tm_rendererVk->m_occlusionQueries.bufferQueryResultsIntermediate,\n\t\t\tm_rendererVk->m_occlusionQueries.bufferQueryResults,\n\t\t\t1, &queryCopyRegion);\n\n\t\tVkBufferMemoryBarrier queryHostReadBarrier{};\n\t\tqueryHostReadBarrier.sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER;\n\t\tqueryHostReadBarrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;\n\t\tqueryHostReadBarrier.dstAccessMask = VK_ACCESS_HOST_READ_BIT;\n\t\tqueryHostReadBarrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;\n\t\tqueryHostReadBarrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;\n\t\tqueryHostReadBarrier.buffer = m_rendererVk->m_occlusionQueries.bufferQueryResults;\n\t\tqueryHostReadBarrier.offset = queryResultOffset;\n\t\tqueryHostReadBarrier.size = sizeof(uint64);\n\t\tvkCmdPipelineBarrier(\n\t\t\tm_rendererVk->m_state.currentCommandBuffer,\n\t\t\tVK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT, 0,\n\t\t\t0, nullptr, 1, &queryHostReadBarrier, 0, nullptr);\n\t}\n\telse\n\t{\n\t\tvkCmdCopyQueryPoolResults(\n\t\t\tm_rendererVk->m_state.currentCommandBuffer,\n\t\t\tm_rendererVk->m_occlusionQueries.queryPool,\n\t\t\tqueryIndex, 1,\n\t\t\tm_rendererVk->m_occlusionQueries.bufferQueryResults,\n\t\t\tqueryResultOffset, sizeof(uint64),\n\t\t\tVK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT);\n\t}\n\tlist_queryFragments.back().m_finishCommandBuffer = m_rendererVk->GetCurrentCommandBufferId();\n'''
query = replace_once(query, old_copy_block, new_copy_block, "device-local query intermediate copy path")

old_result_block = '''\t\tif (!m_rendererVk->HasCommandBufferFinished(it.m_finishCommandBuffer))\n\t\t\tbreak;\n\t\tm_acccumulatedSum += m_rendererVk->m_occlusionQueries.ptrQueryResults[it.queryIndex];\n'''
new_result_block = '''\t\tconst bool commandBufferFinished = m_rendererVk->HasCommandBufferFinished(it.m_finishCommandBuffer);\n\t\tif (!commandBufferFinished)\n\t\t\tbreak;\n\t\tconst uint64 mappedResultValue = m_rendererVk->m_occlusionQueries.ptrQueryResults[it.queryIndex];\n\t\tuint64 fragmentResult = mappedResultValue;\n\t\tif (TargetDirectQueryReadbackEnabled())\n\t\t{\n\t\t\tuint64 directResultValue = 0;\n\t\t\tconst VkResult directResult = vkGetQueryPoolResults(\n\t\t\t\tm_rendererVk->GetLogicalDevice(),\n\t\t\t\tm_rendererVk->m_occlusionQueries.queryPool,\n\t\t\t\tit.queryIndex, 1,\n\t\t\t\tsizeof(directResultValue), &directResultValue, sizeof(uint64),\n\t\t\t\tVK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT);\n\t\t\tconst uint64 n = ++s_targetDirectQueryReadbackCount;\n\t\t\tconst bool valueMismatch = directResult == VK_SUCCESS && directResultValue != mappedResultValue;\n\t\t\tif (directResult == VK_SUCCESS)\n\t\t\t\tfragmentResult = directResultValue;\n\t\t\tif (n <= 128 || (n % 1000ULL) == 0 || directResult != VK_SUCCESS || valueMismatch)\n\t\t\t{\n\t\t\t\tcemuLog_log(LogType::Force,\n\t\t\t\t\t"[QUERY_DIRECT] n={} title={:016x} queryIndex={} cmdBuffer={} cmdFinished={} path=intermediate vkResult={} direct={} mapped={} selected={} mismatch={}",\n\t\t\t\t\tn, CafeSystem::GetForegroundTitleId(), it.queryIndex, it.m_finishCommandBuffer, commandBufferFinished ? 1 : 0,\n\t\t\t\t\tstatic_cast<sint32>(directResult), directResultValue, mappedResultValue, fragmentResult, valueMismatch ? 1 : 0);\n\t\t\t}\n\t\t}\n\t\tm_acccumulatedSum += fragmentResult;\n'''
query = replace_once(query, old_result_block, new_result_block, "target direct-readback result selection")

for token in (
    "[QUERY_DIRECT]",
    "path=intermediate",
    "vkGetQueryPoolResults(",
    "vkCmdCopyBuffer(",
    "bufferQueryResultsIntermediate",
    "VK_ACCESS_TRANSFER_READ_BIT",
    "VK_ACCESS_HOST_READ_BIT",
    "0x00050000101AFF00ULL",
    "0x000500001011B900ULL",
    "m_acccumulatedSum += fragmentResult;",
):
    if token not in query:
        raise RuntimeError(f"query intermediate/direct-readback token missing: {token}")
if "vkInvalidateMappedMemoryRanges(" in query:
    raise RuntimeError("failed invalidate experiment leaked into intermediate-copy experiment")
if "fragmentResult = directResultValue;" not in query:
    raise RuntimeError("runtime-PASS direct-readback result selection was lost")

query_path.write_text(query, encoding="utf-8", newline="\n")

for path in (header_path, renderer_path, query_path):
    if "\\t" in path.read_text(encoding="utf-8"):
        pass

print("Star Fox Zero + Bayonetta 2 direct-readback PASS path preserved; DEVICE_LOCAL query intermediate -> host buffer copy experiment installed")
