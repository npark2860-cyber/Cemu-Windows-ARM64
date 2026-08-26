from pathlib import Path


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8", newline="\n")


# Keep the PipelineInfo associated with a pipeline compiler so failure logs can
# include state hashes and guest shader hashes. Logging is runtime-gated by
# CEMU_EXPERIMENTS=pipeline-diag and has no effect when the switch is absent.
h_path = "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"
h = read(h_path)
h_anchor = "\tbool m_requestRobustBufferAccess{false};"
if h.count(h_anchor) != 1:
    raise RuntimeError(f"PipelineCompiler header anchor count={h.count(h_anchor)}")
h = h.replace(h_anchor, h_anchor + "\n\tPipelineInfo* m_diagPipelineInfo{};", 1)
write(h_path, h)

cpp_path = "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp"
p = read(cpp_path)
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
\t\tif (RuntimeExperiments::Enabled("pipeline-diag") && m_diagPipelineInfo)
\t\t{
\t\t\tconst uint64 vsHash = m_diagPipelineInfo->vertexShader ? m_diagPipelineInfo->vertexShader->baseHash : 0;
\t\t\tconst uint64 psHash = m_diagPipelineInfo->pixelShader ? m_diagPipelineInfo->pixelShader->baseHash : 0;
\t\t\tconst uint64 gsHash = m_diagPipelineInfo->geometryShader ? m_diagPipelineInfo->geometryShader->baseHash : 0;
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[ADRENO_DIAG] PIPELINE_FAIL state={:016x} min={:016x} result={} vs={:016x} ps={:016x} gs={:016x} prim={} topology={} stages={} attrs={} bindings={} cull={} front={} polygon={} depthClamp={} depthTest={} depthWrite={} depthCompare={} blendAttachments={} samples={} robust={} pnext={} rasterPnext={}",
\t\t\t\tm_diagPipelineInfo->stateHash, m_diagPipelineInfo->minimalStateHash, (sint32)result,
\t\t\t\tvsHash, psHash, gsHash, (uint32)m_diagPipelineInfo->primitiveMode, (uint32)inputAssembly.topology,
\t\t\t\tshaderStages.size(), vertexInputAttributeDescription.size(), vertexInputBindingDescription.size(),
\t\t\t\t(uint32)rasterizer.cullMode, (uint32)rasterizer.frontFace, (uint32)rasterizer.polygonMode, (uint32)rasterizer.depthClampEnable,
\t\t\t\t(uint32)depthStencilState.depthTestEnable, (uint32)depthStencilState.depthWriteEnable, (uint32)depthStencilState.depthCompareOp,
\t\t\t\tcolorBlending.attachmentCount, (uint32)multisampling.rasterizationSamples, (uint32)m_requestRobustBufferAccess,
\t\t\t\tpipelineInfo.pNext ? 1u : 0u, rasterizer.pNext ? 1u : 0u);
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[ADRENO_DIAG] RT_FORMATS state={:016x} c0={} c1={} c2={} c3={} c4={} c5={} c6={} c7={} depth={}",
\t\t\t\tm_diagPipelineInfo->stateHash,
\t\t\t\t(uint32)m_renderPassObj->GetColorFormat(0), (uint32)m_renderPassObj->GetColorFormat(1),
\t\t\t\t(uint32)m_renderPassObj->GetColorFormat(2), (uint32)m_renderPassObj->GetColorFormat(3),
\t\t\t\t(uint32)m_renderPassObj->GetColorFormat(4), (uint32)m_renderPassObj->GetColorFormat(5),
\t\t\t\t(uint32)m_renderPassObj->GetColorFormat(6), (uint32)m_renderPassObj->GetColorFormat(7),
\t\t\t\t(uint32)m_renderPassObj->GetDepthFormat());
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
\t\tcemuLog_log(LogType::Force, "Failed to create graphics pipeline. Error {}", (sint32)result);
\t\tcemu_assert_debug(false);
\t\treturn true; // true indicates that caller should no longer attempt to compile this pipeline again
\t}'''

p = p.replace(old_fail, new_fail, 1)
write(cpp_path, p)
print("Runtime-gated pipeline diagnostics installed")

# Generic ARM64 Diagnostic Edition: UI-controlled observation-only extensions.
import subprocess
for script in (
    "tools/diagnostics/Apply-DiagnosticUI.py",
    "tools/diagnostics/Apply-DiagnosticPerformance.py",
    "tools/diagnostics/Apply-DiagnosticVulkan.py",
    "tools/diagnostics/Apply-DiagnosticArm64.py",
    "tools/diagnostics/Verify-DiagnosticCoverage.py",
):
    print(f"[diagnostic-edition] applying {script}")
    subprocess.run(["python", script], check=True)
