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
# Bayonetta 2 target0 (0x46a92ec8) downstream resource identity/content trace.
#
# Observation-only. Applied after the existing target-transition downstream
# trace. It inspects only the recurring downstream pipeline family observed in
# the prior runtime capture and records guest resource identities/content hashes.
# -----------------------------------------------------------------------------
vk_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
vk = vk_path.read_text(encoding="utf-8")

resource_helpers = r'''extern float s_vkUniformDataVS[512 * 4];
extern float s_vkUniformDataPS[512 * 4];
extern float s_vkUniformDataGS[512 * 4];

static FORCE_INLINE void Bayo2Target0ResourceTrace_Mix(uint64& hash, uint64 value)
{
\thash ^= value + 0x9e3779b97f4a7c15ULL + (hash << 6) + (hash >> 2);
}

static uint64 Bayo2Target0ResourceTrace_HashBytes(const uint8* data, uint32 size)
{
\tif (data == nullptr || size == 0)
\t\treturn 0;

\tuint64 hash = 1469598103934665603ULL;
\tfor (uint32 i = 0; i < size; i++)
\t{
\t\thash ^= data[i];
\t\thash *= 1099511628211ULL;
\t}
\treturn hash;
}

static uint64 Bayo2Target0ResourceTrace_HashPhysical(MPTR address, uint32 size)
{
\tif (address == MPTR_NULL || size == 0 || address >= 0x50000000)
\t\treturn 0;

\tuint64 end = static_cast<uint64>(address) + static_cast<uint64>(size);
\tif (end > 0x50000000ULL)
\t\tsize = static_cast<uint32>(0x50000000ULL - address);
\tif (size == 0)
\t\treturn 0;

\tconst uint8* base = memory_getPointerFromPhysicalOffset(address);
\tif (base == nullptr)
\t\treturn 0;

\tif (size <= 4096)
\t\treturn Bayo2Target0ResourceTrace_HashBytes(base, size);

\tconstexpr uint32 chunkSize = 256;
\tconst uint32 offsets[4] = {
\t\t0,
\t\t(size / 3) > (chunkSize / 2) ? (size / 3) - (chunkSize / 2) : 0,
\t\t((size * 2) / 3) > (chunkSize / 2) ? ((size * 2) / 3) - (chunkSize / 2) : 0,
\t\tsize - chunkSize
\t};

\tuint64 hash = 1469598103934665603ULL;
\tfor (uint32 offset : offsets)
\t{
\t\tconst uint32 clampedOffset = std::min<uint32>(offset, size - chunkSize);
\t\tconst uint64 chunkHash = Bayo2Target0ResourceTrace_HashBytes(base + clampedOffset, chunkSize);
\t\tBayo2Target0ResourceTrace_Mix(hash, clampedOffset);
\t\tBayo2Target0ResourceTrace_Mix(hash, chunkHash);
\t}
\treturn hash;
}

struct Bayo2Target0ResourceBindingSummary
{
\tuint32 count{};
\tuint64 identityHash{};
\tuint64 contentHash{};
\tMPTR firstAddress{};
\tuint32 firstSize{};
\tuint32 firstAux{};
};

struct Bayo2Target0UniformSummary
{
\tBayo2Target0ResourceBindingSummary cb{};
\tuint32 varSize{};
\tuint64 varHash{};
};

static Bayo2Target0ResourceBindingSummary Bayo2Target0ResourceTrace_SummarizeVertexBuffers(
\tconst PipelineInfo* pipelineInfo,
\tuint32* ctx)
{
\tBayo2Target0ResourceBindingSummary summary{};
\tif (pipelineInfo == nullptr || pipelineInfo->fetchShader == nullptr || ctx == nullptr)
\t\treturn summary;

\tuint64 identityHash = 1469598103934665603ULL;
\tuint64 contentHash = 1469598103934665603ULL;

\tfor (const auto& group : pipelineInfo->fetchShader->bufferGroups)
\t{
\t\tconst uint32 bufferIndex = group.attributeBufferIndex;
\t\tconst uint32 reg = mmSQ_VTX_ATTRIBUTE_BLOCK_START + bufferIndex * 7;
\t\tconst MPTR address = ctx[reg + 0];
\t\tconst uint32 size = ctx[reg + 1] + 1;
\t\tconst uint32 stride = group.getCurrentBufferStride(ctx);
\t\tconst uint64 memoryHash = Bayo2Target0ResourceTrace_HashPhysical(address, size);

\t\tif (summary.count == 0)
\t\t{
\t\t\tsummary.firstAddress = address;
\t\t\tsummary.firstSize = size;
\t\t\tsummary.firstAux = stride;
\t\t}
\t\tsummary.count++;

\t\tBayo2Target0ResourceTrace_Mix(identityHash, bufferIndex);
\t\tBayo2Target0ResourceTrace_Mix(identityHash, address);
\t\tBayo2Target0ResourceTrace_Mix(identityHash, size);
\t\tBayo2Target0ResourceTrace_Mix(identityHash, stride);
\t\tBayo2Target0ResourceTrace_Mix(contentHash, bufferIndex);
\t\tBayo2Target0ResourceTrace_Mix(contentHash, memoryHash);
\t}

\tif (summary.count != 0)
\t{
\t\tsummary.identityHash = identityHash;
\t\tsummary.contentHash = contentHash;
\t}
\treturn summary;
}

static Bayo2Target0UniformSummary Bayo2Target0ResourceTrace_SummarizeUniformStage(
\tconst LatteDecompilerShader* shader,
\tconst uint32* ctx,
\tuint32 uniformBufferRegOffset,
\tconst float* uniformVarData,
\tuint32 uniformVarCapacityBytes)
{
\tBayo2Target0UniformSummary summary{};
\tif (shader == nullptr || ctx == nullptr)
\t\treturn summary;

\tsummary.varSize = std::min<uint32>(shader->uniform.uniformRangeSize, uniformVarCapacityBytes);
\tif (summary.varSize != 0 && uniformVarData != nullptr)
\t\tsummary.varHash = Bayo2Target0ResourceTrace_HashBytes(reinterpret_cast<const uint8*>(uniformVarData), summary.varSize);

\tif (shader->uniformMode != LATTE_DECOMPILER_UNIFORM_MODE_FULL_CBANK)
\t\treturn summary;

\tuint64 identityHash = 1469598103934665603ULL;
\tuint64 contentHash = 1469598103934665603ULL;

\tfor (const auto& buf : shader->list_quickBufferList)
\t{
\t\tconst uint32 bufferIndex = static_cast<uint32>(buf.index);
\t\tconst uint32 reg = uniformBufferRegOffset + bufferIndex * 7;
\t\tconst MPTR address = ctx[reg + 0];
\t\tuint32 size = ctx[reg + 1] + 1;
\t\tsize = std::min<uint32>(size, static_cast<uint32>(buf.size));
\t\tconst uint64 memoryHash = Bayo2Target0ResourceTrace_HashPhysical(address, size);

\t\tif (summary.cb.count == 0)
\t\t{
\t\t\tsummary.cb.firstAddress = address;
\t\t\tsummary.cb.firstSize = size;
\t\t\tsummary.cb.firstAux = bufferIndex;
\t\t}
\t\tsummary.cb.count++;

\t\tBayo2Target0ResourceTrace_Mix(identityHash, bufferIndex);
\t\tBayo2Target0ResourceTrace_Mix(identityHash, address);
\t\tBayo2Target0ResourceTrace_Mix(identityHash, size);
\t\tBayo2Target0ResourceTrace_Mix(contentHash, bufferIndex);
\t\tBayo2Target0ResourceTrace_Mix(contentHash, memoryHash);
\t}

\tif (summary.cb.count != 0)
\t{
\t\tsummary.cb.identityHash = identityHash;
\t\tsummary.cb.contentHash = contentHash;
\t}
\treturn summary;
}

static void Bayo2Target0ResourceTrace_LogDrawResources(
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

\tconst auto* vertexShader = pipelineInfo->vertexShader;
\tconst auto* pixelShader = pipelineInfo->pixelShader;
\tif (pipelineInfo->stateHash != 0x4addb8b25c8fc2bfULL ||
\t\tvertexShader == nullptr || vertexShader->baseHash != 0xdba0c5a2b50b7103ULL ||
\t\tpixelShader == nullptr || pixelShader->baseHash != 0x2360006f2b86aae5ULL)
\t{
\t\treturn;
\t}

\tconst uint64 frameSeq = Bayo2QueryCorr_GetFrameSeq();
\tBayo2TargetDownstreamWatchSnapshot watches[32]{};
\tconst uint32 watchCount = Bayo2TargetDownstream_GetActiveWatches(frameSeq, watches, 32);
\tif (watchCount == 0)
\t\treturn;

\tbool hasTarget0Watch = false;
\tfor (uint32 i = 0; i < watchCount; i++)
\t{
\t\tif (watches[i].targetIndex == 0 && watches[i].queryMPTR == 0x46a92ec8)
\t\t{
\t\t\thasTarget0Watch = true;
\t\t\tbreak;
\t\t}
\t}
\tif (!hasTarget0Watch)
\t\treturn;

\tuint32* ctx = LatteGPUState.contextNew.GetRawView();
\tconst auto vertexBuffers = Bayo2Target0ResourceTrace_SummarizeVertexBuffers(pipelineInfo, ctx);
\tconst auto vsUniform = Bayo2Target0ResourceTrace_SummarizeUniformStage(
\t\tvertexShader, ctx, mmSQ_VTX_UNIFORM_BLOCK_START, s_vkUniformDataVS, static_cast<uint32>(sizeof(s_vkUniformDataVS)));
\tconst auto psUniform = Bayo2Target0ResourceTrace_SummarizeUniformStage(
\t\tpixelShader, ctx, mmSQ_PS_UNIFORM_BLOCK_START, s_vkUniformDataPS, static_cast<uint32>(sizeof(s_vkUniformDataPS)));
\tconst auto* geometryShader = pipelineInfo->geometryShader;
\tconst auto gsUniform = Bayo2Target0ResourceTrace_SummarizeUniformStage(
\t\tgeometryShader, ctx, mmSQ_GS_UNIFORM_BLOCK_START, s_vkUniformDataGS, static_cast<uint32>(sizeof(s_vkUniformDataGS)));

\tconst uint64 drawSeq = Bayo2QueryCorr_GetDrawSeq();

\tfor (uint32 i = 0; i < watchCount; i++)
\t{
\t\tconst auto& watch = watches[i];
\t\tif (watch.targetIndex != 0 || watch.queryMPTR != 0x46a92ec8)
\t\t\tcontinue;

\t\tconst uint64 frameOffset = frameSeq - watch.triggerFrame;
\t\tcemuLog_log(LogType::Force,
\t\t\t"[BAYO2_RESOURCE] DRAW watch={} transition={} triggerGen={} prevResult={} result={} triggerFrame={} observedFrame={} frameOffset={} draw={} "
\t\t\t"pipeline={:016x} count={} instances={} baseVertex={} baseInstance={} indexType={} index={:08x} "
\t\t\t"vbCount={} vbIdentity={:016x} vbContent={:016x} vb0={:08x}/{}/{} "
\t\t\t"vsCbCount={} vsCbIdentity={:016x} vsCbContent={:016x} vsCb0={:08x}/{}/{} vsVarSize={} vsVarHash={:016x} "
\t\t\t"psCbCount={} psCbIdentity={:016x} psCbContent={:016x} psCb0={:08x}/{}/{} psVarSize={} psVarHash={:016x} "
\t\t\t"gsCbCount={} gsCbIdentity={:016x} gsCbContent={:016x} gsCb0={:08x}/{}/{} gsVarSize={} gsVarHash={:016x}",
\t\t\twatch.watchId,
\t\t\twatch.transitionCode == 1 ? "0->NZ" : "NZ->0",
\t\t\twatch.triggerGeneration,
\t\t\twatch.previousResult,
\t\t\twatch.result,
\t\t\twatch.triggerFrame,
\t\t\tframeSeq,
\t\t\tframeOffset,
\t\t\tdrawSeq,
\t\t\tpipelineInfo->stateHash,
\t\t\tcount,
\t\t\tinstanceCount,
\t\t\tbaseVertex,
\t\t\tbaseInstance,
\t\t\tstatic_cast<uint32>(indexType),
\t\t\tindexDataMPTR,
\t\t\tvertexBuffers.count,
\t\t\tvertexBuffers.identityHash,
\t\t\tvertexBuffers.contentHash,
\t\t\tvertexBuffers.firstAddress,
\t\t\tvertexBuffers.firstSize,
\t\t\tvertexBuffers.firstAux,
\t\t\tvsUniform.cb.count,
\t\t\tvsUniform.cb.identityHash,
\t\t\tvsUniform.cb.contentHash,
\t\t\tvsUniform.cb.firstAddress,
\t\t\tvsUniform.cb.firstSize,
\t\t\tvsUniform.cb.firstAux,
\t\t\tvsUniform.varSize,
\t\t\tvsUniform.varHash,
\t\t\tpsUniform.cb.count,
\t\t\tpsUniform.cb.identityHash,
\t\t\tpsUniform.cb.contentHash,
\t\t\tpsUniform.cb.firstAddress,
\t\t\tpsUniform.cb.firstSize,
\t\t\tpsUniform.cb.firstAux,
\t\t\tpsUniform.varSize,
\t\t\tpsUniform.varHash,
\t\t\tgsUniform.cb.count,
\t\t\tgsUniform.cb.identityHash,
\t\t\tgsUniform.cb.contentHash,
\t\t\tgsUniform.cb.firstAddress,
\t\t\tgsUniform.cb.firstSize,
\t\t\tgsUniform.cb.firstAux,
\t\t\tgsUniform.varSize,
\t\t\tgsUniform.varHash);
\t}
}

'''

vk = replace_once(
    vk,
    "// includes only states that may change during minimal drawcalls\n",
    resource_helpers + "// includes only states that may change during minimal drawcalls\n",
    "Vulkan target0 resource helper insertion",
)

old_call = "\tBayo2TargetDownstreamTrace_LogDrawFingerprint(pipeline_info, baseVertex, baseInstance, instanceCount, count, indexDataMPTR, indexType);\n"
new_call = old_call + "\tBayo2Target0ResourceTrace_LogDrawResources(pipeline_info, baseVertex, baseInstance, instanceCount, count, indexDataMPTR, indexType);\n"
vk = replace_count(
    vk,
    old_call,
    new_call,
    2,
    "Vulkan target0 resource trace call sites",
)

if "[BAYO2_RESOURCE] DRAW" not in vk:
    raise RuntimeError("target0 resource marker missing after transform")
if "0x4addb8b25c8fc2bfULL" not in vk:
    raise RuntimeError("target0 downstream pipeline filter missing after transform")
if vk.count("Bayo2Target0ResourceTrace_LogDrawResources(pipeline_info") != 2:
    raise RuntimeError("expected exactly two target0 resource trace call sites")

vk_path.write_text(vk, encoding="utf-8", newline="\n")
print("Bayonetta 2 target0 downstream vertex/uniform resource identity trace installed; behavior unchanged")