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


# -----------------------------------------------------------------------------
# Bayonetta 2 target0 (0x46a92ec8) query-producer resource trace.
#
# Observation-only. Applied after the existing target0 downstream resource trace
# so it reuses the already validated vertex/uniform resource summary helpers.
# It records resources only while target0 is actively bracketing its six query
# producer draws. Query values/readiness, render state, resources and draw
# execution are not modified.
# -----------------------------------------------------------------------------
vk_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
vk = vk_path.read_text(encoding="utf-8")

producer_helpers = '''static void Bayo2Target0ProducerResourceTrace_LogDrawResources(
\tPipelineInfo* pipelineInfo,
\tuint32 baseVertex,
\tuint32 baseInstance,
\tuint32 instanceCount,
\tuint32 count,
\tMPTR indexDataMPTR,
\tLatte::LATTE_VGT_DMA_INDEX_TYPE::E_INDEX_TYPE indexType)
{
\tif (pipelineInfo == nullptr)
\t\treturn;

\tMPTR queryMPTRs[5]{};
\tuint64 generations[5]{};
\tsint32 targetIndices[5]{};
\tconst uint32 targetCount = Bayo2QueryTarget_GetActiveTargets(queryMPTRs, generations, targetIndices, 5);
\tif (targetCount == 0)
\t\treturn;

\tuint64 targetGeneration = 0;
\tbool target0Active = false;
\tfor (uint32 i = 0; i < targetCount; i++)
\t{
\t\tif (targetIndices[i] == 0 && queryMPTRs[i] == 0x46a92ec8)
\t\t{
\t\t\ttargetGeneration = generations[i];
\t\t\ttarget0Active = true;
\t\t\tbreak;
\t\t}
\t}
\tif (!target0Active)
\t\treturn;

\tuint32* ctx = LatteGPUState.contextNew.GetRawView();
\tconst auto* vertexShader = pipelineInfo->vertexShader;
\tconst auto* pixelShader = pipelineInfo->pixelShader;
\tconst auto* geometryShader = pipelineInfo->geometryShader;

\tconst auto vertexBuffers = Bayo2Target0ResourceTrace_SummarizeVertexBuffers(pipelineInfo, ctx);
\tconst auto vsUniform = Bayo2Target0ResourceTrace_SummarizeUniformStage(
\t\tvertexShader, ctx, mmSQ_VTX_UNIFORM_BLOCK_START, s_vkUniformDataVS, static_cast<uint32>(sizeof(s_vkUniformDataVS)));
\tconst auto psUniform = Bayo2Target0ResourceTrace_SummarizeUniformStage(
\t\tpixelShader, ctx, mmSQ_PS_UNIFORM_BLOCK_START, s_vkUniformDataPS, static_cast<uint32>(sizeof(s_vkUniformDataPS)));
\tconst auto gsUniform = Bayo2Target0ResourceTrace_SummarizeUniformStage(
\t\tgeometryShader, ctx, mmSQ_GS_UNIFORM_BLOCK_START, s_vkUniformDataGS, static_cast<uint32>(sizeof(s_vkUniformDataGS)));

\tconst uint64 frameSeq = Bayo2QueryCorr_GetFrameSeq();
\tconst uint64 drawSeq = Bayo2QueryCorr_GetDrawSeq();

\tcemuLog_log(LogType::Force,
\t\t"[BAYO2_TARGET_RESOURCE] DRAW target=0 query=46a92ec8 gen={} frame={} draw={} "
\t\t"pipeline={:016x} count={} instances={} baseVertex={} baseInstance={} indexType={} index={:08x} "
\t\t"vbCount={} vbIdentity={:016x} vbContent={:016x} vb0={:08x}/{}/{} "
\t\t"vsCbCount={} vsCbIdentity={:016x} vsCbContent={:016x} vsCb0={:08x}/{}/{} vsVarSize={} vsVarHash={:016x} "
\t\t"psCbCount={} psCbIdentity={:016x} psCbContent={:016x} psCb0={:08x}/{}/{} psVarSize={} psVarHash={:016x} "
\t\t"gsCbCount={} gsCbIdentity={:016x} gsCbContent={:016x} gsCb0={:08x}/{}/{} gsVarSize={} gsVarHash={:016x}",
\t\ttargetGeneration,
\t\tframeSeq,
\t\tdrawSeq,
\t\tpipelineInfo->stateHash,
\t\tcount,
\t\tinstanceCount,
\t\tbaseVertex,
\t\tbaseInstance,
\t\tstatic_cast<uint32>(indexType),
\t\tindexDataMPTR,
\t\tvertexBuffers.count,
\t\tvertexBuffers.identityHash,
\t\tvertexBuffers.contentHash,
\t\tvertexBuffers.firstAddress,
\t\tvertexBuffers.firstSize,
\t\tvertexBuffers.firstAux,
\t\tvsUniform.cb.count,
\t\tvsUniform.cb.identityHash,
\t\tvsUniform.cb.contentHash,
\t\tvsUniform.cb.firstAddress,
\t\tvsUniform.cb.firstSize,
\t\tvsUniform.cb.firstAux,
\t\tvsUniform.varSize,
\t\tvsUniform.varHash,
\t\tpsUniform.cb.count,
\t\tpsUniform.cb.identityHash,
\t\tpsUniform.cb.contentHash,
\t\tpsUniform.cb.firstAddress,
\t\tpsUniform.cb.firstSize,
\t\tpsUniform.cb.firstAux,
\t\tpsUniform.varSize,
\t\tpsUniform.varHash,
\t\tgsUniform.cb.count,
\t\tgsUniform.cb.identityHash,
\t\tgsUniform.cb.contentHash,
\t\tgsUniform.cb.firstAddress,
\t\tgsUniform.cb.firstSize,
\t\tgsUniform.cb.firstAux,
\t\tgsUniform.varSize,
\t\tgsUniform.varHash);
}

'''
producer_helpers = producer_helpers.replace(chr(92) + "t", chr(9))

vk = replace_once(
    vk,
    "// includes only states that may change during minimal drawcalls\n",
    producer_helpers + "// includes only states that may change during minimal drawcalls\n",
    "Vulkan target0 producer resource helper insertion",
)

old_call = "\tBayo2Target0ResourceTrace_LogDrawResources(pipeline_info, baseVertex, baseInstance, instanceCount, count, indexDataMPTR, indexType);\n"
new_call = old_call + "\tBayo2Target0ProducerResourceTrace_LogDrawResources(pipeline_info, baseVertex, baseInstance, instanceCount, count, indexDataMPTR, indexType);\n"
vk = replace_count(
    vk,
    old_call,
    new_call,
    2,
    "Vulkan target0 producer resource call sites",
)

if "[BAYO2_TARGET_RESOURCE] DRAW" not in vk:
    raise RuntimeError("target0 producer resource marker missing after transform")
if "query=46a92ec8" not in vk:
    raise RuntimeError("target0 producer query pointer missing after transform")
if vk.count("Bayo2Target0ProducerResourceTrace_LogDrawResources(pipeline_info") != 2:
    raise RuntimeError("expected exactly two target0 producer resource trace call sites")

vk_path.write_text(vk, encoding="utf-8", newline="\n")
print("Bayonetta 2 target0 query-producer vertex/uniform resource trace installed; behavior unchanged")
