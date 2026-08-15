from pathlib import Path
import re


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8", newline="\n")


# Keep the grouped compatibility behavior already validated on this device.
swap = "src/Cafe/HW/Latte/Renderer/Vulkan/SwapchainInfoVk.cpp"
s = read(swap)
old = "colorAttachment.loadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;"
new = "colorAttachment.loadOp = VK_ATTACHMENT_LOAD_OP_LOAD;"
if s.count(old) != 1:
    raise RuntimeError(f"Expected 1 swapchain loadOp, found {s.count(old)}")
s = s.replace(old, new)
write(swap, s)

vr = "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp"
v = read(vr)
old_flag = "beginInfo.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;"
new_flag = "beginInfo.flags = VK_COMMAND_BUFFER_USAGE_SIMULTANEOUS_USE_BIT;"
if v.count(old_flag) != 2:
    raise RuntimeError(f"Expected 2 ONE_TIME_SUBMIT flags, found {v.count(old_flag)}")
v = v.replace(old_flag, new_flag)

anchor = "LatteTextureViewVk* texViewVk = (LatteTextureViewVk*)texView;\n\tdraw_endRenderPass();\n"
if v.count(anchor) != 1:
    raise RuntimeError(f"Expected DrawBackbufferQuad anchor once, found {v.count(anchor)}")
v = v.replace(anchor, anchor + "\n\tif (clearBackground)\n\t\tClearColorbuffer(padView);\n", 1)

clear_pattern = re.compile(
    r"\n\tif \(clearBackground\)\n\t\{\n\t\tVkClearAttachment clearAttachment\{\};.*?\n\t\}\n\n\tvkCmdBindPipeline",
    re.S,
)
v, n = clear_pattern.subn("\n\tvkCmdBindPipeline", v, count=1)
if n != 1:
    raise RuntimeError(f"Expected 1 vkCmdClearAttachments block, found {n}")

# PipelineInfo retains a thread-safe marker when vkCreateGraphicsPipelines fails.
vrh = "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h"
h = read(vrh)
h_anchor = "\tbool neverSkipAccurateBarrier{false};"
if h.count(h_anchor) != 1:
    raise RuntimeError(f"PipelineInfo anchor count={h.count(h_anchor)}")
h = h.replace(
    h_anchor,
    h_anchor
    + "\n\n\t// Adreno diagnostic: correlate pipeline creation failures with skipped draws"
    + "\n\tstd::atomic_bool diagCompileFailed{false};"
    + "\n\tstd::atomic_bool diagFailureDrawLogged{false};",
    1,
)
write(vrh, h)

# Keep a pointer to the PipelineInfo associated with the Vk pipeline being compiled.
pch = "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"
ph = read(pch)
ph_anchor = "\tbool m_requestRobustBufferAccess{false};"
if ph.count(ph_anchor) != 1:
    raise RuntimeError(f"PipelineCompiler header anchor count={ph.count(ph_anchor)}")
ph = ph.replace(ph_anchor, ph_anchor + "\n\tPipelineInfo* m_diagPipelineInfo{};", 1)
write(pch, ph)

pc = "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp"
p = read(pc)
assign_anchor = "\tm_requestRobustBufferAccess = requireRobustBufferAccess;"
if p.count(assign_anchor) != 1:
    raise RuntimeError(f"PipelineCompiler assignment anchor count={p.count(assign_anchor)}")
p = p.replace(assign_anchor, assign_anchor + "\n\tm_diagPipelineInfo = pipelineInfo;", 1)

old_fail = '''\telse
\t{
\t\tcemuLog_log(LogType::Force, "Failed to create graphics pipeline. Error {}", (sint32)result);
\t\tcemu_assert_debug(false);
\t\treturn true; // true indicates that caller should no longer attempt to compile this pipeline again
\t}'''
if p.count(old_fail) != 1:
    raise RuntimeError(f"Pipeline failure block count={p.count(old_fail)}")

new_fail = '''\telse
\t{
\t\tif (m_diagPipelineInfo)
\t\t{
\t\t\tm_diagPipelineInfo->diagCompileFailed.store(true, std::memory_order_relaxed);
\t\t\tconst uint64 vsHash = m_diagPipelineInfo->vertexShader ? m_diagPipelineInfo->vertexShader->baseHash : 0;
\t\t\tconst uint64 psHash = m_diagPipelineInfo->pixelShader ? m_diagPipelineInfo->pixelShader->baseHash : 0;
\t\t\tconst uint64 gsHash = m_diagPipelineInfo->geometryShader ? m_diagPipelineInfo->geometryShader->baseHash : 0;
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[ADRENO_DIAG] PIPELINE_FAIL state={:016x} min={:016x} result={} vs={:016x} ps={:016x} gs={:016x} prim={} topology={} stages={} attrs={} bindings={} cull={} front={} polygon={} depthTest={} depthWrite={} depthCompare={} blendAttachments={} samples={} robust={}",
\t\t\t\tm_diagPipelineInfo->stateHash, m_diagPipelineInfo->minimalStateHash, (sint32)result,
\t\t\t\tvsHash, psHash, gsHash, (uint32)m_diagPipelineInfo->primitiveMode, (uint32)inputAssembly.topology,
\t\t\t\tshaderStages.size(), vertexInputAttributeDescription.size(), vertexInputBindingDescription.size(),
\t\t\t\t(uint32)rasterizer.cullMode, (uint32)rasterizer.frontFace, (uint32)rasterizer.polygonMode,
\t\t\t\t(uint32)depthStencilState.depthTestEnable, (uint32)depthStencilState.depthWriteEnable, (uint32)depthStencilState.depthCompareOp,
\t\t\t\tcolorBlending.attachmentCount, (uint32)multisampling.rasterizationSamples, (uint32)m_requestRobustBufferAccess);
\t\t\tfor (const auto& attr : vertexInputAttributeDescription)
\t\t\t{
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[ADRENO_DIAG] ATTR state={:016x} loc={} bind={} format={} offset={}",
\t\t\t\t\tm_diagPipelineInfo->stateHash, attr.location, attr.binding, (uint32)attr.format, attr.offset);
\t\t\t}
\t\t\tfor (uint32 i = 0; i < colorBlending.attachmentCount && i < colorBlendAttachments.size(); ++i)
\t\t\t{
\t\t\t\tconst auto& b = colorBlendAttachments[i];
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[ADRENO_DIAG] BLEND state={:016x} att={} enable={} srcC={} dstC={} opC={} srcA={} dstA={} opA={} mask={}",
\t\t\t\t\tm_diagPipelineInfo->stateHash, i, (uint32)b.blendEnable,
\t\t\t\t\t(uint32)b.srcColorBlendFactor, (uint32)b.dstColorBlendFactor, (uint32)b.colorBlendOp,
\t\t\t\t\t(uint32)b.srcAlphaBlendFactor, (uint32)b.dstAlphaBlendFactor, (uint32)b.alphaBlendOp, (uint32)b.colorWriteMask);
\t\t\t}
\t\t}
\t\telse
\t\t{
\t\t\tcemuLog_log(LogType::Force, "[ADRENO_DIAG] PIPELINE_FAIL state=unknown result={}", (sint32)result);
\t\t}
\t\tcemuLog_log(LogType::Force, "Failed to create graphics pipeline. Error {}", (sint32)result);
\t\tcemu_assert_debug(false);
\t\treturn true; // true indicates that caller should no longer attempt to compile this pipeline again
\t}'''
p = p.replace(old_fail, new_fail, 1)
write(pc, p)

# Both regular draw paths return early on a null VkPipeline. Log only when
# that null handle is known to be the result of an actual compile failure.
null_pattern = re.compile(r"if \(vkObjPipeline->GetPipeline\(\) == VK_NULL_HANDLE\)\n\t\{")
matches = list(null_pattern.finditer(v))
if len(matches) != 2:
    raise RuntimeError(f"Expected 2 null-pipeline draw checks, found {len(matches)}")

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
v, n = null_pattern.subn(diag_head, v)
if n != 2:
    raise RuntimeError(f"Null-pipeline replacement count={n}")
write(vr, v)

print("Diagnostic patch applied successfully")
