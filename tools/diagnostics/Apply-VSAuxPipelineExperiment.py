from pathlib import Path

path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
text = path.read_text(encoding="utf-8")

include_old = '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"\n'
include_new = include_old + '#include "diagnostics/RuntimeExperiments.h"\n'
if '#include "diagnostics/RuntimeExperiments.h"' not in text:
    if include_old not in text:
        raise RuntimeError("VulkanRendererCore include anchor not found")
    text = text.replace(include_old, include_new, 1)

hash_old = "\tif (vertexShader)\n\t\tstateHash += vertexShader->baseHash;"
hash_new = "\tif (vertexShader)\n\t{\n\t\tstateHash += vertexShader->baseHash;\n\t\tif (RuntimeExperiments::Enabled(\"pipeline-vs-aux-key\"))\n\t\t\tstateHash += vertexShader->auxHash;\n\t}"
if 'RuntimeExperiments::Enabled("pipeline-vs-aux-key")' not in text:
    if hash_old not in text:
        raise RuntimeError("VS hash anchor not found")
    text = text.replace(hash_old, hash_new, 1)

cache_old = "\tconst auto innerit = it->second.find(stateHash);\n\tif (innerit == it->second.cend())\n\t\treturn nullptr;\n\n\treturn innerit->second;"
cache_new = "\tconst auto innerit = it->second.find(stateHash);\n\tif (innerit == it->second.cend())\n\t\treturn nullptr;\n\n\tPipelineInfo* cachedPipeline = innerit->second;\n\tif (RuntimeExperiments::Enabled(\"pipeline-vs-aux-diag\") &&\n\t\tcachedPipeline->vertexShader &&\n\t\tcachedPipeline->vertexShader->auxHash != vertexShader->auxHash)\n\t{\n\t\tstatic std::atomic_uint64_t s_vsAuxMismatchCount{0};\n\t\tconst uint64 mismatchCount = s_vsAuxMismatchCount.fetch_add(1, std::memory_order_relaxed) + 1;\n\t\tif (mismatchCount <= 100 || (mismatchCount % 1000) == 0)\n\t\t{\n\t\t\tcemuLog_log(LogType::Force,\n\t\t\t\t\"[PIPE_VS_AUX] mismatch #{} base={:016x} currentAux={:016x} cachedAux={:016x} state={:016x}\",\n\t\t\t\tmismatchCount, vertexShader->baseHash, vertexShader->auxHash,\n\t\t\t\tcachedPipeline->vertexShader->auxHash, stateHash);\n\t\t}\n\t}\n\n\treturn cachedPipeline;"
if '[PIPE_VS_AUX] mismatch' not in text:
    if cache_old not in text:
        raise RuntimeError("Pipeline cache return anchor not found")
    text = text.replace(cache_old, cache_new, 1)

path.write_text(text, encoding="utf-8", newline="\n")
print("[pipeline-vs-aux] installed diag/key experiment")
