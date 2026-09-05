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
# Bayonetta 2 target0 producer sampled-texture resource observation.
#
# Observation-only. Run #15 proved all six exact guest index-buffer byte ranges
# are identical for completed ZERO and NONZERO generations. The next missing
# producer input class is sampled texture resource state/content.
#
# For the recurring two VS and four PS shader families only, record each shader
# texture unit actually referenced by the decompiler: all seven guest resource
# words, raw guest image/mip addresses, a 4 KiB guest-memory prefix hash, sampler
# assignment and depth-compare use. Repeated draws using the same shader within
# one target0 generation are suppressed. No texture lookup/creation, readback,
# mutation, descriptor change, query/result change or draw behavior change.
# -----------------------------------------------------------------------------
vk_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
vk = vk_path.read_text(encoding="utf-8")

helpers = '''struct Bayo2Target0TextureResourceState
{
\tuint64 lastGeneration{};
};

static Bayo2Target0TextureResourceState s_bayo2Target0TexVsE6fc{};
static Bayo2Target0TextureResourceState s_bayo2Target0TexVs93a1{};
static Bayo2Target0TextureResourceState s_bayo2Target0TexPsE2b9{};
static Bayo2Target0TextureResourceState s_bayo2Target0TexPs5199{};
static Bayo2Target0TextureResourceState s_bayo2Target0TexPs902c{};
static Bayo2Target0TextureResourceState s_bayo2Target0TexPs3626{};

static Bayo2Target0TextureResourceState* Bayo2Target0TextureResource_GetState(uint64 shaderHash)
{
\tswitch (shaderHash)
\t{
\tcase 0xe6fc4f385f9b0034ULL:
\t\treturn &s_bayo2Target0TexVsE6fc;
\tcase 0x93a12f899ed56598ULL:
\t\treturn &s_bayo2Target0TexVs93a1;
\tcase 0xe2b9a6e6c2a4a0f8ULL:
\t\treturn &s_bayo2Target0TexPsE2b9;
\tcase 0x519954498085e510ULL:
\t\treturn &s_bayo2Target0TexPs5199;
\tcase 0x902ca3422dccc182ULL:
\t\treturn &s_bayo2Target0TexPs902c;
\tcase 0x362608e302d3de4cULL:
\t\treturn &s_bayo2Target0TexPs3626;
\tdefault:
\t\treturn nullptr;
\t}
}

static void Bayo2Target0TextureResource_LogStage(
\tconst char* stage,
\tconst LatteDecompilerShader* shader,
\tuint32 baseReg,
\tuint64 generation,
\tuint64 frameSeq,
\tuint64 drawSeq)
{
\tif (shader == nullptr)
\t\treturn;

\tauto* state = Bayo2Target0TextureResource_GetState(shader->baseHash);
\tif (state == nullptr || state->lastGeneration == generation)
\t\treturn;
\tstate->lastGeneration = generation;

\tconst sint32 textureCount = shader->textureUnitListCount;
\tif (textureCount == 0)
\t{
\t\tcemuLog_log(LogType::Force,
\t\t\t"[BAYO2_TARGET_TEXTURE] stage={} query=46a92ec8 gen={} frame={} draw={} shader={:016x} textureCount=0 unit=-1",
\t\t\tstage, generation, frameSeq, drawSeq, shader->baseHash);
\t\treturn;
\t}

\tuint32* ctx = LatteGPUState.contextNew.GetRawView();
\tfor (sint32 i = 0; i < textureCount; i++)
\t{
\t\tconst uint32 unit = shader->textureUnitList[i];
\t\tif (unit >= Latte::GPU_LIMITS::NUM_TEXTURES_PER_STAGE)
\t\t\tcontinue;

\t\tconst uint32 reg = baseReg + unit * 7;
\t\tconst uint32 w0 = ctx[reg + 0];
\t\tconst uint32 w1 = ctx[reg + 1];
\t\tconst uint32 w2 = ctx[reg + 2];
\t\tconst uint32 w3 = ctx[reg + 3];
\t\tconst uint32 w4 = ctx[reg + 4];
\t\tconst uint32 w5 = ctx[reg + 5];
\t\tconst uint32 w6 = ctx[reg + 6];
\t\tconst MPTR imageRaw = static_cast<MPTR>(w2 << 8);
\t\tconst MPTR mipRaw = static_cast<MPTR>(w3 << 8);
\t\tconst uint64 image4kHash = Bayo2Target0ResourceTrace_HashPhysical(imageRaw, 4096);
\t\tconst uint64 mip4kHash = mipRaw != MPTR_NULL ? Bayo2Target0ResourceTrace_HashPhysical(mipRaw, 4096) : 0;
\t\tconst sint32 samplerAssignment = shader->textureUnitSamplerAssignment[unit];
\t\tconst uint32 depthCompare = shader->textureUsesDepthCompare[unit] ? 1u : 0u;

\t\tcemuLog_log(LogType::Force,
\t\t\t"[BAYO2_TARGET_TEXTURE] stage={} query=46a92ec8 gen={} frame={} draw={} shader={:016x} textureCount={} unit={} "
\t\t\t"word0={:08x} word1={:08x} word2={:08x} word3={:08x} word4={:08x} word5={:08x} word6={:08x} "
\t\t\t"imageRaw={:08x} mipRaw={:08x} image4kHash={:016x} mip4kHash={:016x} samplerAssignment={} depthCompare={}",
\t\t\tstage,
\t\t\tgeneration,
\t\t\tframeSeq,
\t\t\tdrawSeq,
\t\t\tshader->baseHash,
\t\t\ttextureCount,
\t\t\tunit,
\t\t\tw0,
\t\t\tw1,
\t\t\tw2,
\t\t\tw3,
\t\t\tw4,
\t\t\tw5,
\t\t\tw6,
\t\t\timageRaw,
\t\t\tmipRaw,
\t\t\timage4kHash,
\t\t\tmip4kHash,
\t\t\tsamplerAssignment,
\t\t\tdepthCompare);
\t}
}

static void Bayo2Target0TextureResourceTrace_LogDraw(
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

\tBayo2Target0TextureResource_LogStage(
\t\t"VS", pipelineInfo->vertexShader,
\t\tstatic_cast<uint32>(Latte::REGADDR::SQ_TEX_RESOURCE_WORD0_N_VS),
\t\ttargetGeneration, frameSeq, drawSeq);
\tBayo2Target0TextureResource_LogStage(
\t\t"PS", pipelineInfo->pixelShader,
\t\tstatic_cast<uint32>(Latte::REGADDR::SQ_TEX_RESOURCE_WORD0_N_PS),
\t\ttargetGeneration, frameSeq, drawSeq);
\tBayo2Target0TextureResource_LogStage(
\t\t"GS", pipelineInfo->geometryShader,
\t\tstatic_cast<uint32>(Latte::REGADDR::SQ_TEX_RESOURCE_WORD0_N_GS),
\t\ttargetGeneration, frameSeq, drawSeq);
}

'''
helpers = helpers.replace(chr(92) + "t", chr(9))

vk = replace_once(
    vk,
    "// includes only states that may change during minimal drawcalls\n",
    helpers + "// includes only states that may change during minimal drawcalls\n",
    "Vulkan target0 texture resource helper insertion",
)

old_call = "\tBayo2Target0IndexContentTrace_LogDraw(pipeline_info, baseVertex, baseInstance, instanceCount, count, indexDataMPTR, indexType);\n"
new_call = old_call + "\tBayo2Target0TextureResourceTrace_LogDraw(pipeline_info, baseVertex, baseInstance, instanceCount, count, indexDataMPTR, indexType);\n"
vk = replace_count(
    vk,
    old_call,
    new_call,
    2,
    "Vulkan target0 texture resource call sites",
)

for token in (
    "[BAYO2_TARGET_TEXTURE]",
    "SQ_TEX_RESOURCE_WORD0_N_VS",
    "SQ_TEX_RESOURCE_WORD0_N_PS",
    "SQ_TEX_RESOURCE_WORD0_N_GS",
    "textureUnitListCount",
    "image4kHash",
):
    if token not in vk:
        raise RuntimeError(f"target0 texture resource token missing after transform: {token}")

if vk.count("Bayo2Target0TextureResourceTrace_LogDraw(pipeline_info") != 2:
    raise RuntimeError("expected exactly two target0 texture resource trace call sites")

vk_path.write_text(vk, encoding="utf-8", newline="\n")
print("Bayonetta 2 target0 sampled-texture resource trace installed; behavior unchanged")
