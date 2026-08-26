from pathlib import Path

path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
text = path.read_text(encoding="utf-8")

include_old = '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"\n'
include_new = include_old + '#include "diagnostics/RuntimeExperiments.h"\n#include "diagnostics/RuntimeDiagnostics.h"\n'
if '#include "diagnostics/RuntimeExperiments.h"' not in text:
    if include_old not in text:
        raise RuntimeError("VulkanRendererCore include anchor not found")
    text = text.replace(include_old, include_new, 1)
elif '#include "diagnostics/RuntimeDiagnostics.h"' not in text:
    text = text.replace('#include "diagnostics/RuntimeExperiments.h"\n', '#include "diagnostics/RuntimeExperiments.h"\n#include "diagnostics/RuntimeDiagnostics.h"\n', 1)

hash_old = "\tif (vertexShader)\n\t\tstateHash += vertexShader->baseHash;"
hash_new = "\tif (vertexShader)\n\t{\n\t\tstateHash += vertexShader->baseHash;\n\t\tif (RuntimeExperiments::Enabled(\"pipeline-vs-aux-key\"))\n\t\t\tstateHash += vertexShader->auxHash;\n\t}"
if 'RuntimeExperiments::Enabled("pipeline-vs-aux-key")' not in text:
    if hash_old not in text:
        raise RuntimeError("VS hash anchor not found")
    text = text.replace(hash_old, hash_new, 1)

cache_old = "\tconst auto innerit = it->second.find(stateHash);\n\tif (innerit == it->second.cend())\n\t\treturn nullptr;\n\n\treturn innerit->second;"
cache_new = '''\tconst auto innerit = it->second.find(stateHash);
\tif (innerit == it->second.cend())
\t{
\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PipelineCache))
\t\t{
\t\t\tconst uint64_t misses = RuntimeDiagnostics::g_pipelineCacheMisses.fetch_add(1, std::memory_order_relaxed) + 1;
\t\t\tif (misses <= 50 || (misses % 5000ULL) == 0)
\t\t\t\tcemuLog_log(LogType::Force, "[PIPE_CACHE] MISS n={} state={:016x} vs={:016x}", misses, stateHash, vertexShader ? vertexShader->baseHash : 0);
\t\t}
\t\treturn nullptr;
\t}

\tPipelineInfo* cachedPipeline = innerit->second;
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PipelineCache))
\t{
\t\tconst uint64_t hits = RuntimeDiagnostics::g_pipelineCacheHits.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (hits <= 50 || (hits % 5000ULL) == 0)
\t\t\tcemuLog_log(LogType::Force, "[PIPE_CACHE] HIT n={} state={:016x} vs={:016x}", hits, stateHash, vertexShader ? vertexShader->baseHash : 0);
\t}
\tif ((RuntimeExperiments::Enabled("pipeline-vs-aux-diag") || RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ShaderAuxHash)) &&
\t\tvertexShader && cachedPipeline->vertexShader &&
\t\tcachedPipeline->vertexShader->auxHash != vertexShader->auxHash)
\t{
\t\tstatic std::atomic_uint64_t s_vsAuxMismatchCount{0};
\t\tconst uint64 mismatchCount = s_vsAuxMismatchCount.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (mismatchCount <= 100 || (mismatchCount % 1000) == 0)
\t\t{
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[PIPE_VS_AUX] mismatch #{} base={:016x} currentAux={:016x} cachedAux={:016x} state={:016x}",
\t\t\t\tmismatchCount, vertexShader->baseHash, vertexShader->auxHash,
\t\t\t\tcachedPipeline->vertexShader->auxHash, stateHash);
\t\t}
\t}

\treturn cachedPipeline;'''
if '[PIPE_CACHE] HIT' not in text:
    if cache_old not in text:
        raise RuntimeError("Pipeline cache return anchor not found")
    text = text.replace(cache_old, cache_new, 1)

path.write_text(text, encoding="utf-8", newline="\n")
print("[pipeline-vs-aux] installed independent cache/auxHash diagnostics")