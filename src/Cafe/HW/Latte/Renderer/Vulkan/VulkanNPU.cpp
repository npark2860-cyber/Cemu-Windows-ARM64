#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h"
#ifdef CEMU_ENABLE_NPU
#include "config/CemuConfig.h"
#include "config/ActiveSettings.h"
#include "Cafe/HW/Latte/Core/LatteOverlay.h"
#include "npu_cemu.h"
#include <fstream>
#include <chrono>

struct NpuHostTiming {
    double sum{},maximum{};uint64_t count{};
    void add(double ms) {sum+=ms;maximum=std::max(maximum,ms);++count;}
    double average() const {return count?sum/double(count):0.0;}
};
struct VulkanNPUState {
    HMODULE library{};
    CemuNpuApi api{sizeof(CemuNpuApi)};
    CemuNpu* context{};
    VkExtent2D processingExtent{1920,1080};
    bool failed{},enabled{},eligible{},pending{},presenting{},unsupportedLogged{};
    std::string failureReason;
    uint64_t frameId{},presents{},generatedPresents{},rejected{};
    VkImage realImage{};
    std::optional<double> displayFps;
    std::chrono::steady_clock::time_point lastCapture{},intervalStart{};
    CemuNpuStats previous{};
    NpuHostTiming captureSubmit,moduleProcess,generatedAcquire,sourceThrottle,imageFence,queueLimit,queuePresent;
};

namespace {
using NpuClock=std::chrono::steady_clock;
void NpuBarrier(VkCommandBuffer command,VkImage image,VkImageLayout before,VkImageLayout after) {
    VkImageMemoryBarrier barrier{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};
    barrier.srcAccessMask=before==VK_IMAGE_LAYOUT_UNDEFINED?0:VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT;
    barrier.dstAccessMask=VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT;
    barrier.oldLayout=before;barrier.newLayout=after;barrier.image=image;
    barrier.srcQueueFamilyIndex=barrier.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;
    barrier.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
    vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,0,0,nullptr,0,nullptr,1,&barrier);
}
void NpuBlit(VkCommandBuffer command,VkImage source,VkImageLayout beforeSource,VkExtent2D sourceSize,
    VkImage destination,VkImageLayout beforeDestination,VkExtent2D destinationSize) {
    NpuBarrier(command,source,beforeSource,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL);
    NpuBarrier(command,destination,beforeDestination,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL);
    VkImageBlit blit{};blit.srcSubresource=blit.dstSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1};
    blit.srcOffsets[1]={int32_t(sourceSize.width),int32_t(sourceSize.height),1};
    blit.dstOffsets[1]={int32_t(destinationSize.width),int32_t(destinationSize.height),1};
    const bool scaled=sourceSize.width!=destinationSize.width || sourceSize.height!=destinationSize.height;
    vkCmdBlitImage(command,source,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,destination,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,1,&blit,scaled?VK_FILTER_LINEAR:VK_FILTER_NEAREST);
    NpuBarrier(command,source,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,beforeSource);
    NpuBarrier(command,destination,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,beforeDestination==VK_IMAGE_LAYOUT_UNDEFINED?VK_IMAGE_LAYOUT_PRESENT_SRC_KHR:beforeDestination);
}
void NpuReport(VulkanNPUState& state,bool force=false) {
    const auto now=NpuClock::now();
    if(!state.intervalStart.time_since_epoch().count()) {state.intervalStart=now;return;}
    const double seconds=std::chrono::duration<double>(now-state.intervalStart).count();
    if(seconds<=0 || (!force && seconds<2)) return;
    if(!force && state.enabled && state.eligible) state.displayFps=double(state.presents)/seconds;
    CemuNpuStats stats{};if(state.context) state.api.stats(state.context,&stats);
    const auto& prior=state.previous;
    const double runs=double(std::max<uint64_t>(1,stats.npuRuns-prior.npuRuns));
    const double pre=double(std::max<uint64_t>(1,stats.preGpuSamples-prior.preGpuSamples));
    const double post=double(std::max<uint64_t>(1,stats.postGpuSamples-prior.postGpuSamples));
    cemuLog_log(LogType::Force,"[NPU-PERF] {} eligible={} accepted_present_fps={:.2f} real_present_fps={:.2f} generated_present_fps={:.2f} rejected={} submitted={} completed={} stale={} no_slot={}; one-frame delay; scanout cadence unverified",
        state.enabled?"ON":"OFF",state.eligible,state.presents/seconds,(state.presents-state.generatedPresents)/seconds,state.generatedPresents/seconds,state.rejected,
        stats.submitted-prior.submitted,stats.completed-prior.completed,stats.stale-prior.stale,stats.noSlot-prior.noSlot);
    cemuLog_log(LogType::Force,"[NPU-PROFILE] worker NPU_Run_avg_ms={:.3f} input_fence_wait_sum_ms={:.3f} queue_start_delay_sum_ms={:.3f} runs={}; GPU_downsample_avg_ms={:.3f} motion_avg_ms={:.3f} warp_pack_avg_ms={:.3f} compose_avg_ms={:.3f} pre_samples={} post_samples={} queue_submit_sum_ms={:.3f}; render_thread_NPU_wait=0 queue_owner=render_thread",
        double(stats.npuRunUs-prior.npuRunUs)/1000/runs,double(stats.inputWaitUs-prior.inputWaitUs)/1000,double(stats.workerStartUs-prior.workerStartUs)/1000,stats.npuRuns-prior.npuRuns,
        (stats.downsampleMs-prior.downsampleMs)/pre,(stats.motionMs-prior.motionMs)/pre,(stats.packMs-prior.packMs)/pre,(stats.composeMs-prior.composeMs)/post,
        stats.preGpuSamples-prior.preGpuSamples,stats.postGpuSamples-prior.postGpuSamples,stats.submitMs-prior.submitMs);
    cemuLog_log(LogType::Force,"[NPU-HOST] ms avg/max/n: capture_submit={:.3f}/{:.3f}/{} module_process={:.3f}/{:.3f}/{} generated_acquire={:.3f}/{:.3f}/{} source_throttle={:.3f}/{:.3f}/{} image_available_fence={:.3f}/{:.3f}/{} queue_limit={:.3f}/{:.3f}/{} vkQueuePresentKHR={:.3f}/{:.3f}/{}; overlay_reupload=0 explicit_generated_fence_wait=0; maxima can include resize",
        state.captureSubmit.average(),state.captureSubmit.maximum,state.captureSubmit.count,
        state.moduleProcess.average(),state.moduleProcess.maximum,state.moduleProcess.count,
        state.generatedAcquire.average(),state.generatedAcquire.maximum,state.generatedAcquire.count,
        state.sourceThrottle.average(),state.sourceThrottle.maximum,state.sourceThrottle.count,
        state.imageFence.average(),state.imageFence.maximum,state.imageFence.count,
        state.queueLimit.average(),state.queueLimit.maximum,state.queueLimit.count,
        state.queuePresent.average(),state.queuePresent.maximum,state.queuePresent.count);
    state.captureSubmit={};state.moduleProcess={};state.generatedAcquire={};state.sourceThrottle={};state.imageFence={};state.queueLimit={};state.queuePresent={};
    state.previous=stats;state.intervalStart=now;state.presents=state.generatedPresents=state.rejected=0;
}
}

void VulkanRenderer::npuInitialize() {
    m_npu=new VulkanNPUState;
    auto& state=*m_npu;
    try {
        if(!m_npuSupported) throw std::runtime_error("Vulkan compute queue and extended storage image formats are required");
        const bool performance=GetConfig().npu_processing_height.GetValue()==720;
        state.processingExtent=performance?VkExtent2D{1280,720}:VkExtent2D{1920,1080};
        for(const auto format:{VK_FORMAT_R8G8B8A8_UNORM,VK_FORMAT_B8G8R8A8_UNORM}) {
            VkFormatProperties properties{};vkGetPhysicalDeviceFormatProperties(m_physicalDevice,format,&properties);
            constexpr auto required=VK_FORMAT_FEATURE_BLIT_SRC_BIT|VK_FORMAT_FEATURE_BLIT_DST_BIT|VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT;
            if((properties.optimalTilingFeatures&required)!=required) throw std::runtime_error("NPU capture/display blit format unavailable");
        }
        // Keep the app-local QNN dependencies beside Cemu's
        // executable, matching the tested Windows loader/skel deployment layout.
        const auto directory=ActiveSettings::GetExecutablePath().parent_path();
        std::ifstream file(directory/L"rpc-path.txt");std::string rpcLine;std::getline(file,rpcLine);
        if(!rpcLine.empty() && rpcLine.back()=='\r') rpcLine.pop_back();
        if(rpcLine.empty()) throw std::runtime_error("Missing rpc-path.txt beside the NPU runtime");
        const auto rpc=fs::u8path(rpcLine).wstring();
        state.library=LoadLibraryExW((directory/L"cemu_npu.dll").c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
        if(!state.library) throw std::runtime_error(fmt::format("NPU module load failed, Win32 {}",GetLastError()));
        auto getApi=reinterpret_cast<CemuNpuGetApi>(GetProcAddress(state.library,"cemu_npu_get_api"));
        if(!getApi || getApi(CEMU_NPU_ABI,&state.api) || state.api.abi!=CEMU_NPU_ABI) throw std::runtime_error("NPU module ABI mismatch");
        const auto path=directory.wstring();
        CemuNpuCreateInfo info{sizeof(info),CEMU_NPU_ABI,m_instance,m_physicalDevice,m_logicalDevice,m_graphicsQueue,uint32_t(m_indices.graphicsFamily),vkGetInstanceProcAddr,path.c_str(),rpc.c_str(),state.processingExtent.height};
        char error[1024]{};
        if(state.api.create(&info,&state.context,error,sizeof(error))) throw std::runtime_error(error);
        state.intervalStart=NpuClock::now();
        cemuLog_log(LogType::Force,"[NPU] READY/OFF: ANVIL U8 NHWC processing={}x{}, window-sized SDR output, 3 shared slots; QNN worker and borrowed Vulkan queue. No inference at startup. One-frame buffering, cached block motion and immutable overlay replay.",state.processingExtent.width,state.processingExtent.height);
    } catch(const std::exception& error) {
        state.failed=true;state.failureReason=error.what();GetConfig().npu_enabled=false;
        cemuLog_log(LogType::Force,"[NPU] Startup unavailable: {}. Original frames remain available.",error.what());
        LatteOverlay_pushNotification(_tr("NPU FG initialization failed. Showing original frames; see log.txt."),8000);
    }
}

void VulkanRenderer::npuInvalidate() {
    if(!m_npu) return;
    auto& state=*m_npu;NpuReport(state,true);
    if(state.context) state.api.reset(state.context);
    state.frameId=0;state.pending=false;state.displayFps.reset();state.lastCapture={};state.eligible=false;
    // Keep realImage and all module resources alive for an in-progress generated
    // present restoring its buffered real frame across swapchain recreation.
}

void VulkanRenderer::npuCapture() {
    if(!m_npu || m_npu->failed) {
        if(m_npu && GetConfig().npu_enabled.GetValue()) {
            cemuLog_log(LogType::Force,"[NPU] Enable rejected: {}",m_npu->failureReason);
            LatteOverlay_pushNotification(_tr("NPU FG unavailable: initialization failed. See log.txt. Showing original frames."),8000);
        }
        GetConfig().npu_enabled=false;return;
    }
    auto& state=*m_npu;
    const bool requested=GetConfig().npu_enabled.GetValue();
    if(requested!=state.enabled) {
        npuInvalidate();state.enabled=requested;state.unsupportedLogged=false;
        cemuLog_log(LogType::Force,"[NPU] {}: history reset; no per-frame inference wait",requested?"ON (one-frame buffered)":"OFF/passthrough");
    }
    if(!requested) return; // No frame copies, dispatches, NPU Run, or waits while OFF.
    try {
        auto& chain=GetChainInfo(true);const auto extent=chain.getExtent();
        const bool supportedSize=extent.width>0 && extent.height>0;
        const bool supported=supportedSize && chain.m_npuTransferSource && chain.m_surfaceFormat.colorSpace==VK_COLOR_SPACE_SRGB_NONLINEAR_KHR &&
            (chain.m_surfaceFormat.format==VK_FORMAT_R8G8B8A8_UNORM || chain.m_surfaceFormat.format==VK_FORMAT_B8G8R8A8_UNORM);
        if(!supported) {
            if(state.eligible) npuInvalidate();
            if(!state.unsupportedLogged) {
                cemuLog_log(LogType::Force,"[NPU] Passthrough at {}x{} format={}; a nonzero SDR UNORM output with transfer-source support is required",extent.width,extent.height,uint32_t(chain.m_surfaceFormat.format));
                LatteOverlay_pushNotification(_tr("NPU FG: current output format is unsupported. Showing original frames."),5000);
            }
            state.unsupportedLogged=true;state.eligible=false;state.displayFps.reset();return;
        }
        state.unsupportedLogged=false;state.eligible=true;
        if(chain.swapchainImageIndex==uint32_t(-1) || !chain.hasDefinedSwapchainImage) return;
        const auto now=NpuClock::now();
        if(state.lastCapture.time_since_epoch().count() && now-state.lastCapture>std::chrono::milliseconds(250)) {npuInvalidate();state.eligible=true;}
        state.lastCapture=now;const auto id=++state.frameId;
        draw_endRenderPass();
        const auto capture=state.api.captureImage(state.context,id);
        if(!capture) throw std::runtime_error("NPU capture image unavailable");
        NpuBlit(m_state.currentCommandBuffer,chain.m_swapchainImages[chain.swapchainImageIndex],VK_IMAGE_LAYOUT_PRESENT_SRC_KHR,extent,capture,VK_IMAGE_LAYOUT_GENERAL,state.processingExtent);
        const auto captureSubmitStart=NpuClock::now();
        SubmitCommandBuffer(); // Same queue; no host wait for capture or preprocessing.
        state.captureSubmit.add(std::chrono::duration<double,std::milli>(NpuClock::now()-captureSubmitStart).count());
        CemuNpuFrame frame{};char error[1024]{};
        const auto processStart=NpuClock::now();
        if(state.api.process(state.context,id,&frame,error,sizeof(error))) throw std::runtime_error(error);
        state.moduleProcess.add(std::chrono::duration<double,std::milli>(NpuClock::now()-processStart).count());
        state.realImage=frame.realImage;state.pending=frame.generatedImage!=VK_NULL_HANDLE;
        const auto display=state.pending?frame.generatedImage:frame.realImage;
        NpuBlit(m_state.currentCommandBuffer,display,VK_IMAGE_LAYOUT_GENERAL,state.processingExtent,chain.m_swapchainImages[chain.swapchainImageIndex],VK_IMAGE_LAYOUT_PRESENT_SRC_KHR,extent);
        if(id<=3) cemuLog_log(LogType::Force,"[NPU] Capture {} -> real {} generated={} processing={}x{} output={}x{} (capture 2 repeats real 1 once to establish buffering)",id,frame.realId,state.pending,state.processingExtent.width,state.processingExtent.height,extent.width,extent.height);
    } catch(const std::exception& error) {
        state.failed=true;state.enabled=false;state.pending=false;state.displayFps.reset();GetConfig().npu_enabled=false;
        state.failureReason=error.what();
        state.api.reset(state.context);
        cemuLog_log(LogType::Force,"[NPU] Frame path failed: {}. Disabled; resources retained until normal shutdown.",error.what());
        LatteOverlay_pushNotification(_tr("NPU FG stopped after an error. Showing original frames; see log.txt."),8000);
    }
}

bool VulkanRenderer::npuPresentGenerated() {
    if(!m_npu || !m_npu->pending || !m_npuImguiMainWindow) return false;
    auto& state=*m_npu;state.pending=false;
    const auto generation=m_npuSwapchainGeneration;
    state.presenting=true;
    try {SwapBuffer(true);} catch(...) {state.presenting=false;throw;}
    state.presenting=false;
    // The second overlay draw reads the same immutable vertex/index upload.
    // No host overwrite occurs here, so no generated-frame fence wait is needed.
    // Normal source-frame throttling and the existing ImGui ring protect reuse
    // on future frames. Swapchain recreation still drains the GPU and skips replay.
    const auto acquireStart=NpuClock::now();
    const bool acquired=AcquireNextSwapchainImage(true);
    state.generatedAcquire.add(std::chrono::duration<double,std::milli>(NpuClock::now()-acquireStart).count());
    if(!acquired) {npuInvalidate();return false;}
    auto& chain=GetChainInfo(true);
    NpuBlit(m_state.currentCommandBuffer,state.realImage,VK_IMAGE_LAYOUT_GENERAL,state.processingExtent,
        chain.m_swapchainImages[chain.swapchainImageIndex],VK_IMAGE_LAYOUT_UNDEFINED,chain.getExtent());
    chain.hasDefinedSwapchainImage=true;m_state.currentPipeline=VK_NULL_HANDLE;
    if(generation!=m_npuSwapchainGeneration) {cemuLog_log(LogType::Force,"[NPU] Resize during generated present: buffered real restored; old overlay replay skipped");return false;}
    return true;
}

bool VulkanRenderer::npuIsGeneratedPresent() const {
    return m_npu && m_npu->presenting;
}
void VulkanRenderer::npuRecordPresentTiming(double throttleMs,double fenceMs,double limitMs,double presentMs) {
    if(!m_npu || !m_npu->enabled || !m_npu->eligible || m_npu->failed) return;
    auto& state=*m_npu;
    if(!state.presenting) state.sourceThrottle.add(throttleMs);
    state.imageFence.add(fenceMs);state.queueLimit.add(limitMs);state.queuePresent.add(presentMs);
}
void VulkanRenderer::npuRecordPresent(VkResult result) {
    if(!m_npu || !m_npu->enabled || !m_npu->eligible || m_npu->failed) return;
    if(result==VK_SUCCESS || result==VK_SUBOPTIMAL_KHR) {++m_npu->presents;if(m_npu->presenting) ++m_npu->generatedPresents;}
    else ++m_npu->rejected;
    NpuReport(*m_npu);
}
std::optional<double> VulkanRenderer::GetFrameGenerationFps() const { return npuGetFps(); }
std::optional<double> VulkanRenderer::npuGetFps() const {
    if(!m_npu || m_npu->failed || !m_npu->eligible || !m_npu->enabled || !GetConfig().npu_enabled.GetValue()) return std::nullopt;
    return m_npu->displayFps;
}
void VulkanRenderer::npuShutdown() {
    if(!m_npu) return;
    NpuReport(*m_npu,true);
    if(m_npu->context) m_npu->api.destroy(m_npu->context);
    if(m_npu->library) FreeLibrary(m_npu->library);
    delete m_npu;m_npu=nullptr;
}
#endif
