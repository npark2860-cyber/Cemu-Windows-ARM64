from pathlib import Path


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8", newline="\n")


# Keep the PipelineInfo associated with a pipeline compiler so diagnostics can
# report pipeline state and guest shader association without changing behavior.
h_path = "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"
h = read(h_path)
h_anchor = "\tbool m_requestRobustBufferAccess{false};"
if h.count(h_anchor) != 1:
    raise RuntimeError(f"PipelineCompiler header anchor count={h.count(h_anchor)}")
h = h.replace(h_anchor, h_anchor + "\n\tPipelineInfo* m_diagPipelineInfo{};", 1)
write(h_path, h)

cpp_path = "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp"
p = read(cpp_path)

if '#include "diagnostics/RuntimeDiagnostics.h"\n' not in p:
    if '#include "diagnostics/RuntimeExperiments.h"\n' in p:
        p = p.replace('#include "diagnostics/RuntimeExperiments.h"\n', '#include "diagnostics/RuntimeExperiments.h"\n#include "diagnostics/RuntimeDiagnostics.h"\n', 1)
    else:
        include_anchor = '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"\n'
        if include_anchor not in p:
            raise RuntimeError("PipelineCompiler diagnostics include anchor not found")
        p = p.replace(include_anchor, include_anchor + '#include "diagnostics/RuntimeDiagnostics.h"\n', 1)

assign_anchor = "\tm_requestRobustBufferAccess = requireRobustBufferAccess;"
if p.count(assign_anchor) != 1:
    raise RuntimeError(f"PipelineCompiler assignment anchor count={p.count(assign_anchor)}")
p = p.replace(assign_anchor, assign_anchor + "\n\tm_diagPipelineInfo = pipelineInfo;", 1)

# Pipeline creation and stage diagnostics are sampled because pipeline creation
# can be a hot path. Each checkbox controls only its own log family.
compile_anchor = 'bool PipelineCompiler::Compile(bool forceCompile, bool isRenderThread, bool showInOverlay)\n{\n'
if p.count(compile_anchor) != 1:
    raise RuntimeError(f"Pipeline compile anchor count={p.count(compile_anchor)}")
compile_preamble = '''bool PipelineCompiler::Compile(bool forceCompile, bool isRenderThread, bool showInOverlay)
{
\tuint64_t diagPipelineSeq = 0;
\tbool diagPipelineSample = false;
\tconst bool diagPipelineCreate = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PipelineCreation);
\tconst bool diagVS = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ShaderVS);
\tconst bool diagPS = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ShaderPS);
\tconst bool diagGS = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ShaderGS);
\tif (m_diagPipelineInfo && (diagPipelineCreate || diagVS || diagPS || diagGS))
\t{
\t\tstatic std::atomic_uint64_t s_pipelineDiagSeq{0};
\t\tdiagPipelineSeq = s_pipelineDiagSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tdiagPipelineSample = diagPipelineSeq <= 100 || (diagPipelineSeq % 1000ULL) == 0;
\t\tif (diagPipelineSample)
\t\t{
\t\t\tif (diagPipelineCreate)
\t\t\t\tcemuLog_log(LogType::Force, "[PIPE_CREATE] BEGIN n={} state={:016x} min={:016x} force={} renderThread={}", diagPipelineSeq, m_diagPipelineInfo->stateHash, m_diagPipelineInfo->minimalStateHash, forceCompile ? 1 : 0, isRenderThread ? 1 : 0);
\t\t\tif (diagVS && m_diagPipelineInfo->vertexShader)
\t\t\t\tcemuLog_log(LogType::Force, "[SHADER_VS] n={} base={:016x} aux={:016x}", diagPipelineSeq, m_diagPipelineInfo->vertexShader->baseHash, m_diagPipelineInfo->vertexShader->auxHash);
\t\t\tif (diagPS && m_diagPipelineInfo->pixelShader)
\t\t\t\tcemuLog_log(LogType::Force, "[SHADER_PS] n={} base={:016x} aux={:016x}", diagPipelineSeq, m_diagPipelineInfo->pixelShader->baseHash, m_diagPipelineInfo->pixelShader->auxHash);
\t\t\tif (diagGS && m_diagPipelineInfo->geometryShader)
\t\t\t\tcemuLog_log(LogType::Force, "[SHADER_GS] n={} base={:016x} aux={:016x}", diagPipelineSeq, m_diagPipelineInfo->geometryShader->baseHash, m_diagPipelineInfo->geometryShader->auxHash);
\t\t}
\t}
'''
p = p.replace(compile_anchor, compile_preamble, 1)

success_old = '''\telse if (result == VK_SUCCESS)
\t{
\t\tm_vkrObjPipeline->SetPipeline(pipeline);
\t}'''
success_new = '''\telse if (result == VK_SUCCESS)
\t{
\t\tm_vkrObjPipeline->SetPipeline(pipeline);
\t\tif (diagPipelineCreate && diagPipelineSample && m_diagPipelineInfo)
\t\t\tcemuLog_log(LogType::Force, "[PIPE_CREATE] OK n={} state={:016x}", diagPipelineSeq, m_diagPipelineInfo->stateHash);
\t}'''
if p.count(success_old) != 1:
    raise RuntimeError(f"Pipeline success block count={p.count(success_old)}")
p = p.replace(success_old, success_new, 1)

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
\t\tconst bool legacyPipelineDiag = RuntimeExperiments::Enabled("pipeline-diag");
\t\tif (m_diagPipelineInfo)
\t\t{
\t\t\tconst uint64 vsHash = m_diagPipelineInfo->vertexShader ? m_diagPipelineInfo->vertexShader->baseHash : 0;
\t\t\tconst uint64 psHash = m_diagPipelineInfo->pixelShader ? m_diagPipelineInfo->pixelShader->baseHash : 0;
\t\t\tconst uint64 gsHash = m_diagPipelineInfo->geometryShader ? m_diagPipelineInfo->geometryShader->baseHash : 0;

\t\t\tif (legacyPipelineDiag || RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PipelineFailure))
\t\t\t{
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[ADRENO_DIAG] PIPELINE_FAIL state={:016x} min={:016x} result={}",
\t\t\t\t\tm_diagPipelineInfo->stateHash, m_diagPipelineInfo->minimalStateHash, (sint32)result);
\t\t\t}

\t\t\tif (legacyPipelineDiag || RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ShaderHashAssociation))
\t\t\t{
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[ADRENO_DIAG] SHADER_HASH state={:016x} vs={:016x} ps={:016x} gs={:016x}",
\t\t\t\t\tm_diagPipelineInfo->stateHash, vsHash, psHash, gsHash);
\t\t\t}

\t\t\tif (legacyPipelineDiag || RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PipelineStateSnapshot))
\t\t\t{
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[ADRENO_DIAG] PIPELINE_STATE state={:016x} prim={} topology={} stages={} attrs={} bindings={} cull={} front={} polygon={} depthClamp={} depthTest={} depthWrite={} depthCompare={} blendAttachments={} samples={} robust={} pnext={} rasterPnext={}",
\t\t\t\t\tm_diagPipelineInfo->stateHash, (uint32)m_diagPipelineInfo->primitiveMode, (uint32)inputAssembly.topology,
\t\t\t\t\tshaderStages.size(), vertexInputAttributeDescription.size(), vertexInputBindingDescription.size(),
\t\t\t\t\t(uint32)rasterizer.cullMode, (uint32)rasterizer.frontFace, (uint32)rasterizer.polygonMode, (uint32)rasterizer.depthClampEnable,
\t\t\t\t\t(uint32)depthStencilState.depthTestEnable, (uint32)depthStencilState.depthWriteEnable, (uint32)depthStencilState.depthCompareOp,
\t\t\t\t\tcolorBlending.attachmentCount, (uint32)multisampling.rasterizationSamples, (uint32)m_requestRobustBufferAccess,
\t\t\t\t\tpipelineInfo.pNext ? 1u : 0u, rasterizer.pNext ? 1u : 0u);
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[ADRENO_DIAG] RT_FORMATS state={:016x} c0={} c1={} c2={} c3={} c4={} c5={} c6={} c7={} depth={}",
\t\t\t\t\tm_diagPipelineInfo->stateHash,
\t\t\t\t\t(uint32)m_renderPassObj->GetColorFormat(0), (uint32)m_renderPassObj->GetColorFormat(1),
\t\t\t\t\t(uint32)m_renderPassObj->GetColorFormat(2), (uint32)m_renderPassObj->GetColorFormat(3),
\t\t\t\t\t(uint32)m_renderPassObj->GetColorFormat(4), (uint32)m_renderPassObj->GetColorFormat(5),
\t\t\t\t\t(uint32)m_renderPassObj->GetColorFormat(6), (uint32)m_renderPassObj->GetColorFormat(7),
\t\t\t\t\t(uint32)m_renderPassObj->GetDepthFormat());
\t\t\t\tfor (const auto& attr : vertexInputAttributeDescription)
\t\t\t\t{
\t\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\t"[ADRENO_DIAG] ATTR state={:016x} loc={} bind={} format={} offset={}",
\t\t\t\t\t\tm_diagPipelineInfo->stateHash, attr.location, attr.binding, (uint32)attr.format, attr.offset);
\t\t\t\t}
\t\t\t\tfor (uint32 i = 0; i < colorBlending.attachmentCount && i < colorBlendAttachments.size(); ++i)
\t\t\t\t{
\t\t\t\t\tconst auto& b = colorBlendAttachments[i];
\t\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\t"[ADRENO_DIAG] BLEND state={:016x} att={} enable={} srcC={} dstC={} opC={} srcA={} dstA={} opA={} mask={}",
\t\t\t\t\t\tm_diagPipelineInfo->stateHash, i, (uint32)b.blendEnable,
\t\t\t\t\t\t(uint32)b.srcColorBlendFactor, (uint32)b.dstColorBlendFactor, (uint32)b.colorBlendOp,
\t\t\t\t\t\t(uint32)b.srcAlphaBlendFactor, (uint32)b.dstAlphaBlendFactor, (uint32)b.alphaBlendOp, (uint32)b.colorWriteMask);
\t\t\t\t}
\t\t\t}
\t\t}
\t\tcemuLog_log(LogType::Force, "Failed to create graphics pipeline. Error {}", (sint32)result);
\t\tcemu_assert_debug(false);
\t\treturn true; // true indicates that caller should no longer attempt to compile this pipeline again
\t}'''

p = p.replace(old_fail, new_fail, 1)
write(cpp_path, p)
print("Independent runtime-gated pipeline diagnostics installed")

# Generic ARM64 Diagnostic Edition: UI-controlled observation-only extensions.
import subprocess
for script in (
    "tools/diagnostics/Apply-DiagnosticUI.py",
    "tools/diagnostics/Apply-DiagnosticPerformance.py",
    "tools/diagnostics/Apply-DiagnosticVulkan.py",
    "tools/diagnostics/Apply-DiagnosticArm64.py",
    "tools/diagnostics/Apply-SubmitLifetimeDiagnostics.py",
    "tools/diagnostics/Apply-ShaderFailureDiagnostics.py",
    "tools/diagnostics/Apply-RenderTargetFeedbackDiagnostics.py",
    "tools/diagnostics/Verify-DiagnosticCoverage.py",
):
    print(f"[diagnostic-edition] applying {script}")
    subprocess.run(["python", script], check=True)