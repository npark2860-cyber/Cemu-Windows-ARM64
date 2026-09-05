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
# Bayonetta 2 target0 producer exact index-buffer content trace.
#
# Observation-only. Prior runtime captures eliminated producer draw/state,
# VB/CB, uniform-specific and actual depth-identity/history discriminators.
# The six producer draws use fixed U16_BE index addresses/counts, but their
# guest index bytes have not yet been compared by result class.
#
# Hash the complete guest index range for each target0 producer draw. No
# sampling, readback, mutation, query/result or render-state changes.
# -----------------------------------------------------------------------------
vk_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
vk = vk_path.read_text(encoding="utf-8")

helpers = '''static uint64 Bayo2Target0IndexContentTrace_HashExact(MPTR address, uint32 size)
{
\tif (address == MPTR_NULL || size == 0 || address >= 0x50000000)
\t\treturn 0;

\tconst uint64 end = static_cast<uint64>(address) + static_cast<uint64>(size);
\tif (end > 0x50000000ULL)
\t\treturn 0;

\tconst uint8* base = memory_getPointerFromPhysicalOffset(address);
\tif (base == nullptr)
\t\treturn 0;

\treturn Bayo2Target0ResourceTrace_HashBytes(base, size);
}

static void Bayo2Target0IndexContentTrace_LogDraw(
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

\tconst uint32 indexTypeRaw = static_cast<uint32>(indexType);
\tuint32 bytesPerIndex = 0;
\tif (indexTypeRaw == 4) // U16_BE
\t\tbytesPerIndex = 2;
\telse if (indexTypeRaw == 9) // U32_BE
\t\tbytesPerIndex = 4;

\tconst uint64 byteSize64 = static_cast<uint64>(count) * static_cast<uint64>(bytesPerIndex);
\tconst uint32 byteSize = byteSize64 <= 0xFFFFFFFFULL ? static_cast<uint32>(byteSize64) : 0;
\tconst uint64 contentHash = Bayo2Target0IndexContentTrace_HashExact(indexDataMPTR, byteSize);
\tconst uint64 frameSeq = Bayo2QueryCorr_GetFrameSeq();
\tconst uint64 drawSeq = Bayo2QueryCorr_GetDrawSeq();

\tcemuLog_log(LogType::Force,
\t\t"[BAYO2_TARGET_INDEX] query=46a92ec8 gen={} frame={} draw={} pipeline={:016x} index={:08x} indexType={} count={} bytesPerIndex={} byteSize={} hash={:016x}",
\t\ttargetGeneration,
\t\tframeSeq,
\t\tdrawSeq,
\t\tpipelineInfo->stateHash,
\t\tindexDataMPTR,
\t\tindexTypeRaw,
\t\tcount,
\t\tbytesPerIndex,
\t\tbyteSize,
\t\tcontentHash);
}

'''
helpers = helpers.replace(chr(92) + "t", chr(9))

vk = replace_once(
    vk,
    "// includes only states that may change during minimal drawcalls\n",
    helpers + "// includes only states that may change during minimal drawcalls\n",
    "Vulkan target0 index content helper insertion",
)

old_call = "\tBayo2Target0DepthIdentityTrace_LogDraw(pipeline_info, baseVertex, baseInstance, instanceCount, count, indexDataMPTR, indexType);\n"
new_call = old_call + "\tBayo2Target0IndexContentTrace_LogDraw(pipeline_info, baseVertex, baseInstance, instanceCount, count, indexDataMPTR, indexType);\n"
vk = replace_count(
    vk,
    old_call,
    new_call,
    2,
    "Vulkan target0 index content call sites",
)

for token in (
    "[BAYO2_TARGET_INDEX]",
    "Bayo2Target0IndexContentTrace_HashExact",
    "memory_getPointerFromPhysicalOffset",
    "bytesPerIndex",
):
    if token not in vk:
        raise RuntimeError(f"target0 index content token missing after transform: {token}")

if vk.count("Bayo2Target0IndexContentTrace_LogDraw(pipeline_info") != 2:
    raise RuntimeError("expected exactly two target0 index content trace call sites")

vk_path.write_text(vk, encoding="utf-8", newline="\n")
print("Bayonetta 2 target0 exact index-buffer content trace installed; behavior unchanged")

# Apply target0 sampled-texture resource/content observation trace.
texture_resource_path = Path("tools/diagnostics/Apply-Bayo2Target0TextureResourceTrace.py")
exec(compile(texture_resource_path.read_text(encoding="utf-8"), str(texture_resource_path), "exec"))
