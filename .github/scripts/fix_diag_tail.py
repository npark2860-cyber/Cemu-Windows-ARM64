from pathlib import Path

path = Path('.github/scripts/diag_adreno_patch.py')
s = path.read_text(encoding='utf-8')

# Replace the pipeline-failure diagnostic block with an automatic probe matrix.
# The probes only run for real runtime state hashes (not state=0 shader-cache warmup)
# and are capped so a single game launch cannot explode compile time.
start_marker = "new_fail = '''"
end_marker = "p = p.replace(old_fail, new_fail, 1)"
start = s.find(start_marker)
end = s.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError('Could not locate diagnostic failure block')

new_fail_block = r"""new_fail = '''\telse
\t{
\t\tif (m_diagPipelineInfo)
\t\t{
\t\t\tm_diagPipelineInfo->diagCompileFailed.store(true, std::memory_order_relaxed);
\t\t\tconst uint64 vsHash = m_diagPipelineInfo->vertexShader ? m_diagPipelineInfo->vertexShader->baseHash : 0;
\t\t\tconst uint64 psHash = m_diagPipelineInfo->pixelShader ? m_diagPipelineInfo->pixelShader->baseHash : 0;
\t\t\tconst uint64 gsHash = m_diagPipelineInfo->geometryShader ? m_diagPipelineInfo->geometryShader->baseHash : 0;
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\"[ADRENO_DIAG] PIPELINE_FAIL state={:016x} min={:016x} result={} vs={:016x} ps={:016x} gs={:016x} prim={} topology={} stages={} attrs={} bindings={} cull={} front={} polygon={} depthClamp={} depthTest={} depthWrite={} depthCompare={} blendAttachments={} samples={} robust={} pnext={} rasterPnext={}\",
\t\t\t\tm_diagPipelineInfo->stateHash, m_diagPipelineInfo->minimalStateHash, (sint32)result,
\t\t\t\tvsHash, psHash, gsHash, (uint32)m_diagPipelineInfo->primitiveMode, (uint32)inputAssembly.topology,
\t\t\t\tshaderStages.size(), vertexInputAttributeDescription.size(), vertexInputBindingDescription.size(),
\t\t\t\t(uint32)rasterizer.cullMode, (uint32)rasterizer.frontFace, (uint32)rasterizer.polygonMode, (uint32)rasterizer.depthClampEnable,
\t\t\t\t(uint32)depthStencilState.depthTestEnable, (uint32)depthStencilState.depthWriteEnable, (uint32)depthStencilState.depthCompareOp,
\t\t\t\tcolorBlending.attachmentCount, (uint32)multisampling.rasterizationSamples, (uint32)m_requestRobustBufferAccess,
\t\t\t\tpipelineInfo.pNext ? 1u : 0u, rasterizer.pNext ? 1u : 0u);
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\"[ADRENO_DIAG] RT_FORMATS state={:016x} c0={} c1={} c2={} c3={} c4={} c5={} c6={} c7={} depth={}\",
\t\t\t\tm_diagPipelineInfo->stateHash,
\t\t\t\t(uint32)m_renderPassObj->GetColorFormat(0), (uint32)m_renderPassObj->GetColorFormat(1),
\t\t\t\t(uint32)m_renderPassObj->GetColorFormat(2), (uint32)m_renderPassObj->GetColorFormat(3),
\t\t\t\t(uint32)m_renderPassObj->GetColorFormat(4), (uint32)m_renderPassObj->GetColorFormat(5),
\t\t\t\t(uint32)m_renderPassObj->GetColorFormat(6), (uint32)m_renderPassObj->GetColorFormat(7),
\t\t\t\t(uint32)m_renderPassObj->GetDepthFormat());
\t\t\tfor (const auto& attr : vertexInputAttributeDescription)
\t\t\t{
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\"[ADRENO_DIAG] ATTR state={:016x} loc={} bind={} format={} offset={}\",
\t\t\t\t\tm_diagPipelineInfo->stateHash, attr.location, attr.binding, (uint32)attr.format, attr.offset);
\t\t\t}
\t\t\tfor (uint32 i = 0; i < colorBlending.attachmentCount && i < colorBlendAttachments.size(); ++i)
\t\t\t{
\t\t\t\tconst auto& b = colorBlendAttachments[i];
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\"[ADRENO_DIAG] BLEND state={:016x} att={} enable={} srcC={} dstC={} opC={} srcA={} dstA={} opA={} mask={}\",
\t\t\t\t\tm_diagPipelineInfo->stateHash, i, (uint32)b.blendEnable,
\t\t\t\t\t(uint32)b.srcColorBlendFactor, (uint32)b.dstColorBlendFactor, (uint32)b.colorBlendOp,
\t\t\t\t\t(uint32)b.srcAlphaBlendFactor, (uint32)b.dstAlphaBlendFactor, (uint32)b.alphaBlendOp, (uint32)b.colorWriteMask);
\t\t\t}

\t\t\tif (m_diagPipelineInfo->stateHash != 0)
\t\t\t{
\t\t\t\tstatic std::atomic_uint32_t s_adrenoProbeFailureCount{0};
\t\t\t\tconst uint32 probeIndex = s_adrenoProbeFailureCount.fetch_add(1, std::memory_order_relaxed);
\t\t\t\tif (probeIndex < 16)
\t\t\t\t{
\t\t\t\t\tauto runProbe = [&](const char* label, VkGraphicsPipelineCreateInfo& probeInfo, VkPipelineCache cache) -> VkResult
\t\t\t\t\t{
\t\t\t\t\t\tVkPipeline probePipeline = VK_NULL_HANDLE;
\t\t\t\t\t\tVkResult probeResult;
\t\t\t\t\t\t{
\t\t\t\t\t\t\tstd::shared_lock probeLock(vkRenderer->m_pipeline_cache_save_mutex);
\t\t\t\t\t\t\tprobeResult = vkCreateGraphicsPipelines(vkRenderer->m_logicalDevice, cache, 1, &probeInfo, nullptr, &probePipeline);
\t\t\t\t\t\t}
\t\t\t\t\t\tif (probePipeline != VK_NULL_HANDLE)
\t\t\t\t\t\t\tvkDestroyPipeline(vkRenderer->m_logicalDevice, probePipeline, nullptr);
\t\t\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\t\t\"[ADRENO_PROBE] state={:016x} probe={} result={}\",
\t\t\t\t\t\t\tm_diagPipelineInfo->stateHash, label, (sint32)probeResult);
\t\t\t\t\t\treturn probeResult;
\t\t\t\t\t};

\t\t\t\t\t{
\t\t\t\t\t\tauto probeInfo = pipelineInfo;
\t\t\t\t\t\trunProbe(\"NO_CACHE\", probeInfo, VK_NULL_HANDLE);
\t\t\t\t\t}
\t\t\t\t\t{
\t\t\t\t\t\tauto probeInfo = pipelineInfo;
\t\t\t\t\t\tprobeInfo.pNext = nullptr;
\t\t\t\t\t\trunProbe(\"NO_PNEXT\", probeInfo, vkRenderer->m_pipeline_cache);
\t\t\t\t\t}
\t\t\t\t\tif (vkRenderer->m_featureControl.deviceExtensions.pipeline_feedback)
\t\t\t\t\t{
\t\t\t\t\t\tauto probeInfo = pipelineInfo;
\t\t\t\t\t\tauto feedbackOnly = creationFeedbackInfo;
\t\t\t\t\t\tfeedbackOnly.pNext = nullptr;
\t\t\t\t\t\tprobeInfo.pNext = &feedbackOnly;
\t\t\t\t\t\trunProbe(\"FEEDBACK_ONLY\", probeInfo, vkRenderer->m_pipeline_cache);
\t\t\t\t\t}
\t\t\t\t\tif (vkRenderer->m_featureControl.deviceExtensions.pipeline_robustness && m_requestRobustBufferAccess)
\t\t\t\t\t{
\t\t\t\t\t\tauto probeInfo = pipelineInfo;
\t\t\t\t\t\tauto robustOnly = pipelineRobustnessCreateInfo;
\t\t\t\t\t\trobustOnly.pNext = nullptr;
\t\t\t\t\t\tprobeInfo.pNext = &robustOnly;
\t\t\t\t\t\trunProbe(\"ROBUST_ONLY\", probeInfo, vkRenderer->m_pipeline_cache);
\t\t\t\t\t}
\t\t\t\t\t{
\t\t\t\t\t\tauto probeInfo = pipelineInfo;
\t\t\t\t\t\tauto probeRaster = rasterizer;
\t\t\t\t\t\tprobeRaster.pNext = nullptr;
\t\t\t\t\t\tprobeInfo.pRasterizationState = &probeRaster;
\t\t\t\t\t\trunProbe(\"RASTER_NO_PNEXT\", probeInfo, vkRenderer->m_pipeline_cache);
\t\t\t\t\t}
\t\t\t\t\t{
\t\t\t\t\t\tauto probeInfo = pipelineInfo;
\t\t\t\t\t\tauto probeRaster = rasterizer;
\t\t\t\t\t\tprobeRaster.depthClampEnable = VK_FALSE;
\t\t\t\t\t\tprobeInfo.pRasterizationState = &probeRaster;
\t\t\t\t\t\trunProbe(\"DEPTH_CLAMP_OFF\", probeInfo, vkRenderer->m_pipeline_cache);
\t\t\t\t\t}
\t\t\t\t\t{
\t\t\t\t\t\tauto probeInfo = pipelineInfo;
\t\t\t\t\t\tauto probeDepth = depthStencilState;
\t\t\t\t\t\tprobeDepth.depthTestEnable = VK_FALSE;
\t\t\t\t\t\tprobeDepth.depthWriteEnable = VK_FALSE;
\t\t\t\t\t\tprobeDepth.depthBoundsTestEnable = VK_FALSE;
\t\t\t\t\t\tprobeDepth.stencilTestEnable = VK_FALSE;
\t\t\t\t\t\tprobeDepth.depthCompareOp = VK_COMPARE_OP_ALWAYS;
\t\t\t\t\t\tprobeInfo.pDepthStencilState = &probeDepth;
\t\t\t\t\t\trunProbe(\"DEPTH_OFF\", probeInfo, vkRenderer->m_pipeline_cache);
\t\t\t\t\t}
\t\t\t\t\t{
\t\t\t\t\t\tauto probeInfo = pipelineInfo;
\t\t\t\t\t\tauto probeAttachments = colorBlendAttachments;
\t\t\t\t\t\tfor (auto& b : probeAttachments)
\t\t\t\t\t\t{
\t\t\t\t\t\t\tb.blendEnable = VK_FALSE;
\t\t\t\t\t\t\tb.srcColorBlendFactor = VK_BLEND_FACTOR_ONE;
\t\t\t\t\t\t\tb.dstColorBlendFactor = VK_BLEND_FACTOR_ZERO;
\t\t\t\t\t\t\tb.colorBlendOp = VK_BLEND_OP_ADD;
\t\t\t\t\t\t\tb.srcAlphaBlendFactor = VK_BLEND_FACTOR_ONE;
\t\t\t\t\t\t\tb.dstAlphaBlendFactor = VK_BLEND_FACTOR_ZERO;
\t\t\t\t\t\t\tb.alphaBlendOp = VK_BLEND_OP_ADD;
\t\t\t\t\t\t}
\t\t\t\t\t\tauto probeBlend = colorBlending;
\t\t\t\t\t\tprobeBlend.logicOpEnable = VK_FALSE;
\t\t\t\t\t\tprobeBlend.logicOp = VK_LOGIC_OP_COPY;
\t\t\t\t\t\tprobeBlend.pAttachments = probeAttachments.data();
\t\t\t\t\t\tprobeInfo.pColorBlendState = &probeBlend;
\t\t\t\t\t\trunProbe(\"BLEND_CANON\", probeInfo, vkRenderer->m_pipeline_cache);
\t\t\t\t\t}
\t\t\t\t\t{
\t\t\t\t\t\tauto probeInfo = pipelineInfo;
\t\t\t\t\t\tauto probeVertex = vertexInputInfo;
\t\t\t\t\t\tprobeVertex.vertexBindingDescriptionCount = 0;
\t\t\t\t\t\tprobeVertex.pVertexBindingDescriptions = nullptr;
\t\t\t\t\t\tprobeVertex.vertexAttributeDescriptionCount = 0;
\t\t\t\t\t\tprobeVertex.pVertexAttributeDescriptions = nullptr;
\t\t\t\t\t\tprobeInfo.pVertexInputState = &probeVertex;
\t\t\t\t\t\trunProbe(\"VERTEX_NONE\", probeInfo, vkRenderer->m_pipeline_cache);
\t\t\t\t\t}
\t\t\t\t\tif (shaderStages.size() >= 2 && m_vkGeometryShader == nullptr && m_rectEmulationGS == nullptr)
\t\t\t\t\t{
\t\t\t\t\t\tauto probeInfo = pipelineInfo;
\t\t\t\t\t\tauto probeRaster = rasterizer;
\t\t\t\t\t\tprobeRaster.rasterizerDiscardEnable = VK_TRUE;
\t\t\t\t\t\tprobeRaster.pNext = nullptr;
\t\t\t\t\t\tprobeInfo.stageCount = 1;
\t\t\t\t\t\tprobeInfo.pRasterizationState = &probeRaster;
\t\t\t\t\t\tprobeInfo.pColorBlendState = nullptr;
\t\t\t\t\t\tprobeInfo.pDepthStencilState = nullptr;
\t\t\t\t\t\trunProbe(\"VS_ONLY_DISCARD\", probeInfo, vkRenderer->m_pipeline_cache);
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t}
\t\telse
\t\t{
\t\t\tcemuLog_log(LogType::Force, \"[ADRENO_DIAG] PIPELINE_FAIL state=unknown result={}\", (sint32)result);
\t\t}
\t\tcemuLog_log(LogType::Force, \"Failed to create graphics pipeline. Error {}\", (sint32)result);
\t\tcemu_assert_debug(false);
\t\treturn true; // true indicates that caller should no longer attempt to compile this pipeline again
\t}'''
"""

s = s[:start] + new_fail_block + s[end:]

# Fix the draw-path instrumentation target. The two null-pipeline checks live in
# VulkanRendererCore.cpp, not VulkanRenderer.cpp.
marker = '# Both regular draw paths return early on a null VkPipeline.'
idx = s.find(marker)
if idx < 0:
    raise RuntimeError('Diagnostic tail marker not found')

prefix = s[:idx]
tail = r"""# Persist the compatibility changes made in VulkanRenderer.cpp.
write(vr, v)

# Both regular draw paths live in VulkanRendererCore.cpp, not VulkanRenderer.cpp.
# Log only null handles that came from an actual vkCreateGraphicsPipelines failure.
core = "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp"
c = read(core)
null_head = "if (vkObjPipeline->GetPipeline() == VK_NULL_HANDLE)\n\t{"
if c.count(null_head) != 2:
    raise RuntimeError(f"Expected 2 null-pipeline draw checks in VulkanRendererCore.cpp, found {c.count(null_head)}")

diag_head = '''if (vkObjPipeline->GetPipeline() == VK_NULL_HANDLE)
\t{
\t\tif (pipeline_info->diagCompileFailed.load(std::memory_order_relaxed) &&
\t\t\t!pipeline_info->diagFailureDrawLogged.exchange(true, std::memory_order_relaxed))
\t\t{
\t\t\tconst uint64 vsHash = pipeline_info->vertexShader ? pipeline_info->vertexShader->baseHash : 0;
\t\t\tconst uint64 psHash = pipeline_info->pixelShader ? pipeline_info->pixelShader->baseHash : 0;
\t\t\tconst uint64 gsHash = pipeline_info->geometryShader ? pipeline_info->geometryShader->baseHash : 0;
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[ADRENO_DIAG] FAILED_PIPELINE_DRAW_SKIPPED state={:016x} min={:016x} vs={:016x} ps={:016x} gs={:016x} prim={}",
\t\t\t\tpipeline_info->stateHash, pipeline_info->minimalStateHash, vsHash, psHash, gsHash, (uint32)pipeline_info->primitiveMode);
\t\t}'''
c = c.replace(null_head, diag_head)
write(core, c)

print("Diagnostic patch applied successfully")
"""

path.write_text(prefix + tail, encoding='utf-8', newline='\n')
print('Diagnostic script upgraded with automatic Adreno probes')
