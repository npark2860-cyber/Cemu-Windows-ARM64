#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h"
#ifdef CEMU_ENABLE_LSFG
#include "config/CemuConfig.h"
#include "config/ActiveSettings.h"
#include "lsfg_cemu.h"
#include <chrono>
#include <thread>

struct VulkanLSFGState
{
    LsfgCemu* module{};
    LsfgCemuContext* context{};
    std::array<VkImage, 3> images{};
    std::array<VkImageMemAllocation*, 3> memory{};
    VkExtent2D extent{};
    bool failed{}, enabled{}, previousValid{}, generatedPending{};
    unsigned current{};
    uint64_t frameId{}, generated{}, captures{};
    std::chrono::steady_clock::time_point lastCapture{}, midpointPresented{};
    double periodMs{33.333}, previousSleepMs{};
};

namespace
{
using Clock = std::chrono::steady_clock;
void ImageBarrier(VkCommandBuffer command, VkImage image, VkImageLayout before, VkImageLayout after)
{
    VkImageMemoryBarrier barrier{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};
    barrier.srcAccessMask = before == VK_IMAGE_LAYOUT_UNDEFINED ? 0 : VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT;
    barrier.dstAccessMask = VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT;
    barrier.oldLayout = before;
    barrier.newLayout = after;
    barrier.srcQueueFamilyIndex = barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    barrier.image = image;
    barrier.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
    vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,
        0, 0, nullptr, 0, nullptr, 1, &barrier);
}

void Blit(VkCommandBuffer command, VkImage source, VkImageLayout beforeSource, VkExtent2D sourceExtent,
          VkImage destination, VkImageLayout beforeDestination, VkExtent2D destinationExtent,
          VkImageLayout afterSource, VkImageLayout afterDestination)
{
    ImageBarrier(command, source, beforeSource, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL);
    ImageBarrier(command, destination, beforeDestination, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL);
    VkImageBlit region{};
    region.srcSubresource = region.dstSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1};
    region.srcOffsets[1] = {(int32_t)sourceExtent.width, (int32_t)sourceExtent.height, 1};
    region.dstOffsets[1] = {(int32_t)destinationExtent.width, (int32_t)destinationExtent.height, 1};
    vkCmdBlitImage(command, source, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
        destination, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &region, VK_FILTER_NEAREST);
    ImageBarrier(command, source, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, afterSource);
    ImageBarrier(command, destination, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, afterDestination);
}

fs::path LosslessPath()
{
    const auto configured = GetConfig().lsfg_dll_path.GetValue();
    if (!configured.empty()) return fs::u8path(configured);
    const auto local = ActiveSettings::GetExecutablePath().parent_path() / L"Lossless.dll";
    if (fs::exists(local)) return local;
    const auto programFiles = _wgetenv(L"ProgramFiles(x86)");
    return programFiles ? fs::path(programFiles) / L"Steam/steamapps/common/Lossless Scaling/Lossless.dll" : local;
}
}

void VulkanRenderer::lsfgFail(const char* stage, const char* message)
{
    cemuLog_log(LogType::Force, "[LSFG] {} failed: {}. Frame generation disabled.", stage, message);
    GetConfig().lsfg_enabled = false;
    if (m_lsfg)
    {
        m_lsfg->failed = true;
        m_lsfg->enabled = false;
        m_lsfg->previousValid = false;
        LsfgCemuError error{};
        if (m_lsfg->module) lsfg_cemu_set_enabled(m_lsfg->module, VK_FALSE, &error);
        // Never reuse or free images after an incomplete submission. Keep them
        // until normal renderer shutdown has established GPU idleness.
        if (m_lsfg->context)
        {
            auto status = lsfg_cemu_drain(m_lsfg->context, 1'000'000'000ULL, &error);
            cemuLog_log(LogType::Force, "[LSFG] Failure drain: {} ({})", lsfg_cemu_status_string(status), error.message);
        }
    }
}

bool VulkanRenderer::lsfgReleaseContext()
{
    if (!m_lsfg) return true;
    auto& state = *m_lsfg;
    LsfgCemuError error{};
    if (lsfg_cemu_destroy_context(&state.context, &error) != LSFG_CEMU_OK)
    {
        cemuLog_log(LogType::Force, "[LSFG] Retaining pending context and images: {}", error.message);
        return false;
    }
    for (size_t i = 0; i < state.images.size(); ++i)
    {
        if (state.images[i]) vkDestroyImage(m_logicalDevice, state.images[i], nullptr);
        if (state.memory[i]) memoryManager->imageMemoryFree(state.memory[i]);
        state.images[i] = VK_NULL_HANDLE;
        state.memory[i] = nullptr;
    }
    state.extent = {};
    state.previousValid = state.generatedPending = false;
    state.current = 0;
    return true;
}

bool VulkanRenderer::lsfgEnsureContext()
{
    auto& state = *m_lsfg;
    auto& chain = GetChainInfo(true);
    const auto extent = chain.getExtent();
    if (extent.width < 128 || extent.height < 128) return false;
    if (state.context && state.extent.width == extent.width && state.extent.height == extent.height) return true;
    // Includes all prior Cemu blits that can reference these host-owned images.
    const auto id = GetCurrentCommandBufferId();
    SubmitCommandBuffer();
    WaitCommandBufferFinished(id);
    if (!lsfgReleaseContext()) return false;
    if (!chain.m_lsfgTransferSource || (chain.m_surfaceFormat.format != VK_FORMAT_R8G8B8A8_UNORM &&
                                       chain.m_surfaceFormat.format != VK_FORMAT_B8G8R8A8_UNORM))
    {
        lsfgFail("swapchain", "SDR UNORM and transfer-source usage are required");
        return false;
    }
    for (const auto format : {chain.m_surfaceFormat.format, VK_FORMAT_R8G8B8A8_UNORM})
    {
        VkFormatProperties properties{};
        vkGetPhysicalDeviceFormatProperties(m_physicalDevice, format, &properties);
        constexpr auto required = VK_FORMAT_FEATURE_BLIT_SRC_BIT | VK_FORMAT_FEATURE_BLIT_DST_BIT;
        if ((properties.optimalTilingFeatures & required) != required)
        {
            lsfgFail("format", "GPU blit conversion is unavailable");
            return false;
        }
    }
    LsfgCemuContextInfo info{sizeof(info), extent.width, extent.height, VK_FORMAT_R8G8B8A8_UNORM};
    LsfgCemuError error{};
    auto status = lsfg_cemu_create_context(state.module, &info, &state.context, &error);
    if (status == LSFG_CEMU_OK) status = lsfg_cemu_prepare_context(state.context, &error);
    if (status != LSFG_CEMU_OK)
    {
        lsfgFail("context prepare", error.message);
        return false;
    }
    try
    {
        for (size_t i = 0; i < state.images.size(); ++i)
        {
            VkImageCreateInfo imageInfo{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
            imageInfo.imageType = VK_IMAGE_TYPE_2D;
            imageInfo.format = VK_FORMAT_R8G8B8A8_UNORM;
            imageInfo.extent = {extent.width, extent.height, 1};
            imageInfo.mipLevels = imageInfo.arrayLayers = 1;
            imageInfo.samples = VK_SAMPLE_COUNT_1_BIT;
            imageInfo.tiling = VK_IMAGE_TILING_OPTIMAL;
            imageInfo.usage = VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT;
            imageInfo.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
            if (vkCreateImage(m_logicalDevice, &imageInfo, nullptr, &state.images[i]) != VK_SUCCESS)
                throw std::runtime_error("host image allocation failed");
            state.memory[i] = memoryManager->imageMemoryAllocate(state.images[i]);
            if (!state.memory[i]) throw std::runtime_error("host image memory unavailable");
        }
        for (auto image : state.images) ImageBarrier(m_state.currentCommandBuffer, image, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_GENERAL);
        const auto initializeId = GetCurrentCommandBufferId();
        SubmitCommandBuffer();
        WaitCommandBufferFinished(initializeId);
    }
    catch (const std::exception& e)
    {
        lsfgFail("host images", e.what());
        return false;
    }
    state.extent = extent;
    state.lastCapture = {};
    state.previousSleepMs = 0;
    cemuLog_log(LogType::Force, "[LSFG] Context prepared {}x{}; no input frames processed", extent.width, extent.height);
    return true;
}

void VulkanRenderer::lsfgInitialize()
{
    if (!m_lsfgSupported)
    {
        cemuLog_log(LogType::Force, "[LSFG] Required Vulkan 1.2 compute features unavailable; passthrough");
        return;
    }
    m_lsfg = new VulkanLSFGState;
    try
    {
        const auto dll = LosslessPath().wstring();
        LsfgCemuCreateInfo info{};
        info.struct_size = sizeof(info);
        info.abi_version = LSFG_CEMU_ABI_VERSION;
        info.instance = m_instance;
        info.physical_device = m_physicalDevice;
        info.device = m_logicalDevice;
        info.queue = m_graphicsQueue;
        info.queue_family_index = m_indices.graphicsFamily;
        info.get_instance_proc_addr = vkGetInstanceProcAddr;
        info.get_device_proc_addr = vkGetDeviceProcAddr;
        info.lossless_dll_path = dll.c_str();
        info.gpu_wait_timeout_ns = 5'000'000'000ULL;
        info.timeline_semaphore_enabled = VK_TRUE;
        info.shader_storage_image_extended_formats_enabled = VK_TRUE;
        LsfgCemuError error{};
        auto status = lsfg_cemu_create(&info, &m_lsfg->module, &error);
        if (status == LSFG_CEMU_OK) status = lsfg_cemu_prepare(m_lsfg->module, &error);
        if (status != LSFG_CEMU_OK) { lsfgFail("startup prepare", error.message); return; }
        if (!lsfgEnsureContext()) return;
        LsfgCemuStats stats{sizeof(stats)};
        lsfg_cemu_get_stats(m_lsfg->module, &stats, &error);
        cemuLog_log(LogType::Force, "[LSFG] Startup READY/OFF: shaders={} pipelines={} generated={} borrowed_device={}",
            stats.shader_modules, stats.compute_pipelines, stats.generated_outputs, stats.host_objects_reused);
    }
    catch (const std::exception& e) { lsfgFail("startup", e.what()); }
}

void VulkanRenderer::lsfgCapture()
{
    if (!m_lsfg || m_lsfg->failed) return;
    auto& state = *m_lsfg;
    const bool requested = GetConfig().lsfg_enabled.GetValue();
    if (requested != state.enabled)
    {
        LsfgCemuError error{};
        lsfg_cemu_set_enabled(state.module, requested ? VK_TRUE : VK_FALSE, &error);
        state.enabled = requested;
        state.previousValid = false;
        state.lastCapture = {};
        state.previousSleepMs = 0;
        cemuLog_log(LogType::Force, "[LSFG] {}: captured={} generated={}", requested ? "ON" : "OFF/passthrough", state.captures, state.generated);
    }
    // OFF performs no image copies, module calls, dispatches, or frame waits.
    if (!requested) return;
    try
    {
        if (!lsfgEnsureContext()) return;
        auto& chain = GetChainInfo(true);
        if (chain.swapchainImageIndex == uint32_t(-1) || !chain.hasDefinedSwapchainImage) return;
        const auto now = Clock::now();
        if (state.lastCapture.time_since_epoch().count())
        {
            const double interval = std::chrono::duration<double, std::milli>(now - state.lastCapture).count();
            if (interval > 250.0)
            {
                LsfgCemuError error{};
                lsfg_cemu_reset_history(state.context, &error);
                state.previousValid = false;
            }
            else state.periodMs = std::clamp(interval - state.previousSleepMs, 8.333, 100.0);
        }
        state.lastCapture = now;
        state.previousSleepMs = 0;
        draw_endRenderPass();
        Blit(m_state.currentCommandBuffer, chain.m_swapchainImages[chain.swapchainImageIndex], VK_IMAGE_LAYOUT_PRESENT_SRC_KHR, state.extent,
             state.images[state.current], VK_IMAGE_LAYOUT_GENERAL, state.extent, VK_IMAGE_LAYOUT_PRESENT_SRC_KHR, VK_IMAGE_LAYOUT_GENERAL);
        const auto captureId = GetCurrentCommandBufferId();
        SubmitCommandBuffer();
        WaitCommandBufferFinished(captureId);
        ++state.captures;
        ++state.frameId;
        if (!state.previousValid)
        {
            state.previousValid = true;
            state.current ^= 1;
            return;
        }
        const auto start = Clock::now();
        LsfgCemuGenerateInfo info{};
        info.struct_size = sizeof(info);
        info.previous_image = state.images[state.current ^ 1];
        info.current_image = state.images[state.current];
        info.output_image = state.images[2];
        info.previous_frame_id = state.frameId - 1;
        info.current_frame_id = state.frameId;
        LsfgCemuError error{};
        const auto status = lsfg_cemu_generate(state.context, &info, &error);
        if (status != LSFG_CEMU_OK) { lsfgFail("generate", error.message); return; }
        const double ms = std::chrono::duration<double, std::milli>(Clock::now() - start).count();
        state.lastCapture = Clock::now(); // Exclude module work from the native-period estimate.
        ++state.generated;
        if (state.generated <= 4 || state.generated % 120 == 0)
            cemuLog_log(LogType::Force, "[LSFG] Generated frame {}: {:.3f} ms ({}x{})", state.generated, ms, state.extent.width, state.extent.height);
        Blit(m_state.currentCommandBuffer, state.images[2], VK_IMAGE_LAYOUT_GENERAL, state.extent,
             chain.m_swapchainImages[chain.swapchainImageIndex], VK_IMAGE_LAYOUT_PRESENT_SRC_KHR, state.extent,
             VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_PRESENT_SRC_KHR);
        state.generatedPending = true;
    }
    catch (const std::exception& e) { lsfgFail("frame capture", e.what()); }
}

bool VulkanRenderer::lsfgPresentGenerated()
{
    if (!m_lsfg || !m_lsfg->generatedPending || !m_lsfgImguiMainWindow) return false;
    auto& state = *m_lsfg;
    state.generatedPending = false;
    const auto generatedCommandId = GetCurrentCommandBufferId();
    SwapBuffer(true);
    // ImGui draw data is reused for the original frame. Complete its previous
    // upload/draw before the backend can reuse any transient vertex buffers.
    WaitCommandBufferFinished(generatedCommandId);
    state.midpointPresented = Clock::now();
    if (!AcquireNextSwapchainImage(true))
    {
        state.previousValid = false;
        return false;
    }
    auto& chain = GetChainInfo(true);
    const auto sleepStart = Clock::now();
    std::this_thread::sleep_until(state.midpointPresented + std::chrono::microseconds((int64_t)(state.periodMs * 500.0)));
    state.previousSleepMs = std::chrono::duration<double, std::milli>(Clock::now() - sleepStart).count();
    Blit(m_state.currentCommandBuffer, state.images[state.current], VK_IMAGE_LAYOUT_GENERAL, state.extent,
         chain.m_swapchainImages[chain.swapchainImageIndex], VK_IMAGE_LAYOUT_UNDEFINED, chain.getExtent(),
         VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_PRESENT_SRC_KHR);
    chain.hasDefinedSwapchainImage = true;
    state.current ^= 1;
    m_state.currentPipeline = VK_NULL_HANDLE;
    return true;
}

void VulkanRenderer::lsfgShutdown()
{
    if (!m_lsfg) return;
    LsfgCemuError error{};
    LsfgCemuStats stats{sizeof(stats)};
    if (m_lsfg->module && lsfg_cemu_get_stats(m_lsfg->module, &stats, &error) == LSFG_CEMU_OK)
        cemuLog_log(LogType::Force, "[LSFG] Shutdown: captured={} generated={} dispatches={} resets={}",
            m_lsfg->captures, stats.generated_outputs, stats.recorded_dispatches, stats.history_resets);
    if (!lsfgReleaseContext()) return;
    if (lsfg_cemu_destroy(&m_lsfg->module, &error) != LSFG_CEMU_OK) return;
    delete m_lsfg;
    m_lsfg = nullptr;
}
#endif
