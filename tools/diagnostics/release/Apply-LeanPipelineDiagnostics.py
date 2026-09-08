from pathlib import Path

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)

def ensure_include(text, anchor, include_line, label):
    if include_line in text:
        return text
    return replace_once(text, anchor, anchor + include_line, label)

h_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h")
h = h_path.read_text(encoding="utf-8")
h = replace_once(
    h,
    "\tbool m_requestRobustBufferAccess{false};",
    "\tbool m_requestRobustBufferAccess{false};\n\tPipelineInfo* m_diagPipelineInfo{};",
    "PipelineCompiler header diagnostic pointer",
)
h_path.write_text(h, encoding="utf-8", newline="\n")

p_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp")
p = p_path.read_text(encoding="utf-8")
p = ensure_include(
    p,
    '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"\n',
    '#include "diagnostics/RuntimeDiagnostics.h"\n',
    "PipelineCompiler diagnostic include",
)
p = replace_once(
    p,
    "\tm_requestRobustBufferAccess = requireRobustBufferAccess;",
    "\tm_requestRobustBufferAccess = requireRobustBufferAccess;\n\tm_diagPipelineInfo = pipelineInfo;",
    "PipelineCompiler diagnostic state assignment",
)

compile_anchor = "bool PipelineCompiler::Compile(bool forceCompile, bool isRenderThread, bool showInOverlay)\n{\n"
compile_new = """bool PipelineCompiler::Compile(bool forceCompile, bool isRenderThread, bool showInOverlay)
{
\tRuntimeDiagnostics::ScopedPipelineCompile diagPipelineCompile;
\tuint64_t diagPipelineSeq = 0;
\tbool diagPipelineSample = false;
\tconst bool diagCreate = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PipelineCreation);
\tconst bool diagVS = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ShaderVS);
\tconst bool diagPS = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ShaderPS);
\tconst bool diagGS = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ShaderGS);
\tconst bool diagAux = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ShaderAuxHash);
\tif (m_diagPipelineInfo && (diagCreate || diagVS || diagPS || diagGS || diagAux))
\t{
\t\tstatic std::atomic_uint64_t s_diagPipelineSeq{0};
\t\tdiagPipelineSeq = s_diagPipelineSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tdiagPipelineSample = diagPipelineSeq <= 100 || (diagPipelineSeq % 1000ULL) == 0;
\t\tif (diagPipelineSample)
\t\t{
\t\t\tif (diagCreate)
\t\t\t\tcemuLog_log(LogType::Force, "[PIPE_CREATE] BEGIN n={} state={:016x} min={:016x} force={} renderThread={}", diagPipelineSeq, m_diagPipelineInfo->stateHash, m_diagPipelineInfo->minimalStateHash, forceCompile ? 1 : 0, isRenderThread ? 1 : 0);
\t\t\tif (diagVS && m_diagPipelineInfo->vertexShader)
\t\t\t\tcemuLog_log(LogType::Force, "[SHADER_VS] n={} base={:016x} aux={:016x}", diagPipelineSeq, m_diagPipelineInfo->vertexShader->baseHash, m_diagPipelineInfo->vertexShader->auxHash);
\t\t\tif (diagPS && m_diagPipelineInfo->pixelShader)
\t\t\t\tcemuLog_log(LogType::Force, "[SHADER_PS] n={} base={:016x} aux={:016x}", diagPipelineSeq, m_diagPipelineInfo->pixelShader->baseHash, m_diagPipelineInfo->pixelShader->auxHash);
\t\t\tif (diagGS && m_diagPipelineInfo->geometryShader)
\t\t\t\tcemuLog_log(LogType::Force, "[SHADER_GS] n={} base={:016x} aux={:016x}", diagPipelineSeq, m_diagPipelineInfo->geometryShader->baseHash, m_diagPipelineInfo->geometryShader->auxHash);
\t\t\tif (diagAux)
\t\t\t\tcemuLog_log(LogType::Force, "[SHADER_AUX] n={} vs={:016x} ps={:016x} gs={:016x}",
\t\t\t\t\tdiagPipelineSeq,
\t\t\t\t\tm_diagPipelineInfo->vertexShader ? m_diagPipelineInfo->vertexShader->auxHash : 0,
\t\t\t\t\tm_diagPipelineInfo->pixelShader ? m_diagPipelineInfo->pixelShader->auxHash : 0,
\t\t\t\t\tm_diagPipelineInfo->geometryShader ? m_diagPipelineInfo->geometryShader->auxHash : 0);
\t\t}
\t}
"""
p = replace_once(p, compile_anchor, compile_new, "PipelineCompiler compile diagnostics")

success_old = """\telse if (result == VK_SUCCESS)
\t{
\t\tm_vkrObjPipeline->SetPipeline(pipeline);
\t}"""
success_new = """\telse if (result == VK_SUCCESS)
\t{
\t\tm_vkrObjPipeline->SetPipeline(pipeline);
\t\tif (diagCreate && diagPipelineSample && m_diagPipelineInfo)
\t\t\tcemuLog_log(LogType::Force, "[PIPE_CREATE] OK n={} state={:016x}", diagPipelineSeq, m_diagPipelineInfo->stateHash);
\t}"""
p = replace_once(p, success_old, success_new, "PipelineCompiler success diagnostics")

fail_old = """\telse
\t{
\t\tcemuLog_log(LogType::Force, "Failed to create graphics pipeline. Error {}", (sint32)result);
\t\tcemu_assert_debug(false);
\t\treturn true; // true indicates that caller should no longer attempt to compile this pipeline again
\t}"""
fail_new = """\telse
\t{
\t\tif (m_diagPipelineInfo)
\t\t{
\t\t\tconst uint64 vsHash = m_diagPipelineInfo->vertexShader ? m_diagPipelineInfo->vertexShader->baseHash : 0;
\t\t\tconst uint64 psHash = m_diagPipelineInfo->pixelShader ? m_diagPipelineInfo->pixelShader->baseHash : 0;
\t\t\tconst uint64 gsHash = m_diagPipelineInfo->geometryShader ? m_diagPipelineInfo->geometryShader->baseHash : 0;
\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PipelineFailure))
\t\t\t\tcemuLog_log(LogType::Force, "[ADRENO_DIAG] PIPELINE_FAIL state={:016x} min={:016x} result={}", m_diagPipelineInfo->stateHash, m_diagPipelineInfo->minimalStateHash, (sint32)result);
\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ShaderHashAssociation))
\t\t\t\tcemuLog_log(LogType::Force, "[ADRENO_DIAG] SHADER_HASH state={:016x} vs={:016x} ps={:016x} gs={:016x}", m_diagPipelineInfo->stateHash, vsHash, psHash, gsHash);
\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PipelineStateSnapshot))
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
\t\t\t}
\t\t}
\t\tcemuLog_log(LogType::Force, "Failed to create graphics pipeline. Error {}", (sint32)result);
\t\tcemu_assert_debug(false);
\t\treturn true; // true indicates that caller should no longer attempt to compile this pipeline again
\t}"""
p = replace_once(p, fail_old, fail_new, "PipelineCompiler failure diagnostics")
p_path.write_text(p, encoding="utf-8", newline="\n")

core_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
core = core_path.read_text(encoding="utf-8")
core = ensure_include(
    core,
    '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"\n',
    '#include "diagnostics/RuntimeDiagnostics.h"\n',
    "VulkanRendererCore diagnostic include",
)

cache_anchor = """PipelineInfo* VulkanRenderer::draw_getCachedPipeline()
{
\t// todo - optimize m_pipeline_info_cache away and store directly in vk vertex shader
\tconst auto fetchShader = LatteSHRC_GetActiveFetchShader();
\tconst auto vertexShader = LatteSHRC_GetActiveVertexShader();
\tconst auto it = m_pipeline_info_cache.find(vertexShader->baseHash);
\tif (it == m_pipeline_info_cache.cend())
\t\treturn nullptr;
"""
cache_new = """PipelineInfo* VulkanRenderer::draw_getCachedPipeline()
{
\t// todo - optimize m_pipeline_info_cache away and store directly in vk vertex shader
\tconst auto fetchShader = LatteSHRC_GetActiveFetchShader();
\tconst auto vertexShader = LatteSHRC_GetActiveVertexShader();
\tconst bool diagPipelineCache = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PipelineCache);
\tconst auto it = m_pipeline_info_cache.find(vertexShader->baseHash);
\tif (it == m_pipeline_info_cache.cend())
\t{
\t\tif (diagPipelineCache)
\t\t\tcemuLog_log(LogType::Force, "[PIPE_CACHE] miss stage=vs-map vs={:016x}", vertexShader->baseHash);
\t\treturn nullptr;
\t}
"""
core = replace_once(core, cache_anchor, cache_new, "pipeline cache outer lookup")

inner_anchor = """\tconst auto innerit = it->second.find(stateHash);
\tif (innerit == it->second.cend())
\t\treturn nullptr;

\treturn innerit->second;
}"""
inner_new = """\tconst auto innerit = it->second.find(stateHash);
\tif (innerit == it->second.cend())
\t{
\t\tif (diagPipelineCache)
\t\t\tcemuLog_log(LogType::Force, "[PIPE_CACHE] miss stage=state vs={:016x} state={:016x}", vertexShader->baseHash, stateHash);
\t\treturn nullptr;
\t}
\tif (diagPipelineCache)
\t\tcemuLog_log(LogType::Force, "[PIPE_CACHE] hit vs={:016x} state={:016x}", vertexShader->baseHash, stateHash);
\treturn innerit->second;
}"""
core = replace_once(core, inner_anchor, inner_new, "pipeline cache inner lookup")
core_path.write_text(core, encoding="utf-8", newline="\n")

print("[lean-pipeline] pipeline/cache/shader association diagnostics installed")
