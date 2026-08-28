from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 anchor, found {count}")
    return text.replace(old, new, 1)


# This patch is applied AFTER Apply-Bayonetta2F544GuestRoundtripExperiment.py.
# It keeps that experiment's D24/S8 transfer implementation but disables the
# dangerous cross-pitch 256/64 -> guest RAM -> main 1280 canonicalization.
# Instead it validates one 64x64/pitch64 surface against itself exactly once.

rt_path = Path("src/Cafe/HW/Latte/Core/LatteRenderTarget.cpp")
rt = rt_path.read_text(encoding="utf-8")

anchor = '''static void Bayo2F544SyncBeforeMainBind(LatteTexture* mainTexture)\n{\n'''

insert = '''static void Bayo2F544SyncBeforeMainBind(LatteTexture* mainTexture)\n{\n\tstatic bool s_bayo2F544D24SelfRoundtripDone = false;\n\tif (!Bayo2F544GuestRoundtripEnabled() || !mainTexture || mainTexture->physAddress != 0xF5442800u ||\n\t\t!mainTexture->isDepth || mainTexture->format != Latte::E_GX2SURFFMT::D24_S8_UNORM ||\n\t\tmainTexture->width != 1280 || mainTexture->height != 720 || mainTexture->pitch != 1280)\n\t\treturn;\n\n\t// Self-validation only. The original cross-pitch body below is made unreachable.\n\tif (!s_bayo2F544D24SelfRoundtripDone)\n\t{\n\t\tLatteTexture* alias64 = nullptr;\n\t\tstd::vector<LatteTexture*> aliases;\n\t\tLatteTC_LookupTexturesByPhysAddr(mainTexture->physAddress, aliases);\n\t\tfor (auto* alias : aliases)\n\t\t{\n\t\t\tif (alias && alias != mainTexture && alias->isDepth &&\n\t\t\t\talias->format == Latte::E_GX2SURFFMT::D24_S8_UNORM &&\n\t\t\t\talias->width == 64 && alias->height == 64 && alias->pitch == 64 &&\n\t\t\t\talias->baseView && alias->isUpdatedOnGPU)\n\t\t\t{\n\t\t\t\talias64 = alias;\n\t\t\t\tbreak;\n\t\t\t}\n\t\t}\n\n\t\tif (alias64)\n\t\t{\n\t\t\tstd::vector<uint8> before(64u * 64u * 4u);\n\t\t\tstd::vector<uint8> after(64u * 64u * 4u);\n\t\t\tconst bool readBefore = LatteTextureReadback_ReadbackToLinearBlocking(alias64->baseView, before.data(), 64, 64, 64);\n\t\t\tif (!readBefore)\n\t\t\t{\n\t\t\t\tcemuLog_log(LogType::Force, "[BAYO2_F544_D24_SELFTEST] result=read-before-failed");\n\t\t\t\ts_bayo2F544D24SelfRoundtripDone = true;\n\t\t\t\treturn;\n\t\t\t}\n\n\t\t\tLatteTextureDefinition def(alias64);\n\t\t\tLatteTextureLoader_writeReadbackTextureToMemory(&def, 0, 0, before.data());\n\n\t\t\tg_bayo2F544GuestRoundtripUpload = true;\n\t\t\tLatteTexture_ReloadData(alias64);\n\t\t\tg_bayo2F544GuestRoundtripUpload = false;\n\n\t\t\tconst bool readAfter = LatteTextureReadback_ReadbackToLinearBlocking(alias64->baseView, after.data(), 64, 64, 64);\n\t\t\tif (!readAfter)\n\t\t\t{\n\t\t\t\tcemuLog_log(LogType::Force, "[BAYO2_F544_D24_SELFTEST] result=read-after-failed");\n\t\t\t\ts_bayo2F544D24SelfRoundtripDone = true;\n\t\t\t\treturn;\n\t\t\t}\n\n\t\t\tuint32 mismatchPixels = 0;\n\t\t\tuint32 depthMismatchPixels = 0;\n\t\t\tuint32 stencilMismatchPixels = 0;\n\t\t\tuint32 firstMismatch = 0xFFFFFFFFu;\n\t\t\tuint32 beforeFirst = 0;\n\t\t\tuint32 afterFirst = 0;\n\t\t\tconst uint32* before32 = reinterpret_cast<const uint32*>(before.data());\n\t\t\tconst uint32* after32 = reinterpret_cast<const uint32*>(after.data());\n\t\t\tfor (uint32 i = 0; i < 64u * 64u; i++)\n\t\t\t{\n\t\t\t\tif (before32[i] == after32[i])\n\t\t\t\t\tcontinue;\n\t\t\t\tmismatchPixels++;\n\t\t\t\tif ((before32[i] & 0x00FFFFFFu) != (after32[i] & 0x00FFFFFFu))\n\t\t\t\t\tdepthMismatchPixels++;\n\t\t\t\tif ((before32[i] >> 24) != (after32[i] >> 24))\n\t\t\t\t\tstencilMismatchPixels++;\n\t\t\t\tif (firstMismatch == 0xFFFFFFFFu)\n\t\t\t\t{\n\t\t\t\t\tfirstMismatch = i;\n\t\t\t\t\tbeforeFirst = before32[i];\n\t\t\t\t\tafterFirst = after32[i];\n\t\t\t\t}\n\t\t\t}\n\n\t\t\tauto* info = alias64->sliceMipInfo + alias64->GetSliceMipArrayIndex(0, 0);\n\t\t\tcemuLog_log(LogType::Force,\n\t\t\t\t"[BAYO2_F544_D24_SELFTEST] result={} event={} pixels=4096 mismatch={} depthMismatch={} stencilMismatch={} first={} before=0x{:08x} after=0x{:08x}",\n\t\t\t\tmismatchPixels == 0 ? "exact" : "mismatch", info->lastDynamicUpdate, mismatchPixels, depthMismatchPixels, stencilMismatchPixels,\n\t\t\t\tfirstMismatch, beforeFirst, afterFirst);\n\t\t\ts_bayo2F544D24SelfRoundtripDone = true;\n\t\t}\n\t}\n\n\t// Never execute the old cross-pitch canonicalization body in this validation build.\n\treturn;\n'''

rt = replace_once(rt, anchor, insert, "self-roundtrip override")

if "[BAYO2_F544_D24_SELFTEST]" not in rt:
    raise RuntimeError("self-test marker missing")
if "// Never execute the old cross-pitch canonicalization body in this validation build." not in rt:
    raise RuntimeError("cross-pitch short-circuit missing")

rt_path.write_text(rt, encoding="utf-8", newline="\n")
print("Bayonetta 2 f544 D24 same-surface self-roundtrip validation applied")
