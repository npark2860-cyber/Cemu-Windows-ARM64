from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


def replace_count(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} anchors, found {count}")
    return text.replace(old, new)


p = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
t = p.read_text(encoding="utf-8")

stats_anchor = '''static uint64 s_rtStatLoadRAW = 0;

static bool RTExpEnabled(std::string_view name)
'''
stats_block = '''static uint64 s_rtStatLoadRAW = 0;

// Report-only Vulkan descriptor-path counters. The experiment changes no
// descriptor state or command ordering; it only counts existing operations.
static uint64 s_vkDescDraws = 0;
static uint64 s_vkDescLookups = 0;
static uint64 s_vkDescHits = 0;
static uint64 s_vkDescMisses = 0;
static uint64 s_vkDescAllocCalls = 0;
static uint64 s_vkDescUpdateCalls = 0;
static uint64 s_vkDescUpdateWrites = 0;
static uint64 s_vkDescBindCalls = 0;
static uint64 s_vkDescBindSets = 0;

static bool VkDescriptorStatsEnabled()
{
\tstatic const bool enabled = RuntimeExperiments::Enabled("vk-descriptor-stats");
\treturn enabled;
}

static void VkDescriptorStatsRecordBind(uint32 setCount)
{
\tif (!VkDescriptorStatsEnabled())
\t\treturn;
\t++s_vkDescBindCalls;
\ts_vkDescBindSets += setCount;
}

static void VkDescriptorStatsRecordDraw()
{
\tif (!VkDescriptorStatsEnabled())
\t\treturn;
\t++s_vkDescDraws;
\tif ((s_vkDescDraws % 50000ULL) != 0)
\t\treturn;
\tcemuLog_log(LogType::Force,
\t\t"[VK_DESCRIPTOR_STATS] draws={} lookups={} hits={} misses={} alloc_calls={} update_calls={} update_writes={} bind_calls={} bind_sets={}",
\t\ts_vkDescDraws, s_vkDescLookups, s_vkDescHits, s_vkDescMisses, s_vkDescAllocCalls,
\t\ts_vkDescUpdateCalls, s_vkDescUpdateWrites, s_vkDescBindCalls, s_vkDescBindSets);
}

static bool RTExpEnabled(std::string_view name)
'''
t = replace_once(t, stats_anchor, stats_block, "Vulkan descriptor stats state")

lookup_old = '''\tconst uint64 stateHash = GetDescriptorSetStateHash(shader);
\tcemu_assert_debug(shader->shaderType == LatteConst::ShaderType::Vertex || shader->shaderType == LatteConst::ShaderType::Pixel || shader->shaderType == LatteConst::ShaderType::Geometry);
\tauto& ds_cache = pipeline_info->GetDescriptorSetCache(shader->shaderType);
\tconst auto it = ds_cache.find(stateHash);
\tif (it != ds_cache.cend())
\t\treturn it->second;
'''
lookup_new = '''\tconst uint64 stateHash = GetDescriptorSetStateHash(shader);
\tcemu_assert_debug(shader->shaderType == LatteConst::ShaderType::Vertex || shader->shaderType == LatteConst::ShaderType::Pixel || shader->shaderType == LatteConst::ShaderType::Geometry);
\tauto& ds_cache = pipeline_info->GetDescriptorSetCache(shader->shaderType);
\tconst bool diagDescriptorStats = VkDescriptorStatsEnabled();
\tif (diagDescriptorStats)
\t\t++s_vkDescLookups;
\tconst auto it = ds_cache.find(stateHash);
\tif (it != ds_cache.cend())
\t{
\t\tif (diagDescriptorStats)
\t\t\t++s_vkDescHits;
\t\treturn it->second;
\t}
\tif (diagDescriptorStats)
\t\t++s_vkDescMisses;
'''
t = replace_once(t, lookup_old, lookup_new, "descriptor cache lookup")

alloc_old = '''\tvkObjDS->descriptorSet = result;

\tsint32 textureCount = shader->resourceMapping.getTextureCount();
'''
alloc_new = '''\tvkObjDS->descriptorSet = result;
\tif (diagDescriptorStats)
\t\t++s_vkDescAllocCalls;

\tsint32 textureCount = shader->resourceMapping.getTextureCount();
'''
t = replace_once(t, alloc_old, alloc_new, "descriptor allocation count")

update_old = '''\tif (!descriptorWrites.empty())
\t\tvkUpdateDescriptorSets(m_logicalDevice, (uint32)descriptorWrites.size(), descriptorWrites.data(), 0, nullptr);
'''
update_new = '''\tif (!descriptorWrites.empty())
\t{
\t\tif (diagDescriptorStats)
\t\t{
\t\t\t++s_vkDescUpdateCalls;
\t\t\ts_vkDescUpdateWrites += descriptorWrites.size();
\t\t}
\t\tvkUpdateDescriptorSets(m_logicalDevice, (uint32)descriptorWrites.size(), descriptorWrites.data(), 0, nullptr);
\t}
'''
t = replace_once(t, update_old, update_new, "descriptor update count")

bind2 = '''\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 0, 2, dsArray, numDynOffsetsVS + numDynOffsetsPS, dynamicOffsets);'''
t = replace_once(t, bind2, '\t\tVkDescriptorStatsRecordBind(2);\n' + bind2, "first draw combined descriptor bind")

bind_vertex = '''\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 0, 1, &vertexDS->m_vkObjDescriptorSet->descriptorSet, numDynOffsets, dynamicOffsets);'''
t = replace_once(t, bind_vertex, '\t\tVkDescriptorStatsRecordBind(1);\n' + bind_vertex, "first draw vertex descriptor bind")

bind_pixel = '''\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 1, 1, &pixelDS->m_vkObjDescriptorSet->descriptorSet, numDynOffsets, dynamicOffsets);'''
t = replace_once(t, bind_pixel, '\t\tVkDescriptorStatsRecordBind(1);\n' + bind_pixel, "first draw pixel descriptor bind")

bind_cont = '''\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, dsArrayBase, dsArraySize, dsArray, numDynOffsets, dynamicOffsets);'''
t = replace_once(t, bind_cont, '\t\tVkDescriptorStatsRecordBind((uint32)dsArraySize);\n' + bind_cont, "continued draw descriptor bind")

bind_geometry = '''\t\tvkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, vkObjPipeline->m_pipelineLayout, 2, 1, &geometryDS->m_vkObjDescriptorSet->descriptorSet, numDynOffsets, dynamicOffsets);'''
t = replace_count(t, bind_geometry, '\t\tVkDescriptorStatsRecordBind(1);\n' + bind_geometry, 2, "geometry descriptor binds")

draw_old = '''\tLatteGPUState.drawCallCounter++;
\tRTExpLogStatsMaybe();
}

// used in place of vertex/uniform caching when direct memory access is possible'''
draw_new = '''\tLatteGPUState.drawCallCounter++;
\tRTExpLogStatsMaybe();
\tVkDescriptorStatsRecordDraw();
}

// used in place of vertex/uniform caching when direct memory access is possible'''
t = replace_once(t, draw_old, draw_new, "descriptor draw report hook")

p.write_text(t, encoding="utf-8", newline="\n")
print("[vk-descriptor-stats] added report-only main draw descriptor counters")
