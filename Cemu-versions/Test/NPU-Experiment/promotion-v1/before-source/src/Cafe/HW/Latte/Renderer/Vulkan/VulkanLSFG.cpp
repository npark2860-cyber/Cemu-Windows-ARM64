#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h"
#ifdef CEMU_ENABLE_LSFG
#include "config/CemuConfig.h"
#include "config/ActiveSettings.h"
#include "lsfg_cemu.h"
#include <chrono>

struct LSFGTimingMetric
{
    uint64_t count{};
    double sum{}, maximum{};
    void add(double ms) { ++count; sum += ms; maximum = std::max(maximum, ms); }
    std::string describe() const
    {
        return count ? fmt::format("{:.3f}/{:.3f}/{}", sum / count, maximum, count) : "N/A";
    }
};

struct VulkanLSFGState
{
    LsfgCemu* module{};
    LsfgCemuContext* context{};
    std::array<VkImage, 3> images{};
    std::array<VkImageMemAllocation*, 3> memory{};
    VkExtent2D extent{};
    VkFormat surfaceFormat{VK_FORMAT_UNDEFINED};
    int preset{-1};
    uint32_t flowPercent{100};
    bool failed{}, enabled{}, previousValid{}, generatedPending{}, resetNeeded{}, presentingGenerated{};
    unsigned current{};
    uint64_t frameId{}, generated{}, captures{};
    std::chrono::steady_clock::time_point lastCapture{}, metricsStart{}, lastPresent{};
    uint64_t presents{}, generatedPresents{}, rejectedPresents{}, moduleCalls{}, gapSamples{}, shortGaps{}, longGaps{};
    std::optional<double> displayFps;
    double moduleMs{}, captureSubmitMs{}, presentHostMs{}, overlayWaitMs{}, gapTotalMs{}, gapMaxMs{};
    VkQueryPool realQueries{};
    uint32_t timestampBits{};
    double timestampPeriodNs{};
    struct RealQuerySlot { bool pending{}; uint64_t endCommand{}, epoch{}; };
    std::array<RealQuerySlot, 16> realSlots{};
    int realActive{-1}, boundarySlot{-1};
    uint64_t timingEpoch{}, droppedSamples{}, warmupCalls{}, lastSubmitEndNs{};
    LSFGTimingMetric realGpu, inputGpu, prepassGpu, generationGpu, outputGpu, boundaryGpu;
    LSFGTimingMetric cemuSubmit, cemuWait, submitGap;
    uint64_t lsfgSubmitCalls{};
    double lsfgSubmitMs{}, lsfgWaitMs{};
};

namespace
{
using Clock = std::chrono::steady_clock;
double ElapsedMs(Clock::time_point start) { return std::chrono::duration<double, std::milli>(Clock::now() - start).count(); }

const char* PresetName(int preset)
{
    switch (preset)
    {
    case 0: return "Quality100";
    case 1: return "Performance100";
    case 2: return "Performance75";
    default: return "unprepared";
    }
}

bool TimestampSpan(uint64_t begin, uint64_t end, uint32_t bits, double period, double& ms)
{
    if (!bits || bits > 64 || period <= 0.0) return false;
    const uint64_t mask = bits == 64 ? UINT64_MAX : (uint64_t(1) << bits) - 1;
    const uint64_t ticks = (end - begin) & mask;
    // Ignore inverted/ambiguous intervals instead of logging an enormous wrap.
    if (ticks > mask / 2) return false;
    ms = double(ticks) * period / 1e6;
    return true;
}

void AddModuleGpuPair(LSFGTimingMetric& metric, const LsfgCemuTimingStats& timing, unsigned first)
{
    if ((timing.availability_mask & (3u << first)) != (3u << first)) return;
    double ms{};
    if (TimestampSpan(timing.gpu_ticks[first], timing.gpu_ticks[first + 1],
        timing.timestamp_valid_bits, timing.timestamp_period_ns, ms)) metric.add(ms);
}

void ReportPerformance(VulkanLSFGState& state, bool force = false)
{
    const auto now = Clock::now();
    if (!state.metricsStart.time_since_epoch().count()) { state.metricsStart = now; return; }
    const double seconds = std::chrono::duration<double>(now - state.metricsStart).count();
    if (seconds <= 0.0 || (!force && seconds < 2.0)) return;
    // Use accepted real + generated presents from this same measured interval.
    // Warmup and rejected presents naturally reduce the result. A forced flush
    // closes a partial interval at toggle/resize; it must not publish a spike.
    if (!force) state.displayFps = state.presents / seconds;
    cemuLog_log(LogType::Force,
        "[LSFG-PERF] {} {}x{} {:.2f}s: source_present_fps={:.2f} generated_present_fps={:.2f} accepted_present_fps={:.2f} rejected={} preset={} flow_percent={}",
        state.enabled && !state.failed ? "ON" : "OFF", state.extent.width, state.extent.height, seconds,
        (state.presents - state.generatedPresents) / seconds, state.generatedPresents / seconds, state.presents / seconds, state.rejectedPresents,
        PresetName(state.preset), state.flowPercent);
    const double moduleDivisor = std::max<uint64_t>(1, state.moduleCalls);
    cemuLog_log(LogType::Force,
        "[LSFG-PERF] CPU wall ms: module_batch_avg={:.3f} capture_submit_sum={:.3f} present_host_sum={:.3f} overlay_wait_sum={:.3f} intentional_sleep=0",
        state.moduleMs / moduleDivisor, state.captureSubmitMs, state.presentHostMs, state.overlayWaitMs);
    cemuLog_log(LogType::Force,
        "[LSFG-PERF] Present return gaps ms: mean={:.3f} max={:.3f} under4ms={} over33ms={} (not display scanout timing)",
        state.gapTotalMs / std::max<uint64_t>(1, state.gapSamples), state.gapMaxMs, state.shortGaps, state.longGaps);
    cemuLog_log(LogType::Force,
        "[LSFG-PROFILE] GPU span ms avg/max/n: real={} input_copy={} prepass={} generated={} output_copy={} warmup_excluded={} query_dropped={}",
        state.realGpu.describe(), state.inputGpu.describe(), state.prepassGpu.describe(), state.generationGpu.describe(),
        state.outputGpu.describe(), state.warmupCalls, state.droppedSamples);
    cemuLog_log(LogType::Force,
        "[LSFG-PROFILE] CPU ms: Cemu_vkQueueSubmit_avg/max/n={} LSFG_vkQueueSubmit_sum={:.3f} calls={} Cemu_fence_wait_sum={:.3f} calls={} LSFG_tail_fence_wait_sum={:.3f}",
        state.cemuSubmit.describe(), state.lsfgSubmitMs, state.lsfgSubmitCalls, state.cemuWait.sum, state.cemuWait.count, state.lsfgWaitMs);
    cemuLog_log(LogType::Force,
        "[LSFG-PROFILE] Boundary ms avg/max/n: host_capture_submit_end_to_LSFG_submit={} GPU_real_end_to_prepass_begin={} queue_mutex_hold=N/A(single_render_thread); boundary spans include copies/dependencies, not proven GPU idle",
        state.submitGap.describe(), state.boundaryGpu.describe());
    state.metricsStart = now;
    state.presents = state.generatedPresents = state.rejectedPresents = state.moduleCalls = state.gapSamples = state.shortGaps = state.longGaps = 0;
    state.moduleMs = state.captureSubmitMs = state.presentHostMs = state.overlayWaitMs = state.gapTotalMs = state.gapMaxMs = 0;
    state.realGpu = state.inputGpu = state.prepassGpu = state.generationGpu = state.outputGpu = state.boundaryGpu = {};
    state.cemuSubmit = state.cemuWait = state.submitGap = {};
    state.lsfgSubmitCalls = state.warmupCalls = state.droppedSamples = 0;
    state.lsfgSubmitMs = state.lsfgWaitMs = 0;
}
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
        m_lsfg->displayFps.reset();
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
    state.surfaceFormat = VK_FORMAT_UNDEFINED;
    state.preset = -1;
    state.previousValid = state.generatedPending = false;
    state.current = 0;
    return true;
}

bool VulkanRenderer::lsfgEnsureContext()
{
    auto& state = *m_lsfg;
    auto& chain = GetChainInfo(true);
    const auto extent = chain.getExtent();
    const int preset = std::clamp(GetConfig().lsfg_preset.GetValue(), 0, 2);
    uint32_t flowPercent = preset == 2 ? 75 : 100;
    // The backend's seven-level pyramid needs both internal axes >=128.
    const float divisor = 100.0f / flowPercent;
    if (static_cast<uint32_t>(float(extent.width) / divisor) < 128 ||
        static_cast<uint32_t>(float(extent.height) / divisor) < 128) flowPercent = 100;
    if (extent.width < 128 || extent.height < 128) return false;
    if (state.context && state.extent.width == extent.width && state.extent.height == extent.height &&
        state.surfaceFormat == chain.m_surfaceFormat.format && chain.m_lsfgTransferSource && state.preset == preset) return true;
    state.displayFps.reset();
    if (state.context)
    {
        // Do not mix costs from different dimensions or presets in one window.
        if (state.presents || state.moduleCalls) ReportPerformance(state, true);
        ++state.timingEpoch;
        state.lastPresent = {};
    }
    // Includes all prior Cemu blits that can reference these host-owned images.
    const auto id = GetCurrentCommandBufferId();
    SubmitCommandBuffer();
    WaitCommandBufferFinished(id);
    if (!lsfgReleaseContext())
    {
        lsfgFail("resize", "previous context is still pending");
        return false;
    }
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
    const LsfgCemuContextTuning tuning{sizeof(tuning), preset == 0 ? VK_FALSE : VK_TRUE, flowPercent};
    if (status == LSFG_CEMU_OK) status = lsfg_cemu_set_context_tuning(state.context, &tuning, &error);
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
    state.surfaceFormat = chain.m_surfaceFormat.format;
    state.preset = preset;
    state.flowPercent = flowPercent;
    state.lastCapture = {};
    state.metricsStart = Clock::now();
    cemuLog_log(LogType::Force, "[LSFG] Context prepared {}x{} preset={} flow_percent={} internal_motion={}x{}; no input frames processed",
        extent.width, extent.height, PresetName(preset), flowPercent,
        static_cast<uint32_t>(float(extent.width) / (100.0f / flowPercent)),
        static_cast<uint32_t>(float(extent.height) / (100.0f / flowPercent)));
    return true;
}

void VulkanRenderer::lsfgInitialize()
{
    if (!m_lsfgSupported)
    {
        GetConfig().lsfg_enabled = false;
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
        VkPhysicalDeviceProperties properties{};
        vkGetPhysicalDeviceProperties(m_physicalDevice, &properties);
        uint32_t queueCount{};
        vkGetPhysicalDeviceQueueFamilyProperties(m_physicalDevice, &queueCount, nullptr);
        std::vector<VkQueueFamilyProperties> queues(queueCount);
        vkGetPhysicalDeviceQueueFamilyProperties(m_physicalDevice, &queueCount, queues.data());
        auto& state = *m_lsfg;
        state.timestampBits = queues[m_indices.graphicsFamily].timestampValidBits;
        state.timestampPeriodNs = properties.limits.timestampPeriod;
        if (state.timestampBits && state.timestampPeriodNs > 0.0)
        {
            VkQueryPoolCreateInfo queryInfo{VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO};
            queryInfo.queryType = VK_QUERY_TYPE_TIMESTAMP;
            queryInfo.queryCount = uint32_t(state.realSlots.size()) * 2;
            if (vkCreateQueryPool(m_logicalDevice, &queryInfo, nullptr, &state.realQueries) != VK_SUCCESS)
                cemuLog_log(LogType::Force, "[LSFG-PROFILE] Cemu timestamp allocation failed; GPU real span unavailable");
        }
        LsfgCemuStats stats{sizeof(stats)};
        lsfg_cemu_get_stats(m_lsfg->module, &stats, &error);
        cemuLog_log(LogType::Force, "[LSFG] Startup READY/OFF: shaders={} pipelines={} generated={} borrowed_device={}",
            stats.shader_modules, stats.compute_pipelines, stats.generated_outputs, stats.host_objects_reused);
        cemuLog_log(LogType::Force, "[LSFG-PERF] Target: source >=30 FPS, output 60 FPS with even cadence. Same-queue batched GPU work; render-thread pacing sleep removed.");
        m_lsfg->metricsStart = Clock::now();
        cemuLog_log(LogType::Force, "[LSFG-PROFILE] timestamp_bits={} period_ns={}; query reads add no completion wait. Real spans include GPU timeline gaps; not busy utilization. OFF records diagnostic timestamps only.",
            state.timestampBits, state.timestampPeriodNs);
        lsfgBeginRealFrameTiming();
    }
    catch (const std::exception& e) { lsfgFail("startup", e.what()); }
}

void VulkanRenderer::lsfgCapture()
{
    lsfgEndRealFrameTiming();
    if (!m_lsfg || m_lsfg->failed)
    {
        GetConfig().lsfg_enabled = false;
        return;
    }
    auto& state = *m_lsfg;
    const bool requested = GetConfig().lsfg_enabled.GetValue();
    if (requested != state.enabled)
    {
        ReportPerformance(state, true);
        ++state.timingEpoch;
        state.metricsStart = Clock::now();
        state.lastPresent = {};
        LsfgCemuError error{};
        if (lsfg_cemu_set_enabled(state.module, requested ? VK_TRUE : VK_FALSE, &error) != LSFG_CEMU_OK)
        {
            lsfgFail("toggle", error.message);
            return;
        }
        state.enabled = requested;
        state.displayFps.reset();
        state.previousValid = false;
        state.lastCapture = {};
        cemuLog_log(LogType::Force, "[LSFG] {}: captured={} generated={}", requested ? "ON" : "OFF/passthrough", state.captures, state.generated);
    }
    // OFF performs no image copies, module calls, dispatches, or frame waits.
    if (!requested) return;
    try
    {
        if (!lsfgEnsureContext()) return;
        if (state.resetNeeded)
        {
            LsfgCemuError error{};
            if (lsfg_cemu_reset_history(state.context, &error) != LSFG_CEMU_OK)
            {
                lsfgFail("presentation history reset", error.message);
                return;
            }
            state.resetNeeded = false;
            state.previousValid = false;
        }
        auto& chain = GetChainInfo(true);
        if (chain.swapchainImageIndex == uint32_t(-1) || !chain.hasDefinedSwapchainImage) return;
        const auto now = Clock::now();
        if (state.lastCapture.time_since_epoch().count())
        {
            const double interval = std::chrono::duration<double, std::milli>(now - state.lastCapture).count();
            if (interval > 250.0)
            {
                LsfgCemuError error{};
                if (lsfg_cemu_reset_history(state.context, &error) != LSFG_CEMU_OK)
                {
                    lsfgFail("frame gap history reset", error.message);
                    return;
                }
                state.previousValid = false;
            }
        }
        state.lastCapture = now;
        const auto captureStart = Clock::now();
        draw_endRenderPass();
        Blit(m_state.currentCommandBuffer, chain.m_swapchainImages[chain.swapchainImageIndex], VK_IMAGE_LAYOUT_PRESENT_SRC_KHR, state.extent,
             state.images[state.current], VK_IMAGE_LAYOUT_GENERAL, state.extent, VK_IMAGE_LAYOUT_PRESENT_SRC_KHR, VK_IMAGE_LAYOUT_GENERAL);
        SubmitCommandBuffer();
        // Capture and the module use this same graphics queue. The module's
        // input barriers and final fence order/complete the work without an
        // extra CPU round trip here. Images remain alive through that fence.
        state.captureSubmitMs += ElapsedMs(captureStart);
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
        const auto status = lsfg_cemu_generate_step(state.context, &info, &error);
        state.moduleMs += ElapsedMs(start);
        ++state.moduleCalls;
        LsfgCemuTimingStats timing{sizeof(timing)};
        if (lsfg_cemu_get_timing_stats(state.context, &timing, nullptr) == LSFG_CEMU_OK)
        {
            state.lsfgSubmitCalls += timing.queue_submit_calls;
            state.lsfgSubmitMs += double(timing.queue_submit_cpu_ns) / 1e6;
            state.lsfgWaitMs += double(timing.gpu_wait_cpu_ns) / 1e6;
            if (timing.first_submit_cpu_ns && state.lastSubmitEndNs && timing.first_submit_cpu_ns >= state.lastSubmitEndNs)
                state.submitGap.add(double(timing.first_submit_cpu_ns - state.lastSubmitEndNs) / 1e6);
            if (status == LSFG_CEMU_OK)
            {
                AddModuleGpuPair(state.inputGpu, timing, 0);
                AddModuleGpuPair(state.prepassGpu, timing, 2);
                AddModuleGpuPair(state.generationGpu, timing, 4);
                AddModuleGpuPair(state.outputGpu, timing, 6);
                // The successful module tail fence follows the capture submit
                // on this exact queue, so its query reset/end have executed.
                if (state.realQueries && state.boundarySlot >= 0 && (timing.availability_mask & (1u << 2)))
                {
                    uint64_t end[2]{};
                    if (vkGetQueryPoolResults(m_logicalDevice, state.realQueries, unsigned(state.boundarySlot) * 2 + 1, 1,
                        sizeof(end), end, sizeof(end), VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WITH_AVAILABILITY_BIT) == VK_SUCCESS && end[1])
                    {
                        double ms{};
                        if (TimestampSpan(end[0], timing.gpu_ticks[2], state.timestampBits, state.timestampPeriodNs, ms))
                            state.boundaryGpu.add(ms);
                    }
                }
            }
        }
        if (status == LSFG_CEMU_WARMING)
        {
            ++state.warmupCalls;
            // This real frame remains untouched in the swapchain. Retain it as
            // the previous input and use the normal Cemu overlay/present path.
            state.current ^= 1;
            state.lastCapture = Clock::now();
            cemuLog_log(LogType::Force, "[LSFG] WARMING: source={} original presented", state.frameId);
            return;
        }
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

void VulkanRenderer::lsfgInvalidateSwapchain()
{
    if (!m_lsfg) return;
    auto& state = *m_lsfg;
    ReportPerformance(state, true);
    state.displayFps.reset();
    state.previousValid = false;
    state.generatedPending = false;
    state.resetNeeded = true;
    state.lastCapture = {};
    // Keep the host images and current input index alive: an in-progress
    // generated present may still need to restore the real image after acquire.
    // lsfgEnsureContext drains Cemu commands before replacing these images.
}

std::optional<double> VulkanRenderer::GetFrameGenerationFps() const
{
#ifdef CEMU_ENABLE_NPU
    if(GetConfig().npu_enabled.GetValue()) return npuGetFps();
#endif
    if (!m_lsfg || m_lsfg->failed || !m_lsfg->enabled || !GetConfig().lsfg_enabled.GetValue())
        return std::nullopt;
    return m_lsfg->displayFps;
}

bool VulkanRenderer::lsfgPresentGenerated()
{
    if (!m_lsfg || !m_lsfg->generatedPending || !m_lsfgImguiMainWindow) return false;
    auto& state = *m_lsfg;
    state.generatedPending = false;
    const auto priorGeneration = m_lsfgSwapchainGeneration;
    const auto generatedCommandId = GetCurrentCommandBufferId();
    state.presentingGenerated = true;
    try { SwapBuffer(true); }
    catch (...) { state.presentingGenerated = false; throw; }
    state.presentingGenerated = false;
    // ImGui draw data is reused for the original frame. Complete its previous
    // upload/draw before the backend can reuse any transient vertex buffers.
    const auto overlayWaitStart = Clock::now();
    WaitCommandBufferFinished(generatedCommandId);
    state.overlayWaitMs += ElapsedMs(overlayWaitStart);
    if (!AcquireNextSwapchainImage(true))
    {
        state.previousValid = false;
        state.resetNeeded = true;
        return false;
    }
    auto& chain = GetChainInfo(true);
    // Do not stop the producer for half a frame after completing generation.
    // This comparison build measures the resulting cadence; bursty presents
    // must not be reported as a verified, evenly paced 60 Hz output.
    Blit(m_state.currentCommandBuffer, state.images[state.current], VK_IMAGE_LAYOUT_GENERAL, state.extent,
         chain.m_swapchainImages[chain.swapchainImageIndex], VK_IMAGE_LAYOUT_UNDEFINED, chain.getExtent(),
         VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_PRESENT_SRC_KHR);
    chain.hasDefinedSwapchainImage = true;
    state.current ^= 1;
    m_state.currentPipeline = VK_NULL_HANDLE;
    if (m_lsfgSwapchainGeneration != priorGeneration)
    {
        // Resize/vsync recreation can retire ImGui textures. The original is
        // restored, but this old draw list must not reuse retired texture IDs,
        // even when the new swapchain happens to have the same handle value.
        cemuLog_log(LogType::Force, "[LSFG-SURFACE] Overlay replay skipped: generation {} -> {}; real frame restored, history reset pending",
            priorGeneration, m_lsfgSwapchainGeneration);
        return false;
    }
    return true;
}

void VulkanRenderer::lsfgShutdown()
{
    if (!m_lsfg) return;
    lsfgCollectRealFrameTiming();
    ReportPerformance(*m_lsfg, true);
    LsfgCemuError error{};
    LsfgCemuStats stats{sizeof(stats)};
    if (m_lsfg->module && lsfg_cemu_get_stats(m_lsfg->module, &stats, &error) == LSFG_CEMU_OK)
        cemuLog_log(LogType::Force, "[LSFG] Shutdown: captured={} generated={} dispatches={} resets={}",
            m_lsfg->captures, stats.generated_outputs, stats.recorded_dispatches, stats.history_resets);
    LsfgCemuResourceStats resources{sizeof(resources)};
    if (m_lsfg->module && lsfg_cemu_get_resource_stats(m_lsfg->module, &resources, &error) == LSFG_CEMU_OK)
        cemuLog_log(LogType::Force, "[LSFG] Resources: context_builds={} history_clears={}",
            resources.context_builds, resources.history_clears);
    if (!lsfgReleaseContext()) return;
    if (lsfg_cemu_destroy(&m_lsfg->module, &error) != LSFG_CEMU_OK) return;
    if (m_lsfg->realQueries) vkDestroyQueryPool(m_logicalDevice, m_lsfg->realQueries, nullptr);
    delete m_lsfg;
    m_lsfg = nullptr;
}

void VulkanRenderer::lsfgRecordSubmit(double hostMs, uint64_t endNs)
{
    if (!m_lsfg) return;
    m_lsfg->cemuSubmit.add(hostMs);
    m_lsfg->lastSubmitEndNs = endNs;
}

void VulkanRenderer::lsfgRecordWait(double hostMs)
{
    if (m_lsfg) m_lsfg->cemuWait.add(hostMs);
}

void VulkanRenderer::lsfgCollectRealFrameTiming()
{
    if (!m_lsfg || !m_lsfg->realQueries) return;
    auto& state = *m_lsfg;
    for (unsigned i = 0; i < state.realSlots.size(); ++i)
    {
        auto& slot = state.realSlots[i];
        // Availability alone can be stale until the queued reset has run.
        if (!slot.pending || !HasCommandBufferFinished(slot.endCommand)) continue;
        uint64_t results[4]{};
        const auto status = vkGetQueryPoolResults(m_logicalDevice, state.realQueries, i * 2, 2,
            sizeof(results), results, sizeof(uint64_t) * 2, VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WITH_AVAILABILITY_BIT);
        if (status == VK_SUCCESS && results[1] && results[3] && slot.epoch == state.timingEpoch)
        {
            double ms{};
            if (TimestampSpan(results[0], results[2], state.timestampBits, state.timestampPeriodNs, ms)) state.realGpu.add(ms);
        }
        slot.pending = false;
    }
}

void VulkanRenderer::lsfgBeginRealFrameTiming()
{
    if (!m_lsfg || !m_lsfg->realQueries || m_lsfg->realActive >= 0) return;
    auto& state = *m_lsfg;
    lsfgCollectRealFrameTiming();
    for (unsigned i = 0; i < state.realSlots.size(); ++i)
    {
        auto& slot = state.realSlots[i];
        if (slot.pending) continue;
        draw_endRenderPass();
        vkCmdResetQueryPool(m_state.currentCommandBuffer, state.realQueries, i * 2, 2);
        vkCmdWriteTimestamp(m_state.currentCommandBuffer, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, state.realQueries, i * 2);
        slot.epoch = state.timingEpoch;
        state.realActive = int(i);
        return;
    }
    ++state.droppedSamples;
}

void VulkanRenderer::lsfgEndRealFrameTiming()
{
    if (!m_lsfg) return;
    auto& state = *m_lsfg;
    state.boundarySlot = -1;
    if (!state.realQueries || state.realActive < 0) return;
    const auto index = unsigned(state.realActive);
    vkCmdWriteTimestamp(m_state.currentCommandBuffer, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT, state.realQueries, index * 2 + 1);
    state.realSlots[index].pending = true;
    state.realSlots[index].endCommand = GetCurrentCommandBufferId();
    state.boundarySlot = state.realActive;
    state.realActive = -1;
}

void VulkanRenderer::lsfgRecordPresent(VkResult result, double hostMs)
{
    if (!m_lsfg) return;
    auto& state = *m_lsfg;
    state.presentHostMs += hostMs;
    if (result == VK_SUCCESS || result == VK_SUBOPTIMAL_KHR)
    {
        ++state.presents;
        if (state.presentingGenerated) ++state.generatedPresents;
        const auto now = Clock::now();
        if (state.lastPresent.time_since_epoch().count())
        {
            const double gap = std::chrono::duration<double, std::milli>(now - state.lastPresent).count();
            ++state.gapSamples;
            state.gapTotalMs += gap;
            state.gapMaxMs = std::max(state.gapMaxMs, gap);
            if (gap < 4.0) ++state.shortGaps;
            if (gap > 33.333) ++state.longGaps;
        }
        state.lastPresent = now;
    }
    else ++state.rejectedPresents;
    ReportPerformance(state);
}
#endif
