from pathlib import Path

path = Path("src/Cafe/HW/Latte/Core/LatteTexture.cpp")
text = path.read_text(encoding="utf-8")

copy_anchor = '''void LatteTexture_CopySlice(LatteTexture* srcTexture, sint32 srcSlice, sint32 srcMip, LatteTexture* dstTexture, sint32 dstSlice, sint32 dstMip, sint32 srcX, sint32 srcY, sint32 dstX, sint32 dstY, sint32 width, sint32 height)\n{\n'''
copy_insert = copy_anchor + '''\tstatic uint64 s_bayo2AliasCopyTrace = 0;\n\tconst bool traceAlias = srcTexture->physAddress == 0xf4c24000 || dstTexture->physAddress == 0xf4c24000;\n\tif (traceAlias)\n\t{\n\t\tconst char* copyPath = srcTexture->isDepth != dstTexture->isDepth ? "format-conversion" : "image-copy";\n\t\tif (s_bayo2AliasCopyTrace < 1024 || (s_bayo2AliasCopyTrace % 10000) == 0)\n\t\t{\n\t\t\tcemuLog_log(LogType::Force,\n\t\t\t\t"[BAYO2_ALIAS_COPY] n={} path={} srcAddr={:08x} srcFmt=0x{:x} srcDepth={} srcSize={}x{} srcPitch={} srcTile={} srcSwizzle={:08x} srcGPU={} srcMip={} srcSlice={} dstAddr={:08x} dstFmt=0x{:x} dstDepth={} dstSize={}x{} dstPitch={} dstTile={} dstSwizzle={:08x} dstGPU={} dstMip={} dstSlice={} copy={}x{}",\n\t\t\t\ts_bayo2AliasCopyTrace, copyPath,\n\t\t\t\tsrcTexture->physAddress, (uint32)srcTexture->format, srcTexture->isDepth, srcTexture->width, srcTexture->height, srcTexture->pitch, (uint32)srcTexture->tileMode, srcTexture->swizzle, srcTexture->isUpdatedOnGPU, srcMip, srcSlice,\n\t\t\t\tdstTexture->physAddress, (uint32)dstTexture->format, dstTexture->isDepth, dstTexture->width, dstTexture->height, dstTexture->pitch, (uint32)dstTexture->tileMode, dstTexture->swizzle, dstTexture->isUpdatedOnGPU, dstMip, dstSlice, width, height);\n\t\t}\n\t\ts_bayo2AliasCopyTrace++;\n\t}\n'''
if text.count(copy_anchor) != 1:
    raise SystemExit(f"Expected one LatteTexture_CopySlice anchor, found {text.count(copy_anchor)}")
text = text.replace(copy_anchor, copy_insert, 1)

relation_anchor = '''void LatteTexture_TrackTextureRelation(LatteTexture* texture1, LatteTexture* texture2)\n{\n\t// make sure texture 2 is always at texture 1 mip level 0 or beyond\n\tif (texture1->physAddress > texture2->physAddress)\n\t\treturn LatteTexture_TrackTextureRelation(texture2, texture1);\n'''
relation_insert = relation_anchor + '''\tconst bool traceAlias = texture1->physAddress == 0xf4c24000 || texture2->physAddress == 0xf4c24000;\n\tauto traceAliasRelation = [&](const char* result)\n\t{\n\t\tif (!traceAlias)\n\t\t\treturn;\n\t\tstatic uint64 s_bayo2AliasRelationTrace = 0;\n\t\tif (s_bayo2AliasRelationTrace < 512 || (s_bayo2AliasRelationTrace % 10000) == 0)\n\t\t{\n\t\t\tcemuLog_log(LogType::Force,\n\t\t\t\t"[BAYO2_ALIAS_REL] n={} result={} aAddr={:08x} aFmt=0x{:x} aDepth={} aSize={}x{} aPitch={} aTile={} aSwizzle={:08x} aGPU={} bAddr={:08x} bFmt=0x{:x} bDepth={} bSize={}x{} bPitch={} bTile={} bSwizzle={:08x} bGPU={}",\n\t\t\t\ts_bayo2AliasRelationTrace, result,\n\t\t\t\ttexture1->physAddress, (uint32)texture1->format, texture1->isDepth, texture1->width, texture1->height, texture1->pitch, (uint32)texture1->tileMode, texture1->swizzle, texture1->isUpdatedOnGPU,\n\t\t\t\ttexture2->physAddress, (uint32)texture2->format, texture2->isDepth, texture2->width, texture2->height, texture2->pitch, (uint32)texture2->tileMode, texture2->swizzle, texture2->isUpdatedOnGPU);\n\t\t}\n\t\ts_bayo2AliasRelationTrace++;\n\t};\n\ttraceAliasRelation("attempt");\n'''
if text.count(relation_anchor) != 1:
    raise SystemExit(f"Expected one LatteTexture_TrackTextureRelation anchor, found {text.count(relation_anchor)}")
text = text.replace(relation_anchor, relation_insert, 1)

old_duplicate = '''\tfor (auto& it : texture1->list_compatibleRelations)\n\t{\n\t\tif (it->baseTexture == texture1 && it->subTexture == texture2)\n\t\t\treturn; // association already known\n\t}\n'''
new_duplicate = '''\tfor (auto& it : texture1->list_compatibleRelations)\n\t{\n\t\tif (it->baseTexture == texture1 && it->subTexture == texture2)\n\t\t{\n\t\t\ttraceAliasRelation("duplicate");\n\t\t\treturn; // association already known\n\t\t}\n\t}\n'''
if text.count(old_duplicate) != 1:
    raise SystemExit(f"Expected one duplicate relation block, found {text.count(old_duplicate)}")
text = text.replace(old_duplicate, new_duplicate, 1)

old_blocked = '''\tif (LatteTexture_IsBlockedFormatRelation(texture1, texture2))\n\t\treturn;\n'''
new_blocked = '''\tif (LatteTexture_IsBlockedFormatRelation(texture1, texture2))\n\t{\n\t\ttraceAliasRelation("blocked-format");\n\t\treturn;\n\t}\n'''
if text.count(old_blocked) != 1:
    raise SystemExit(f"Expected one blocked-format check, found {text.count(old_blocked)}")
text = text.replace(old_blocked, new_blocked, 1)

old_submap = '''\t\t\tif (LatteTexture_GetSubtextureSliceAndMip(texture1, texture2, &baseSliceIndex, &baseMipIndex) == false)\n\t\t\t{\n\t\t\t\treturn;\n\t\t\t}\n'''
new_submap = '''\t\t\tif (LatteTexture_GetSubtextureSliceAndMip(texture1, texture2, &baseSliceIndex, &baseMipIndex) == false)\n\t\t\t{\n\t\t\t\ttraceAliasRelation("subtexture-map-fail");\n\t\t\t\treturn;\n\t\t\t}\n'''
if text.count(old_submap) != 1:
    raise SystemExit(f"Expected one subtexture mapping check, found {text.count(old_submap)}")
text = text.replace(old_submap, new_submap, 1)

old_compat = '''\t\tif (_LatteTexture_IsTileModeCompatible(texture1, baseMipIndex, texture2, 0) == false)\n\t\t\treturn; // not compatible\n\t\tif (texture1SliceInfo->pitch != texture2SliceInfo->pitch)\n\t\t\treturn; // not compatible\n'''
new_compat = '''\t\tif (_LatteTexture_IsTileModeCompatible(texture1, baseMipIndex, texture2, 0) == false)\n\t\t{\n\t\t\ttraceAliasRelation("tile-mismatch");\n\t\t\treturn; // not compatible\n\t\t}\n\t\tif (texture1SliceInfo->pitch != texture2SliceInfo->pitch)\n\t\t{\n\t\t\ttraceAliasRelation("pitch-mismatch");\n\t\t\treturn; // not compatible\n\t\t}\n'''
if text.count(old_compat) != 1:
    raise SystemExit(f"Expected one relation compatibility block, found {text.count(old_compat)}")
text = text.replace(old_compat, new_compat, 1)

old_success = '''\t\ttexture1->list_compatibleRelations.push_back(rel);\n\t\ttexture2->list_compatibleRelations.push_back(rel);\n\t}\n}\n'''
new_success = '''\t\ttexture1->list_compatibleRelations.push_back(rel);\n\t\ttexture2->list_compatibleRelations.push_back(rel);\n\t\ttraceAliasRelation("success");\n\t}\n}\n'''
if text.count(old_success) != 1:
    raise SystemExit(f"Expected one relation success block, found {text.count(old_success)}")
text = text.replace(old_success, new_success, 1)

path.write_text(text, encoding="utf-8")
print("[bayo2-alias-sync] patched LatteTexture.cpp")
print("[bayo2-alias-sync] observation only; no synchronization behavior changed")
print("[bayo2-alias-sync] markers: [BAYO2_ALIAS_REL], [BAYO2_ALIAS_COPY]")
