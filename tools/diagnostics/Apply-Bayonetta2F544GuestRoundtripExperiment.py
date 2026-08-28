from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 anchor, found {count}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Vulkan D24/S8 blocking readback: depth and stencil are separate buffer planes.
# This path is only exercised by the dedicated f544 roundtrip experiment.
# ---------------------------------------------------------------------------
rbvk_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/TextureReadbackVk.cpp")
rbvk = rbvk_path.read_text(encoding="utf-8")
rbvk = replace_once(
    rbvk,
    '''\telse if (textureView->format == Latte::E_GX2SURFFMT::D24_S8_UNORM)\n\t{\n\t\tcemu_assert(textureFormat == VK_FORMAT_D24_UNORM_S8_UINT);\n\t\t// todo - if driver does not support VK_FORMAT_D24_UNORM_S8_UINT this is represented as VK_FORMAT_D32_SFLOAT_S8_UINT which is 8 bytes\n\t\treturn baseTexture->width * baseTexture->height * 4;\n\t}\n''',
    '''\telse if (textureView->format == Latte::E_GX2SURFFMT::D24_S8_UNORM)\n\t{\n\t\tcemu_assert(textureFormat == VK_FORMAT_D24_UNORM_S8_UINT);\n\t\t// D24 depth aspect is X8_D24 (4 B/texel) and stencil is a separate S8 plane (1 B/texel).\n\t\treturn baseTexture->width * baseTexture->height * 5;\n\t}\n''',
    "D24 readback allocation",
)

old_start = '''void LatteTextureReadbackInfoVk::StartTransfer()\n{\n\tcemu_assert(m_textureView);\n\n\tauto* baseTexture = (LatteTextureVk*)m_textureView->baseTexture;\n\tbaseTexture->GetImageObj()->flagForCurrentCommandBuffer();\n\n\tcemu_assert_debug(m_textureView->firstSlice == 0);\n\tcemu_assert_debug(m_textureView->firstMip == 0);\n\tcemu_assert_debug(m_textureView->baseTexture->dim != Latte::E_DIM::DIM_3D);\n\n\tVkBufferImageCopy region{};\n\tregion.bufferOffset = m_buffer_offset;\n\tregion.bufferRowLength = baseTexture->width;\n\tregion.bufferImageHeight = baseTexture->height;\n\n\tregion.imageSubresource.aspectMask = baseTexture->GetImageAspect();\n\tregion.imageSubresource.baseArrayLayer = 0;\n\tregion.imageSubresource.layerCount = 1;\n\tregion.imageSubresource.mipLevel = 0;\n\n\tregion.imageOffset = {0,0,0};\n\tregion.imageExtent = {(uint32)baseTexture->width,(uint32)baseTexture->height,1};\n\n\tconst auto renderer = VulkanRenderer::GetInstance();\n\trenderer->draw_endRenderPass();\n\n\trenderer->barrier_image<VulkanRenderer::ANY_TRANSFER | VulkanRenderer::IMAGE_WRITE, VulkanRenderer::TRANSFER_READ>(baseTexture, region.imageSubresource, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL);\n\n\trenderer->barrier_sequentializeTransfer();\n\n\tvkCmdCopyImageToBuffer(renderer->getCurrentCommandBuffer(), baseTexture->GetImageObj()->m_image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, m_buffer, 1, &region);\n\n\trenderer->barrier_sequentializeTransfer();\n\n\trenderer->barrier_image<VulkanRenderer::TRANSFER_READ, VulkanRenderer::ANY_TRANSFER | VulkanRenderer::IMAGE_WRITE>(baseTexture, region.imageSubresource, baseTexture->GetDefaultLayout()); // make sure transfer is finished before image is modified\n\trenderer->barrier_bufferRange<VulkanRenderer::TRANSFER_WRITE, VulkanRenderer::HOST_READ>(m_buffer, m_buffer_offset, m_image_size); // make sure transfer is finished before result is read\n\n\tm_associatedCommandBufferId = renderer->GetCurrentCommandBufferId();\n\tm_textureView = nullptr;\n\n\t// to decrease latency of readbacks make sure that the current command buffer is submitted soon\n\trenderer->RequestSubmitSoon();\n\trenderer->RequestSubmitOnIdle();\n}\n'''
new_start = '''void LatteTextureReadbackInfoVk::StartTransfer()\n{\n\tcemu_assert(m_textureView);\n\n\tauto* baseTexture = (LatteTextureVk*)m_textureView->baseTexture;\n\tbaseTexture->GetImageObj()->flagForCurrentCommandBuffer();\n\n\tcemu_assert_debug(m_textureView->firstSlice == 0);\n\tcemu_assert_debug(m_textureView->firstMip == 0);\n\tcemu_assert_debug(m_textureView->baseTexture->dim != Latte::E_DIM::DIM_3D);\n\n\tVkBufferImageCopy regions[2]{};\n\tregions[0].bufferOffset = m_buffer_offset;\n\tregions[0].bufferRowLength = baseTexture->width;\n\tregions[0].bufferImageHeight = baseTexture->height;\n\tregions[0].imageSubresource.baseArrayLayer = 0;\n\tregions[0].imageSubresource.layerCount = 1;\n\tregions[0].imageSubresource.mipLevel = 0;\n\tregions[0].imageOffset = {0,0,0};\n\tregions[0].imageExtent = {(uint32)baseTexture->width,(uint32)baseTexture->height,1};\n\n\tuint32 regionCount = 1;\n\tif (m_textureView->format == Latte::E_GX2SURFFMT::D24_S8_UNORM && baseTexture->GetFormat() == VK_FORMAT_D24_UNORM_S8_UINT)\n\t{\n\t\tregions[0].imageSubresource.aspectMask = VK_IMAGE_ASPECT_DEPTH_BIT;\n\t\tregions[1] = regions[0];\n\t\tregions[1].bufferOffset = m_buffer_offset + (uint32)baseTexture->width * (uint32)baseTexture->height * 4u;\n\t\tregions[1].imageSubresource.aspectMask = VK_IMAGE_ASPECT_STENCIL_BIT;\n\t\tregionCount = 2;\n\t}\n\telse\n\t{\n\t\tregions[0].imageSubresource.aspectMask = baseTexture->GetImageAspect();\n\t}\n\n\tVkImageSubresourceLayers barrierSubresource = regions[0].imageSubresource;\n\tbarrierSubresource.aspectMask = baseTexture->GetImageAspect();\n\n\tconst auto renderer = VulkanRenderer::GetInstance();\n\trenderer->draw_endRenderPass();\n\n\trenderer->barrier_image<VulkanRenderer::ANY_TRANSFER | VulkanRenderer::IMAGE_WRITE, VulkanRenderer::TRANSFER_READ>(baseTexture, barrierSubresource, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL);\n\trenderer->barrier_sequentializeTransfer();\n\tvkCmdCopyImageToBuffer(renderer->getCurrentCommandBuffer(), baseTexture->GetImageObj()->m_image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, m_buffer, regionCount, regions);\n\trenderer->barrier_sequentializeTransfer();\n\trenderer->barrier_image<VulkanRenderer::TRANSFER_READ, VulkanRenderer::ANY_TRANSFER | VulkanRenderer::IMAGE_WRITE>(baseTexture, barrierSubresource, baseTexture->GetDefaultLayout());\n\trenderer->barrier_bufferRange<VulkanRenderer::TRANSFER_WRITE, VulkanRenderer::HOST_READ>(m_buffer, m_buffer_offset, m_image_size);\n\n\tm_associatedCommandBufferId = renderer->GetCurrentCommandBufferId();\n\tm_textureView = nullptr;\n\n\trenderer->RequestSubmitSoon();\n\trenderer->RequestSubmitOnIdle();\n}\n'''
rbvk = replace_once(rbvk, old_start, new_start, "D24 split-plane StartTransfer")
rbvk_path.write_text(rbvk, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Blocking helper: repack Vulkan X8_D24 + S8 planes into GX2 D24|S8<<24.
# ---------------------------------------------------------------------------
rb_path = Path("src/Cafe/HW/Latte/Core/LatteTextureReadback.cpp")
rb = rb_path.read_text(encoding="utf-8")
old_blocking = '''bool LatteTextureReadback_ReadbackToLinearBlocking(LatteTextureView* sourceView, uint8* dstPtr, uint32 dstWidth, uint32 dstHeight, uint32 dstPitch)\n{\n\tLatteTextureReadbackInfo* info = g_renderer->texture_createReadback(sourceView);\n\tif (!info)\n\t\treturn false;\n\n\tinfo->StartTransfer();\n\tinfo->ForceFinish();\n\tcemu_assert(info->IsFinished());\n\n\tuint8* data = info->GetData(); // returned pixel format should match Latte format\n\tuint32 bpp = Latte::GetFormatBits(sourceView->baseTexture->format) / 8;\n\tuint32 srcRowBytes = sourceView->baseTexture->width * bpp;\n\tuint32 dstRowBytes = dstWidth * bpp;\n\tfor (uint32 y = 0; y < dstHeight; y++)\n\t\tmemcpy(dstPtr + y * dstPitch * bpp, data + y * srcRowBytes, dstRowBytes);\n\n\tinfo->ReleaseData();\n\tdelete info;\n\treturn true;\n}\n'''
new_blocking = '''bool LatteTextureReadback_ReadbackToLinearBlocking(LatteTextureView* sourceView, uint8* dstPtr, uint32 dstWidth, uint32 dstHeight, uint32 dstPitch)\n{\n\tLatteTextureReadbackInfo* info = g_renderer->texture_createReadback(sourceView);\n\tif (!info)\n\t\treturn false;\n\n\tinfo->StartTransfer();\n\tinfo->ForceFinish();\n\tcemu_assert(info->IsFinished());\n\n\tuint8* data = info->GetData();\n\tif (sourceView->format == Latte::E_GX2SURFFMT::D24_S8_UNORM)\n\t{\n\t\tconst uint32 srcWidth = sourceView->baseTexture->width;\n\t\tconst uint32 srcHeight = sourceView->baseTexture->height;\n\t\tconst uint32 pixelCount = srcWidth * srcHeight;\n\t\tconst uint32* depthPlane = reinterpret_cast<const uint32*>(data);\n\t\tconst uint8* stencilPlane = data + pixelCount * 4u;\n\t\tfor (uint32 y = 0; y < dstHeight; y++)\n\t\t{\n\t\t\tuint32* dstRow = reinterpret_cast<uint32*>(dstPtr + y * dstPitch * 4u);\n\t\t\tfor (uint32 x = 0; x < dstWidth; x++)\n\t\t\t{\n\t\t\t\tconst uint32 i = y * srcWidth + x;\n\t\t\t\tdstRow[x] = (depthPlane[i] & 0x00FFFFFFu) | ((uint32)stencilPlane[i] << 24);\n\t\t\t}\n\t\t}\n\t}\n\telse\n\t{\n\t\tuint32 bpp = Latte::GetFormatBits(sourceView->baseTexture->format) / 8;\n\t\tuint32 srcRowBytes = sourceView->baseTexture->width * bpp;\n\t\tuint32 dstRowBytes = dstWidth * bpp;\n\t\tfor (uint32 y = 0; y < dstHeight; y++)\n\t\t\tmemcpy(dstPtr + y * dstPitch * bpp, data + y * srcRowBytes, dstRowBytes);\n\t}\n\n\tinfo->ReleaseData();\n\tdelete info;\n\treturn true;\n}\n'''
rb = replace_once(rb, old_blocking, new_blocking, "D24 blocking readback repack")
rb_path.write_text(rb, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Guest RAM writeback: support raw tiled HWFMT_8_24 (D24 low24 + S8 high8).
# ---------------------------------------------------------------------------
loader_path = Path("src/Cafe/HW/Latte/Core/LatteTextureLoader.cpp")
loader = loader_path.read_text(encoding="utf-8")
loader_anchor = '''\telse if (hwFormat == Latte::E_HWSURFFMT::HWFMT_32_FLOAT)\n\t{\n'''
loader_insert = '''\telse if (hwFormat == Latte::E_HWSURFFMT::HWFMT_8_24)\n\t{\n\t\tfor (sint32 y = 0; y < textureLoader.height; y++)\n\t\t{\n\t\t\tconst uint32* pixelInput = reinterpret_cast<const uint32*>(linearPixelData + (y * textureLoader.width) * 4);\n\t\t\tfor (sint32 x = 0; x < textureLoader.width; x++)\n\t\t\t{\n\t\t\t\tuint8* outputData = LatteTextureLoader_GetInput(&textureLoader, x, y);\n\t\t\t\t*reinterpret_cast<uint32*>(outputData) = *pixelInput++;\n\t\t\t}\n\t\t}\n\t}\n\telse if (hwFormat == Latte::E_HWSURFFMT::HWFMT_32_FLOAT)\n\t{\n'''
loader = replace_once(loader, loader_anchor, loader_insert, "HWFMT_8_24 tiled readback writer")
loader_path.write_text(loader, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Vulkan upload during the experiment-only main reload: split packed stencil
# into the S8 buffer plane. Normal uploads are untouched unless the flag is set.
# ---------------------------------------------------------------------------
vr_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
vr = vr_path.read_text(encoding="utf-8")
vr = replace_once(
    vr,
    'extern std::atomic_int g_compiling_pipelines;\n',
    'extern std::atomic_int g_compiling_pipelines;\nextern bool g_bayo2F544GuestRoundtripUpload;\n',
    "roundtrip upload extern",
)
vr = replace_once(
    vr,
    '''\tuint32 uploadSize = compressedImageSize;// memRequirements.size;\n\tuint32 uploadAlignment = memRequirements.alignment;\n''',
    '''\tconst bool bayo2F544PackedD24Upload = g_bayo2F544GuestRoundtripUpload &&\n\t\thostTexture->physAddress == 0xF5442800u &&\n\t\thostTexture->format == Latte::E_GX2SURFFMT::D24_S8_UNORM &&\n\t\thostTexture->isDepth;\n\tconst uint32 bayo2F544PixelCount = (uint32)width * (uint32)height;\n\tuint32 uploadSize = bayo2F544PackedD24Upload ? compressedImageSize + bayo2F544PixelCount : compressedImageSize;\n\tuint32 uploadAlignment = memRequirements.alignment;\n''',
    "roundtrip D24 upload allocation",
)
vr = replace_once(
    vr,
    '''\tmemcpy(uploadResv.memPtr, pixelData, compressedImageSize);\n\tvkMemAllocator.FlushReservation(uploadResv);\n''',
    '''\tmemcpy(uploadResv.memPtr, pixelData, compressedImageSize);\n\tif (bayo2F544PackedD24Upload)\n\t{\n\t\tconst uint32* packed = reinterpret_cast<const uint32*>(pixelData);\n\t\tuint8* stencilPlane = reinterpret_cast<uint8*>(uploadResv.memPtr) + compressedImageSize;\n\t\tfor (uint32 i = 0; i < bayo2F544PixelCount; i++)\n\t\t\tstencilPlane[i] = (uint8)(packed[i] >> 24);\n\t\tcemuLog_log(LogType::Force, "[BAYO2_F544_ROUNDTRIP_UPLOAD] size={}x{} packedBytes={} stencilBytes={}", width, height, compressedImageSize, bayo2F544PixelCount);\n\t}\n\tvkMemAllocator.FlushReservation(uploadResv);\n''',
    "roundtrip D24 stencil deinterleave",
)
vr = replace_once(
    vr,
    '''\t\timageRegion[1].bufferOffset = uploadResv.bufferOffset;\n\t\timageRegion[1].imageExtent.width = width;\n''',
    '''\t\timageRegion[1].bufferOffset = uploadResv.bufferOffset + (bayo2F544PackedD24Upload ? compressedImageSize : 0u);\n\t\timageRegion[1].imageExtent.width = width;\n''',
    "roundtrip D24 stencil upload offset",
)
vr_path.write_text(vr, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Bayonetta 2 JP f544 coherence A/B.
# Canonicalize newer 256/64 host depth images through guest tiled RAM in event
# order, then reload the 1280 main image. Exact title/address/shape gate only.
# ---------------------------------------------------------------------------
rt_path = Path("src/Cafe/HW/Latte/Core/LatteRenderTarget.cpp")
rt = rt_path.read_text(encoding="utf-8")
rt = replace_once(
    rt,
    '#include "Cafe/GraphicPack/GraphicPack2.h"\n',
    '#include "Cafe/GraphicPack/GraphicPack2.h"\n#include "Cafe/CafeSystem.h"\n',
    "roundtrip CafeSystem include",
)
rt = replace_once(
    rt,
    'bool hasValidFramebufferAttached = false;\n',
    '''bool hasValidFramebufferAttached = false;\n\nbool g_bayo2F544GuestRoundtripUpload = false;\nstatic uint64 s_bayo2F544RoundtripCount = 0;\n\nstatic bool Bayo2F544GuestRoundtripEnabled()\n{\n\treturn CafeSystem::GetForegroundTitleId() == 0x000500001011B900ULL;\n}\n\nstatic bool Bayo2F544WriteAliasToGuest(LatteTexture* alias)\n{\n\tif (!alias || !alias->baseView || alias->overwriteInfo.hasResolutionOverwrite)\n\t\treturn false;\n\tstd::vector<uint8> packed((size_t)alias->width * (size_t)alias->height * 4u);\n\tif (!LatteTextureReadback_ReadbackToLinearBlocking(alias->baseView, packed.data(), alias->width, alias->height, alias->width))\n\t\treturn false;\n\tLatteTextureDefinition def(alias);\n\tLatteTextureLoader_writeReadbackTextureToMemory(&def, 0, 0, packed.data());\n\tauto* info = alias->sliceMipInfo + alias->GetSliceMipArrayIndex(0, 0);\n\tcemuLog_log(LogType::Force, "[BAYO2_F544_ROUNDTRIP] phase=alias-to-guest event={} size={}x{} pitch={} bytes={}",\n\t\tinfo->lastDynamicUpdate, alias->width, alias->height, alias->pitch, packed.size());\n\treturn true;\n}\n\nstatic void Bayo2F544SyncBeforeMainBind(LatteTexture* mainTexture)\n{\n\tif (!Bayo2F544GuestRoundtripEnabled() || !mainTexture || mainTexture->physAddress != 0xF5442800u ||\n\t\t!mainTexture->isDepth || mainTexture->format != Latte::E_GX2SURFFMT::D24_S8_UNORM ||\n\t\tmainTexture->width != 1280 || mainTexture->height != 720 || mainTexture->pitch != 1280)\n\t\treturn;\n\n\tauto* mainInfo = mainTexture->sliceMipInfo + mainTexture->GetSliceMipArrayIndex(0, 0);\n\tstd::vector<std::pair<uint64, LatteTexture*>> pending;\n\tstd::vector<LatteTexture*> aliases;\n\tLatteTC_LookupTexturesByPhysAddr(mainTexture->physAddress, aliases);\n\tfor (auto* alias : aliases)\n\t{\n\t\tif (!alias || alias == mainTexture || !alias->isDepth || alias->format != mainTexture->format ||\n\t\t\talias->tileMode != mainTexture->tileMode || !alias->sliceMipInfo)\n\t\t\tcontinue;\n\t\tconst bool expectedSmall = (alias->width == 256 && alias->height == 256 && alias->pitch == 256) ||\n\t\t\t(alias->width == 64 && alias->height == 64 && alias->pitch == 64);\n\t\tif (!expectedSmall)\n\t\t\tcontinue;\n\t\tauto* aliasInfo = alias->sliceMipInfo + alias->GetSliceMipArrayIndex(0, 0);\n\t\tif (aliasInfo->lastDynamicUpdate > mainInfo->lastDynamicUpdate)\n\t\t\tpending.emplace_back(aliasInfo->lastDynamicUpdate, alias);\n\t}\n\tif (pending.empty())\n\t\treturn;\n\n\tstd::sort(pending.begin(), pending.end(), [](const auto& a, const auto& b) { return a.first < b.first; });\n\tconst uint64 newestEvent = pending.back().first;\n\tconst uint64 n = ++s_bayo2F544RoundtripCount;\n\tcemuLog_log(LogType::Force, "[BAYO2_F544_ROUNDTRIP] phase=begin n={} mainEvent={} pending={} newestEvent={}",\n\t\tn, mainInfo->lastDynamicUpdate, pending.size(), newestEvent);\n\n\tfor (const auto& item : pending)\n\t{\n\t\tif (!Bayo2F544WriteAliasToGuest(item.second))\n\t\t{\n\t\t\tcemuLog_log(LogType::Force, "[BAYO2_F544_ROUNDTRIP] phase=abort n={} event={} size={}x{} pitch={}",\n\t\t\t\tn, item.first, item.second->width, item.second->height, item.second->pitch);\n\t\t\treturn;\n\t\t}\n\t}\n\n\tg_bayo2F544GuestRoundtripUpload = true;\n\tLatteTexture_ReloadData(mainTexture);\n\tg_bayo2F544GuestRoundtripUpload = false;\n\tmainInfo->lastDynamicUpdate = newestEvent;\n\tcemuLog_log(LogType::Force, "[BAYO2_F544_ROUNDTRIP] phase=main-reload n={} syncedEvent={} effective={}x{}",\n\t\tn, newestEvent, mainTexture->overwriteInfo.hasResolutionOverwrite ? mainTexture->overwriteInfo.width : mainTexture->width,\n\t\tmainTexture->overwriteInfo.hasResolutionOverwrite ? mainTexture->overwriteInfo.height : mainTexture->height);\n}\n''',
    "roundtrip helper state",
)
rt = replace_once(
    rt,
    '''\t\t\t\telse\n\t\t\t\t{\n\t\t\t\t\t// check for texture changes\n\t\t\t\t\tLatteTexture_UpdateDataToLatest(depthBufferView->baseTexture);\n\t\t\t\t}\n\t\t\t\t// set effective size\n''',
    '''\t\t\t\telse\n\t\t\t\t{\n\t\t\t\t\t// check for texture changes\n\t\t\t\t\tLatteTexture_UpdateDataToLatest(depthBufferView->baseTexture);\n\t\t\t\t}\n\t\t\t\tBayo2F544SyncBeforeMainBind(depthBufferView->baseTexture);\n\t\t\t\t// set effective size\n''',
    "roundtrip main-bind trigger",
)
rt_path.write_text(rt, encoding="utf-8", newline="\n")

print("Bayonetta 2 f544 guest-memory roundtrip experiment applied")
