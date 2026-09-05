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
# Bayonetta 2 target0 producer uniform delta trace.
#
# Observation-only. Applied after the target0 producer resource trace.
# The Run #12 runtime capture proved that producer VB identity/content and all
# constant-buffer identities/content are stable across ZERO/NONZERO, while the
# VS/PS uniform-variable blocks change by generation. This trace narrows that
# remaining difference without modifying any query/render/resource behavior.
#
# For the two recurring VS hashes and four recurring PS hashes only, log a vec4
# slot when its 16-byte value changed since the previous target0 generation for
# that shader. Repeated draws using the same shader in one generation are
# suppressed. Values are recorded directly so transition captures can be
# compared numerically instead of by whole-block hash only.
# -----------------------------------------------------------------------------
vk_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
vk = vk_path.read_text(encoding="utf-8")

uniform_helpers = '''struct Bayo2Target0UniformDeltaState
{
\tuint64 lastGeneration{};
\tuint64 slotHash[256]{};
\tbool initialized{};
};

static Bayo2Target0UniformDeltaState s_bayo2Target0VsE6fc{};
static Bayo2Target0UniformDeltaState s_bayo2Target0Vs93a1{};
static Bayo2Target0UniformDeltaState s_bayo2Target0PsE2b9{};
static Bayo2Target0UniformDeltaState s_bayo2Target0Ps5199{};
static Bayo2Target0UniformDeltaState s_bayo2Target0Ps902c{};
static Bayo2Target0UniformDeltaState s_bayo2Target0Ps3626{};

static Bayo2Target0UniformDeltaState* Bayo2Target0UniformDelta_GetState(uint64 shaderHash)
{
\tswitch (shaderHash)
\t{
\tcase 0xe6fc4f385f9b0034ULL:
\t\treturn &s_bayo2Target0VsE6fc;
\tcase 0x93a12f899ed56598ULL:
\t\treturn &s_bayo2Target0Vs93a1;
\tcase 0xe2b9a6e6c2a4a0f8ULL:
\t\treturn &s_bayo2Target0PsE2b9;
\tcase 0x519954498085e510ULL:
\t\treturn &s_bayo2Target0Ps5199;
\tcase 0x902ca3422dccc182ULL:
\t\treturn &s_bayo2Target0Ps902c;
\tcase 0x362608e302d3de4cULL:
\t\treturn &s_bayo2Target0Ps3626;
\tdefault:
\t\treturn nullptr;
\t}
}

static void Bayo2Target0UniformDelta_LogStage(
\tconst char* stage,
\tconst LatteDecompilerShader* shader,
\tconst float* uniformData,
\tuint32 capacityBytes,
\tuint64 generation,
\tuint64 frameSeq,
\tuint64 drawSeq)
{
\tif (shader == nullptr || uniformData == nullptr)
\t\treturn;

\tauto* state = Bayo2Target0UniformDelta_GetState(shader->baseHash);
\tif (state == nullptr || state->lastGeneration == generation)
\t\treturn;

\tconst uint32 size = std::min<uint32>(shader->uniform.uniformRangeSize, capacityBytes);
\tconst uint32 slotCount = std::min<uint32>((size + 15) / 16, 256);
\tconst auto* bytes = reinterpret_cast<const uint8*>(uniformData);

\tfor (uint32 slot = 0; slot < slotCount; slot++)
\t{
\t\tconst uint32 byteOffset = slot * 16;
\t\tconst uint32 byteCount = std::min<uint32>(16, size - byteOffset);
\t\tconst uint64 hash = Bayo2Target0ResourceTrace_HashBytes(bytes + byteOffset, byteCount);
\t\tconst uint64 previousHash = state->slotHash[slot];
\t\tif (!state->initialized || hash != previousHash)
\t\t{
\t\t\tconst uint32 floatOffset = slot * 4;
\t\t\tconst float v0 = uniformData[floatOffset + 0];
\t\t\tconst float v1 = byteCount > 4 ? uniformData[floatOffset + 1] : 0.0f;
\t\t\tconst float v2 = byteCount > 8 ? uniformData[floatOffset + 2] : 0.0f;
\t\t\tconst float v3 = byteCount > 12 ? uniformData[floatOffset + 3] : 0.0f;
\n\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[BAYO2_TARGET_UNIFORM] stage={} query=46a92ec8 gen={} frame={} draw={} shader={:016x} slot={} offset={} bytes={} prevHash={:016x} hash={:016x} value={},{},{},{}",
\t\t\t\tstage,
\t\t\t\tgeneration,
\t\t\t\tframeSeq,
\t\t\t\tdrawSeq,
\t\t\t\tshader->baseHash,
\t\t\t\tslot,
\t\t\t\tbyteOffset,
\t\t\t\tbyteCount,
\t\t\t\tpreviousHash,
\t\t\t\thash,
\t\t\t\tv0,
\t\t\t\tv1,
\t\t\t\tv2,
\t\t\t\tv3);
\t\t}
\t\tstate->slotHash[slot] = hash;
\t}

\tstate->initialized = true;
\tstate->lastGeneration = generation;
}

static void Bayo2Target0UniformDeltaTrace_LogDraw(
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

\tconst uint64 frameSeq = Bayo2QueryCorr_GetFrameSeq();
\tconst uint64 drawSeq = Bayo2QueryCorr_GetDrawSeq();

\tBayo2Target0UniformDelta_LogStage(
\t\t"VS",
\t\tpipelineInfo->vertexShader,
\t\ts_vkUniformDataVS,
\t\tstatic_cast<uint32>(sizeof(s_vkUniformDataVS)),
\t\ttargetGeneration,
\t\tframeSeq,
\t\tdrawSeq);

\tBayo2Target0UniformDelta_LogStage(
\t\t"PS",
\t\tpipelineInfo->pixelShader,
\t\ts_vkUniformDataPS,
\t\tstatic_cast<uint32>(sizeof(s_vkUniformDataPS)),
\t\ttargetGeneration,
\t\tframeSeq,
\t\tdrawSeq);
}

'''
uniform_helpers = uniform_helpers.replace(chr(92) + "t", chr(9))

vk = replace_once(
    vk,
    "// includes only states that may change during minimal drawcalls\n",
    uniform_helpers + "// includes only states that may change during minimal drawcalls\n",
    "Vulkan target0 uniform delta helper insertion",
)

old_call = "\tBayo2Target0ProducerResourceTrace_LogDrawResources(pipeline_info, baseVertex, baseInstance, instanceCount, count, indexDataMPTR, indexType);\n"
new_call = old_call + "\tBayo2Target0UniformDeltaTrace_LogDraw(pipeline_info, baseVertex, baseInstance, instanceCount, count, indexDataMPTR, indexType);\n"
vk = replace_count(
    vk,
    old_call,
    new_call,
    2,
    "Vulkan target0 uniform delta call sites",
)

for token in (
    "[BAYO2_TARGET_UNIFORM]",
    "0xe6fc4f385f9b0034ULL",
    "0x93a12f899ed56598ULL",
    "0xe2b9a6e6c2a4a0f8ULL",
    "0x519954498085e510ULL",
    "0x902ca3422dccc182ULL",
    "0x362608e302d3de4cULL",
):
    if token not in vk:
        raise RuntimeError(f"target0 uniform delta token missing after transform: {token}")

if vk.count("Bayo2Target0UniformDeltaTrace_LogDraw(pipeline_info") != 2:
    raise RuntimeError("expected exactly two target0 uniform delta trace call sites")

vk_path.write_text(vk, encoding="utf-8", newline="\n")
print("Bayonetta 2 target0 producer uniform delta trace installed; behavior unchanged")
