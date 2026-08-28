from pathlib import Path

TITLE_ID = "0x000500001011B900ULL"
TARGET_ADDR = "0xF5442800u"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 anchor, found {count}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# LatteTexture.cpp: observe relation rejection, creation and normal draw writes.
# ---------------------------------------------------------------------------
tex_path = Path("src/Cafe/HW/Latte/Core/LatteTexture.cpp")
tex = tex_path.read_text(encoding="utf-8")

tex = replace_once(
    tex,
    '#include "Cafe/GraphicPack/GraphicPack2.h"\n',
    '#include "Cafe/GraphicPack/GraphicPack2.h"\n#include "Cafe/CafeSystem.h"\n',
    "LatteTexture CafeSystem include",
)

state_anchor = '''std::atomic_bool s_refreshTextureQueryList;
std::vector<LatteTextureInformation> s_cacheInfoList;
'''
state_block = '''std::atomic_bool s_refreshTextureQueryList;
std::vector<LatteTextureInformation> s_cacheInfoList;

// Bayonetta 2 JP f5442800 depth-alias observation only.
// No relation, invalidation, copy, clear or write behavior is changed here.
static uint64 s_bayo2F544DrawWriteCount = 0;
static uint32 s_bayo2F544LastDrawWritePitch = 0;

static bool Bayo2F544TraceEnabled_Texture()
{
\treturn CafeSystem::GetForegroundTitleId() == 0x000500001011B900ULL;
}

static size_t Bayo2F544SameAddressOverlapCount(const LatteTexture* texture)
{
\tif (!texture || !texture->sliceMipInfo)
\t\treturn 0;
\tauto* info = texture->sliceMipInfo + texture->GetSliceMipArrayIndex(0, 0);
\tsize_t count = 0;
\tfor (const auto& overlap : info->list_dataOverlap)
\t{
\t\tif (overlap.destTexture && overlap.destTexture->physAddress == 0xF5442800u)
\t\t\t++count;
\t}
\treturn count;
}
'''
tex = replace_once(tex, state_anchor, state_block, "LatteTexture trace state")

incompat_anchor = '''\t\t\t\t\t\t\telse
\t\t\t\t\t\t\t{
\t\t\t\t\t\t\t\t// pitch not compatible or format not compatible
\t\t\t\t\t\t\t}
'''
incompat_block = '''\t\t\t\t\t\t\telse
\t\t\t\t\t\t\t{
\t\t\t\t\t\t\t\t// pitch not compatible or format not compatible
\t\t\t\t\t\t\t\tif (Bayo2F544TraceEnabled_Texture() && texture->physAddress == 0xF5442800u && itrTexture->physAddress == 0xF5442800u)
\t\t\t\t\t\t\t\t{
\t\t\t\t\t\t\t\t\tconst bool pitchMatch = sliceMipInfo->pitch == occupancy.sliceMipInfo->pitch;
\t\t\t\t\t\t\t\t\tconst bool tileMatch = sliceMipInfo->tileMode == occupancy.sliceMipInfo->tileMode;
\t\t\t\t\t\t\t\t\tconst bool texelCompat = LatteTexture_IsTexelSizeCompatibleFormat(texture->format, itrTexture->format);
\t\t\t\t\t\t\t\t\tconst bool formatCompat = LatteTexture_IsFormatViewCompatible(texture->format, itrTexture->format);
\t\t\t\t\t\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\t\t\t\t\t"[BAYO2_F544_REL] result=untracked-zero-offset-incompatible A={}x{} pitch={} tile={} fmt=0x{:x} depth={} start={:08x} end={:08x} sub={} B={}x{} pitch={} tile={} fmt=0x{:x} depth={} start={:08x} end={:08x} sub={} pitchMatch={} tileMatch={} texelCompat={} formatCompat={}",
\t\t\t\t\t\t\t\t\t\ttexture->width, texture->height, sliceMipInfo->pitch, (uint32)sliceMipInfo->tileMode, (uint32)texture->format, texture->isDepth ? 1 : 0,
\t\t\t\t\t\t\t\t\t\tsliceMipInfo->addrStart, sliceMipInfo->addrEnd, sliceMipInfo->subIndex,
\t\t\t\t\t\t\t\t\t\titrTexture->width, itrTexture->height, occupancy.sliceMipInfo->pitch, (uint32)occupancy.sliceMipInfo->tileMode, (uint32)itrTexture->format, itrTexture->isDepth ? 1 : 0,
\t\t\t\t\t\t\t\t\t\toccupancy.sliceMipInfo->addrStart, occupancy.sliceMipInfo->addrEnd, occupancy.sliceMipInfo->subIndex,
\t\t\t\t\t\t\t\t\t\tpitchMatch ? 1 : 0, tileMatch ? 1 : 0, texelCompat ? 1 : 0, formatCompat ? 1 : 0);
\t\t\t\t\t\t\t\t}
\t\t\t\t\t\t\t}
'''
tex = replace_once(tex, incompat_anchor, incompat_block, "zero-offset incompatible relation observation")

create_anchor = '''\tLatteTexture* newTexture = view->baseTexture;
\tLatteTexture_GatherTextureRelations(view->baseTexture);
\tLatteTexture_UpdateTextureFromDynamicChanges(view->baseTexture);
'''
create_block = '''\tLatteTexture* newTexture = view->baseTexture;
\tLatteTexture_GatherTextureRelations(view->baseTexture);
\tif (Bayo2F544TraceEnabled_Texture() && newTexture->physAddress == 0xF5442800u && newTexture->isDepth)
\t{
\t\tstd::vector<LatteTexture*> sameAddressTextures;
\t\tLatteTC_LookupTexturesByPhysAddr(newTexture->physAddress, sameAddressTextures);
\t\tauto* info = newTexture->sliceMipInfo + newTexture->GetSliceMipArrayIndex(0, 0);
\t\tcemuLog_log(LogType::Force,
\t\t\t"[BAYO2_F544_CREATE] size={}x{} pitch={} tile={} fmt=0x{:x} aliases={} rels={} sameAddrOverlaps={} lastDynamic={} gpuUpdated={} reloadDynamic={}",
\t\t\tnewTexture->width, newTexture->height, newTexture->pitch, (uint32)newTexture->tileMode, (uint32)newTexture->format,
\t\t\tsameAddressTextures.size(), newTexture->list_compatibleRelations.size(), Bayo2F544SameAddressOverlapCount(newTexture),
\t\t\tinfo->lastDynamicUpdate, newTexture->isUpdatedOnGPU ? 1 : 0, newTexture->reloadFromDynamicTextures ? 1 : 0);
\t}
\tLatteTexture_UpdateTextureFromDynamicChanges(view->baseTexture);
'''
tex = replace_once(tex, create_anchor, create_block, "new f544 mapping observation")

write_anchor = '''void LatteTexture_TrackTextureGPUWrite(LatteTexture* texture, uint32 slice, uint32 mip, uint64 eventCounter)
{
\tLatteTexture_MarkDynamicTextureAsChanged(texture->baseView, slice, mip, eventCounter);
\tLatteTC_ResetTextureChangeTracker(texture);
\ttexture->isUpdatedOnGPU = true;
\ttexture->lastUnflushedRTDrawcallIndex = LatteGPUState.drawCallCounter;
}
'''
write_block = '''void LatteTexture_TrackTextureGPUWrite(LatteTexture* texture, uint32 slice, uint32 mip, uint64 eventCounter)
{
\tLatteTexture_MarkDynamicTextureAsChanged(texture->baseView, slice, mip, eventCounter);
\tif (Bayo2F544TraceEnabled_Texture() && texture->physAddress == 0xF5442800u && texture->isDepth)
\t{
\t\tconst uint64 n = ++s_bayo2F544DrawWriteCount;
\t\tconst bool switched = s_bayo2F544LastDrawWritePitch != (uint32)texture->pitch;
\t\ts_bayo2F544LastDrawWritePitch = texture->pitch;
\t\tif (switched || n <= 128 || (n % 10000ULL) == 0)
\t\t{
\t\t\tauto* info = texture->sliceMipInfo + texture->GetSliceMipArrayIndex(slice, mip);
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[BAYO2_F544_DRAW_WRITE] n={} switch={} event={} size={}x{} pitch={} tile={} rels={} sameAddrOverlaps={} lastDynamic={} reloadDynamic={} gpuUpdatedBefore={}",
\t\t\t\tn, switched ? 1 : 0, eventCounter, texture->width, texture->height, texture->pitch, (uint32)texture->tileMode,
\t\t\t\ttexture->list_compatibleRelations.size(), Bayo2F544SameAddressOverlapCount(texture), info->lastDynamicUpdate,
\t\t\t\ttexture->reloadFromDynamicTextures ? 1 : 0, texture->isUpdatedOnGPU ? 1 : 0);
\t\t}
\t}
\tLatteTC_ResetTextureChangeTracker(texture);
\ttexture->isUpdatedOnGPU = true;
\ttexture->lastUnflushedRTDrawcallIndex = LatteGPUState.drawCallCounter;
}
'''
tex = replace_once(tex, write_anchor, write_block, "draw GPU write observation")

tex_path.write_text(tex, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# LatteRenderTarget.cpp: observe representation switching/staleness and clears.
# ---------------------------------------------------------------------------
rt_path = Path("src/Cafe/HW/Latte/Core/LatteRenderTarget.cpp")
rt = rt_path.read_text(encoding="utf-8")

rt = replace_once(
    rt,
    '#include "Cafe/GraphicPack/GraphicPack2.h"\n',
    '#include "Cafe/GraphicPack/GraphicPack2.h"\n#include "Cafe/CafeSystem.h"\n',
    "LatteRenderTarget CafeSystem include",
)

rt_state_anchor = '''bool hasValidFramebufferAttached = false;
'''
rt_state_block = '''bool hasValidFramebufferAttached = false;

// Bayonetta 2 JP f5442800 depth-alias observation only.
static uint64 s_bayo2F544BindSwitchCount = 0;
static uint32 s_bayo2F544LastBoundPitch = 0;
static uint64 s_bayo2F544ClearTargetCount = 0;

static bool Bayo2F544TraceEnabled_RT()
{
\treturn CafeSystem::GetForegroundTitleId() == 0x000500001011B900ULL;
}
'''
rt = replace_once(rt, rt_state_anchor, rt_state_block, "LatteRenderTarget trace state")

bind_anchor = '''\t\t\t\tLatteTC_MarkTextureStillInUse(depthBufferView->baseTexture);
\t\t\t\t// after the drawcall mark the texture as updated
\t\t\t\tsLatteRenderTargetState.rtUpdateList[sLatteRenderTargetState.rtUpdateListCount] = depthBufferView;
\t\t\t\tsLatteRenderTargetState.rtUpdateListCount++;
\t\t\t\tSetDepthAndStencilAttachment(depthBufferView, depthBufferView->baseTexture->hasStencil);
'''
bind_block = '''\t\t\t\tLatteTC_MarkTextureStillInUse(depthBufferView->baseTexture);
\t\t\t\tif (Bayo2F544TraceEnabled_RT() && depthBufferView->baseTexture->physAddress == 0xF5442800u)
\t\t\t\t{
\t\t\t\t\tLatteTexture* current = depthBufferView->baseTexture;
\t\t\t\t\tconst bool switched = s_bayo2F544LastBoundPitch != (uint32)current->pitch;
\t\t\t\t\tif (switched)
\t\t\t\t\t{
\t\t\t\t\t\ts_bayo2F544LastBoundPitch = current->pitch;
\t\t\t\t\t\tconst uint64 n = ++s_bayo2F544BindSwitchCount;
\t\t\t\t\t\tauto* currentInfo = current->sliceMipInfo + current->GetSliceMipArrayIndex(depthBufferView->firstSlice, depthBufferView->firstMip);
\t\t\t\t\t\tuint64 newestOtherEvent = 0;
\t\t\t\t\t\tuint32 newestOtherPitch = 0;
\t\t\t\t\t\tuint32 newestOtherWidth = 0;
\t\t\t\t\t\tuint32 newestOtherHeight = 0;
\t\t\t\t\t\tstd::vector<LatteTexture*> aliases;
\t\t\t\t\t\tLatteTC_LookupTexturesByPhysAddr(current->physAddress, aliases);
\t\t\t\t\t\tfor (auto* alias : aliases)
\t\t\t\t\t\t{
\t\t\t\t\t\t\tif (!alias || alias == current || !alias->sliceMipInfo)
\t\t\t\t\t\t\t\tcontinue;
\t\t\t\t\t\t\tauto* aliasInfo = alias->sliceMipInfo + alias->GetSliceMipArrayIndex(0, 0);
\t\t\t\t\t\t\tif (aliasInfo->lastDynamicUpdate > newestOtherEvent)
\t\t\t\t\t\t\t{
\t\t\t\t\t\t\t\tnewestOtherEvent = aliasInfo->lastDynamicUpdate;
\t\t\t\t\t\t\t\tnewestOtherPitch = alias->pitch;
\t\t\t\t\t\t\t\tnewestOtherWidth = alias->width;
\t\t\t\t\t\t\t\tnewestOtherHeight = alias->height;
\t\t\t\t\t\t\t}
\t\t\t\t\t\t}
\t\t\t\t\t\tsize_t sameAddrOverlapCount = 0;
\t\t\t\t\t\tfor (const auto& overlap : currentInfo->list_dataOverlap)
\t\t\t\t\t\t\tif (overlap.destTexture && overlap.destTexture->physAddress == 0xF5442800u)
\t\t\t\t\t\t\t\t++sameAddrOverlapCount;
\t\t\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\t\t"[BAYO2_F544_BIND] n={} size={}x{} pitch={} tile={} selfEvent={} newestOtherEvent={} newestOther={}x{} pitch={} newerAlias={} aliases={} rels={} sameAddrOverlaps={} reloadDynamic={} gpuUpdated={}",
\t\t\t\t\t\t\tn, current->width, current->height, current->pitch, (uint32)current->tileMode, currentInfo->lastDynamicUpdate,
\t\t\t\t\t\t\tnewestOtherEvent, newestOtherWidth, newestOtherHeight, newestOtherPitch,
\t\t\t\t\t\t\tnewestOtherEvent > currentInfo->lastDynamicUpdate ? 1 : 0, aliases.size(), current->list_compatibleRelations.size(),
\t\t\t\t\t\t\tsameAddrOverlapCount, current->reloadFromDynamicTextures ? 1 : 0, current->isUpdatedOnGPU ? 1 : 0);
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\t// after the drawcall mark the texture as updated
\t\t\t\tsLatteRenderTargetState.rtUpdateList[sLatteRenderTargetState.rtUpdateListCount] = depthBufferView;
\t\t\t\tsLatteRenderTargetState.rtUpdateListCount++;
\t\t\t\tSetDepthAndStencilAttachment(depthBufferView, depthBufferView->baseTexture->hasStencil);
'''
rt = replace_once(rt, bind_anchor, bind_block, "f544 depth bind observation")

clear_lookup_anchor = '''\t\tstd::vector<LatteTexture*> list_depthClearTextures;
\t\tLatteTC_LookupTexturesByPhysAddr(depthBufferMPTR, list_depthClearTextures);
\t\tbool foundMatchingDepthBuffer = false;
'''
clear_lookup_block = '''\t\tstd::vector<LatteTexture*> list_depthClearTextures;
\t\tLatteTC_LookupTexturesByPhysAddr(depthBufferMPTR, list_depthClearTextures);
\t\tif (Bayo2F544TraceEnabled_RT() && depthBufferMPTR == 0xF5442800u)
\t\t{
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[BAYO2_F544_CLEAR_REQ] event={} req={}x{} pitch={} tile={} fmt=0x{:x} depthClear={} stencilClear={} depthValue={} stencilValue={} candidates={}",
\t\t\t\teventCounter, depthBufferWidth, depthBufferHeight, depthBufferPitch, (uint32)depthBufferTileMode, (uint32)depthBufferFormat,
\t\t\t\thasDepthClear ? 1 : 0, hasStencilClear ? 1 : 0, clearDepth, clearStencil, list_depthClearTextures.size());
\t\t}
\t\tbool foundMatchingDepthBuffer = false;
'''
rt = replace_once(rt, clear_lookup_anchor, clear_lookup_block, "f544 clear request observation")

clear_target_anchor = '''\t\t\tif (texItr->pitch == depthBufferPitch && texItr->height == depthBufferHeight)
\t\t\t\tfoundMatchingDepthBuffer = true;

\t\t\t// todo - calculate actual sliceIndex and mipIndex since the textures in list_depthClearTextures dont necessarily share the same base
\t\t\tLatteRenderTarget_applyTextureDepthClear(texItr, depthBufferViewFirstSlice, depthBufferMipIndex, hasDepthClear, hasStencilClear, clearDepth, clearStencil, eventCounter);
'''
clear_target_block = '''\t\t\tif (texItr->pitch == depthBufferPitch && texItr->height == depthBufferHeight)
\t\t\t\tfoundMatchingDepthBuffer = true;

\t\t\tif (Bayo2F544TraceEnabled_RT() && depthBufferMPTR == 0xF5442800u && texItr->physAddress == 0xF5442800u)
\t\t\t{
\t\t\t\tconst uint64 n = ++s_bayo2F544ClearTargetCount;
\t\t\t\tif (n <= 512 || (n % 10000ULL) == 0)
\t\t\t\t{
\t\t\t\t\tauto* info = texItr->sliceMipInfo + texItr->GetSliceMipArrayIndex(depthBufferViewFirstSlice, depthBufferMipIndex);
\t\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\t"[BAYO2_F544_CLEAR_TARGET] n={} event={} reqPitch={} target={}x{} pitch={} lastBefore={} rels={} overlaps={} depthClear={} stencilClear={}",
\t\t\t\t\t\tn, eventCounter, depthBufferPitch, texItr->width, texItr->height, texItr->pitch, info->lastDynamicUpdate,
\t\t\t\t\t\ttexItr->list_compatibleRelations.size(), info->list_dataOverlap.size(), hasDepthClear ? 1 : 0, hasStencilClear ? 1 : 0);
\t\t\t\t}
\t\t\t}

\t\t\t// todo - calculate actual sliceIndex and mipIndex since the textures in list_depthClearTextures dont necessarily share the same base
\t\t\tLatteRenderTarget_applyTextureDepthClear(texItr, depthBufferViewFirstSlice, depthBufferMipIndex, hasDepthClear, hasStencilClear, clearDepth, clearStencil, eventCounter);
'''
rt = replace_once(rt, clear_target_anchor, clear_target_block, "f544 clear target observation")

rt_path.write_text(rt, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Static safety checks: markers exist and no behavior-fix call was introduced.
# ---------------------------------------------------------------------------
patched_tex = tex_path.read_text(encoding="utf-8")
patched_rt = rt_path.read_text(encoding="utf-8")

for marker in (
    "[BAYO2_F544_REL]",
    "[BAYO2_F544_CREATE]",
    "[BAYO2_F544_DRAW_WRITE]",
    "[BAYO2_F544_BIND]",
    "[BAYO2_F544_CLEAR_REQ]",
    "[BAYO2_F544_CLEAR_TARGET]",
):
    if marker not in patched_tex and marker not in patched_rt:
        raise RuntimeError(f"missing marker: {marker}")

# The core experiment is observation-only. The original incompatible branch
# must remain behaviorally empty: do not route it into TrackDataOverlap and do
# not add a cross-pitch copy or invalidation here.
if "LatteTexture_TrackDataOverlap(texture, sliceMipInfo, occupancy);" not in patched_tex:
    raise RuntimeError("original non-zero-offset overlap tracking call missing")
if "BAYO2_F544_FORCE" in patched_tex or "BAYO2_F544_FORCE" in patched_rt:
    raise RuntimeError("behavior-changing force marker detected")

print("Bayonetta 2 f544 depth-alias observation trace installed; behavior unchanged")
