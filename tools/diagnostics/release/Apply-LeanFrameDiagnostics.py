from pathlib import Path

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)

p = Path("src/Cafe/HW/Latte/Core/LattePerformanceMonitor.cpp")
t = p.read_text(encoding="utf-8")
if '#include "diagnostics/RuntimeDiagnostics.h"\n' not in t:
    t = replace_once(
        t,
        '#include "WindowSystem.h"\n',
        '#include "WindowSystem.h"\n#include "diagnostics/RuntimeDiagnostics.h"\n',
        "performance monitor diagnostics include",
    )

t = replace_once(
    t,
    "void LattePerformanceMonitor_frameEnd()\n{\n",
    """void LattePerformanceMonitor_frameEnd()
{
\tconst uint64_t diagFrameNs = RuntimeDiagnostics::EndFrame();
\tif (diagFrameNs && RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::HitchTrigger) &&
\t\tdiagFrameNs >= (uint64_t)RuntimeDiagnostics::g_hitchThresholdMs.load(std::memory_order_relaxed) * 1000000ULL)
\t{
\t\tRuntimeDiagnostics::g_hitchCount.fetch_add(1, std::memory_order_relaxed);
\t\tcemuLog_log(LogType::Force,
\t\t\t"[DIAG_HITCH] frame={} cpuMs={:.3f} gpuMs={:.3f} waitsMs={:.3f} draws={} submits={} uploadKB={} copyKB={} descWrites={} barriers={} renderPasses={}",
\t\t\tRuntimeDiagnostics::g_frameId.load(), (double)diagFrameNs/1000000.0,
\t\t\t(double)RuntimeDiagnostics::g_lastGpuSubmitNs.load()/1000000.0,
\t\t\t(double)RuntimeDiagnostics::g_frameWaitNs.load()/1000000.0,
\t\t\tRuntimeDiagnostics::g_frameDraws.load(), RuntimeDiagnostics::g_frameSubmits.load(),
\t\t\tRuntimeDiagnostics::g_frameUploadBytes.load()/1024ULL, RuntimeDiagnostics::g_frameCopyBytes.load()/1024ULL,
\t\t\tRuntimeDiagnostics::g_frameDescriptorWrites.load(),
\t\t\tperformanceMonitor.vk.numDrawBarriersPerFrame.get(), performanceMonitor.vk.numBeginRenderpassPerFrame.get());
\t}
""",
    "frame end diagnostics",
)
t = replace_once(
    t,
    "void LattePerformanceMonitor_frameBegin()\n{\n",
    """void LattePerformanceMonitor_frameBegin()
{
\tRuntimeDiagnostics::BeginFrame();
""",
    "frame begin diagnostics",
)
p.write_text(t, encoding="utf-8", newline="\n")
print("[lean-frame] frame timing and hitch diagnostics installed")
