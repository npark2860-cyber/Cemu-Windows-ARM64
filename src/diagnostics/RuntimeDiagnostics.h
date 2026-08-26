#pragma once

#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <string_view>

namespace RuntimeDiagnostics
{
enum class Flag : uint16_t
{
    JitBlockLifecycle, GuestHostMapping, BranchPatching, ReadyReICache, JitExecutionEntry, Arm64ExceptionContext, GuestMemoryAccess,
    CommandBufferLifecycle, QueueSubmit, FenceLifecycle, SemaphoreFlow, SubmitCompletion, DeviceLostSubmitError,
    PipelineCache, PipelineCreation, PipelineFailure, PipelineStateSnapshot, ShaderHashAssociation, PipelineCacheMismatch,
    ShaderCreation, ShaderVS, ShaderPS, ShaderGS, ShaderAuxHash, ShaderInterface, GLSLCompileFailure, SPIRVCompileFailure, DumpFailedShader, DumpEveryShader,
    RenderPassBeginEnd, FBOChanges, AttachmentUsage, LoadStoreBehavior, RenderTargetAliasing,
    PipelineBarriers, RAWDependency, WAWDependency, SelfDependency, RenderPassSplit, SynchronizationSummary,
    FeedbackSupport, FeedbackUse, FeedbackFallback, FeedbackSelfDependency, ImageLayoutTransition, FeedbackPassSplit,
    TextureLifecycle, TextureViewLifecycle, TextureCache, TextureAliasing, SurfaceInvalidation, SuspiciousTextureState,
    VPAD, KPAD, ControllerSlot, PlayerIndex, ChannelMapping, ConnectDisconnect, InputReadSummary,
    FrameTiming, LatteThreadTiming, DrawCallCount, PipelineCompileTime, PerfPipelineCache, BarrierCount, RenderPassCount, QueueSubmitCount, UploadStallTiming, PresentTiming,
    GpuTimestamp, CpuWaitBreakdown, DescriptorStats, MemoryUploadStats, JitPerformance, HitchTrigger, DiagnosticOverhead, SummaryOnExit,
    Count
};

inline constexpr size_t kFlagCount = static_cast<size_t>(Flag::Count);
inline std::array<std::atomic_bool, kFlagCount> g_flags{};
inline std::atomic_uint32_t g_hitchThresholdMs{50};

// A checkbox is selectable only when this diagnostic edition has a concrete
// non-UI runtime consumer for it. This prevents visually checked controls from
// silently collapsing into unrelated legacy experiment switches.
inline bool IsImplemented(Flag flag)
{
    switch (flag)
    {
    // ARM64 / JIT
    case Flag::JitBlockLifecycle:
    case Flag::GuestHostMapping:
    case Flag::BranchPatching:
    case Flag::ReadyReICache:
    case Flag::JitExecutionEntry:
    case Flag::Arm64ExceptionContext:
    case Flag::GuestMemoryAccess:
    case Flag::JitPerformance:

    // Vulkan / pipeline diagnostics
    case Flag::QueueSubmit:
    case Flag::PipelineCache:
    case Flag::PipelineCreation:
    case Flag::PipelineFailure:
    case Flag::PipelineStateSnapshot:
    case Flag::ShaderHashAssociation:
    case Flag::ShaderVS:
    case Flag::ShaderPS:
    case Flag::ShaderGS:
    case Flag::ShaderAuxHash:

    // Render-target / synchronization diagnostics
    case Flag::RenderPassBeginEnd:
    case Flag::PipelineBarriers:
    case Flag::RAWDependency:
    case Flag::WAWDependency:
    case Flag::SelfDependency:
    case Flag::RenderPassSplit:
    case Flag::SynchronizationSummary:

    // Performance diagnostics
    case Flag::FrameTiming:
    case Flag::DrawCallCount:
    case Flag::PipelineCompileTime:
    case Flag::QueueSubmitCount:
    case Flag::PresentTiming:
    case Flag::GpuTimestamp:
    case Flag::CpuWaitBreakdown:
    case Flag::DescriptorStats:
    case Flag::MemoryUploadStats:
    case Flag::HitchTrigger:
    case Flag::DiagnosticOverhead:
    case Flag::SummaryOnExit:
        return true;
    default:
        return false;
    }
}

inline bool Enabled(Flag flag)
{
    return IsImplemented(flag) && g_flags[static_cast<size_t>(flag)].load(std::memory_order_relaxed);
}
inline void SetEnabled(Flag flag, bool enabled)
{
    g_flags[static_cast<size_t>(flag)].store(IsImplemented(flag) ? enabled : false, std::memory_order_relaxed);
}
inline void SetAll(bool enabled)
{
    for (size_t i = 0; i < kFlagCount; ++i)
    {
        const auto flag = static_cast<Flag>(i);
        g_flags[i].store(IsImplemented(flag) ? enabled : false, std::memory_order_relaxed);
    }
}
inline bool AnyEnabled()
{
    for (size_t i = 0; i < kFlagCount; ++i)
        if (Enabled(static_cast<Flag>(i)))
            return true;
    return false;
}
inline uint64_t NowNs(){ return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count()); }

struct AccumStat { std::atomic_uint64_t count{0}; std::atomic_uint64_t totalNs{0}; std::atomic_uint64_t maxNs{0}; };
inline void UpdateMax(std::atomic_uint64_t& target, uint64_t value){ uint64_t old=target.load(std::memory_order_relaxed); while(old<value && !target.compare_exchange_weak(old,value,std::memory_order_relaxed)){} }
inline void AddAccum(AccumStat& stat,uint64_t ns){ stat.count.fetch_add(1,std::memory_order_relaxed); stat.totalNs.fetch_add(ns,std::memory_order_relaxed); UpdateMax(stat.maxNs,ns); }
inline void ResetAccum(AccumStat& stat){ stat.count.store(0,std::memory_order_relaxed); stat.totalNs.store(0,std::memory_order_relaxed); stat.maxNs.store(0,std::memory_order_relaxed); }

enum class WaitKind:uint8_t{ Fence, Acquire, QueueIdle, DeviceIdle, Count };
inline std::array<AccumStat,static_cast<size_t>(WaitKind::Count)> g_waitStats{};
inline AccumStat g_presentTiming{},g_queueSubmitCpuTiming{},g_pipelineCompileTiming{},g_jitCompileTiming{},g_gpuSubmitTiming{};
inline std::atomic_uint64_t g_totalQueueSubmits{0},g_descriptorAlloc{0},g_descriptorUpdateWrites{0},g_descriptorBinds{0},g_descriptorCacheHits{0},g_descriptorCacheMisses{0},g_pipelineCacheHits{0},g_pipelineCacheMisses{0},g_uploadBytes{0},g_copyBytes{0},g_jitReadyReCount{0},g_diagEventCount{0},g_hitchCount{0},g_frameId{0},g_frameStartNs{0},g_lastFrameNs{0},g_lastGpuSubmitNs{0};
inline std::atomic_uint64_t g_frameDraws{0},g_frameSubmits{0},g_frameUploadBytes{0},g_frameCopyBytes{0},g_frameWaitNs{0},g_frameDescriptorWrites{0};

inline void NoteEvent(){ if(Enabled(Flag::DiagnosticOverhead)) g_diagEventCount.fetch_add(1,std::memory_order_relaxed); }
inline void AddWait(WaitKind kind,uint64_t ns){ AddAccum(g_waitStats[static_cast<size_t>(kind)],ns); g_frameWaitNs.fetch_add(ns,std::memory_order_relaxed); }
inline void AddGpuSubmit(uint64_t ns){ AddAccum(g_gpuSubmitTiming,ns); g_lastGpuSubmitNs.store(ns,std::memory_order_relaxed); }
inline void AddDescriptorWrite(uint64_t count){ g_descriptorUpdateWrites.fetch_add(count,std::memory_order_relaxed); g_frameDescriptorWrites.fetch_add(count,std::memory_order_relaxed); }
inline void AddUploadBytes(uint64_t bytes){ g_uploadBytes.fetch_add(bytes,std::memory_order_relaxed); g_frameUploadBytes.fetch_add(bytes,std::memory_order_relaxed); }
inline void AddCopyBytes(uint64_t bytes){ g_copyBytes.fetch_add(bytes,std::memory_order_relaxed); g_frameCopyBytes.fetch_add(bytes,std::memory_order_relaxed); }
inline bool FrameMetricsEnabled(){ return Enabled(Flag::FrameTiming)||Enabled(Flag::HitchTrigger)||Enabled(Flag::DiagnosticOverhead); }
inline void BeginFrame(){ if(!FrameMetricsEnabled()) return; g_frameDraws.store(0,std::memory_order_relaxed); g_frameSubmits.store(0,std::memory_order_relaxed); g_frameUploadBytes.store(0,std::memory_order_relaxed); g_frameCopyBytes.store(0,std::memory_order_relaxed); g_frameWaitNs.store(0,std::memory_order_relaxed); g_frameDescriptorWrites.store(0,std::memory_order_relaxed); g_frameStartNs.store(NowNs(),std::memory_order_relaxed); }
inline uint64_t EndFrame(){ if(!FrameMetricsEnabled()) return 0; const uint64_t start=g_frameStartNs.load(std::memory_order_relaxed); if(!start) return 0; const uint64_t ns=NowNs()-start; g_lastFrameNs.store(ns,std::memory_order_relaxed); g_frameId.fetch_add(1,std::memory_order_relaxed); return ns; }
inline void ResetCounters(){ for(auto& stat:g_waitStats) ResetAccum(stat); ResetAccum(g_presentTiming); ResetAccum(g_queueSubmitCpuTiming); ResetAccum(g_pipelineCompileTiming); ResetAccum(g_jitCompileTiming); ResetAccum(g_gpuSubmitTiming); g_totalQueueSubmits=0; g_descriptorAlloc=0; g_descriptorUpdateWrites=0; g_descriptorBinds=0; g_descriptorCacheHits=0; g_descriptorCacheMisses=0; g_pipelineCacheHits=0; g_pipelineCacheMisses=0; g_uploadBytes=0; g_copyBytes=0; g_jitReadyReCount=0; g_diagEventCount=0; g_hitchCount=0; g_frameId=0; }

class ScopedPipelineCompile { public: ScopedPipelineCompile():m_active(Enabled(Flag::PipelineCompileTime)),m_start(m_active?NowNs():0){} ~ScopedPipelineCompile(){if(m_active)AddAccum(g_pipelineCompileTiming,NowNs()-m_start);} private:bool m_active;uint64_t m_start;};
class ScopedJitCompile { public: ScopedJitCompile():m_active(Enabled(Flag::JitPerformance)||Enabled(Flag::JitBlockLifecycle)),m_start(m_active?NowNs():0){} ~ScopedJitCompile(){if(m_active)AddAccum(g_jitCompileTiming,NowNs()-m_start);} private:bool m_active;uint64_t m_start;};

// UI diagnostics no longer fan out through the old coarse experiment names.
// Environment-variable experiments still work because RuntimeExperiments::Enabled()
// falls through to parsing CEMU_EXPERIMENTS when this returns false.
inline bool LegacyBridgeEnabled(std::string_view)
{
    return false;
}
}
