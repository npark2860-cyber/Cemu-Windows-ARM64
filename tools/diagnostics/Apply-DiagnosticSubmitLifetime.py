from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


def replace_exact_count(text, old, new, expected, label):
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} anchors, found {count}")
    return text.replace(old, new)


# Make the first submit/lifetime group selectable only after concrete probes are
# installed. Flags remain OFF by default and stay independently controllable.
header_path = Path("src/diagnostics/RuntimeDiagnostics.h")
header = header_path.read_text(encoding="utf-8")
header = replace_once(
    header,
    "    // Vulkan / pipeline diagnostics\n    case Flag::QueueSubmit:\n",
    """    // Vulkan / pipeline diagnostics
    case Flag::CommandBufferLifecycle:
    case Flag::QueueSubmit:
    case Flag::FenceLifecycle:
    case Flag::SemaphoreFlow:
    case Flag::SubmitCompletion:
    case Flag::DeviceLostSubmitError:
""",
    "submit/lifetime IsImplemented flags",
)
header_path.write_text(header, encoding="utf-8", newline="\n")


renderer_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
renderer = renderer_path.read_text(encoding="utf-8")

helper_anchor = "extern std::atomic_int g_compiling_pipelines;\n"
helper_block = r'''extern std::atomic_int g_compiling_pipelines;

namespace
{
static bool SubmitLifetimeDiagSample(std::atomic_uint64_t& counter, uint64_t& seq)
{
    seq = counter.fetch_add(1, std::memory_order_relaxed) + 1;
    return seq <= 100 || (seq % 1000ULL) == 0;
}

static std::atomic_uint64_t s_diagCmdSeq{0};
static std::atomic_uint64_t s_diagFenceSeq{0};
static std::atomic_uint64_t s_diagSemaphoreSeq{0};
static std::atomic_uint64_t s_diagSubmitCompleteSeq{0};
}
'''
renderer = replace_once(renderer, helper_anchor, helper_block, "submit/lifetime helper block")

cmd_begin_old = "\tvkBeginCommandBuffer(m_state.currentCommandBuffer, &beginInfo);\n"
cmd_begin_new = r'''\tvkBeginCommandBuffer(m_state.currentCommandBuffer, &beginInfo);
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::CommandBufferLifecycle))
\t{
\t\tuint64_t seq = 0;
\t\tif (SubmitLifetimeDiagSample(s_diagCmdSeq, seq))
\t\t\tcemuLog_log(LogType::Force, "[VK_CMD] BEGIN n={} index={}", seq, m_commandBufferIndex);
\t}
'''
renderer = replace_exact_count(renderer, cmd_begin_old, cmd_begin_new, 2, "command-buffer begin probes")

cmd_end_old = "\tvkEndCommandBuffer(m_state.currentCommandBuffer);\n"
cmd_end_new = r'''\tvkEndCommandBuffer(m_state.currentCommandBuffer);
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::CommandBufferLifecycle))
\t{
\t\tuint64_t seq = 0;
\t\tif (SubmitLifetimeDiagSample(s_diagCmdSeq, seq))
\t\t\tcemuLog_log(LogType::Force, "[VK_CMD] END n={} index={}", seq, m_commandBufferIndex);
\t}
'''
renderer = replace_once(renderer, cmd_end_old, cmd_end_new, "command-buffer end probe")

fence_reset_old = "\tvkResetFences(m_logicalDevice, 1, &m_cmdBufferFences[m_commandBufferIndex]);\n"
fence_reset_new = r'''\tvkResetFences(m_logicalDevice, 1, &m_cmdBufferFences[m_commandBufferIndex]);
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::FenceLifecycle))
\t{
\t\tuint64_t seq = 0;
\t\tif (SubmitLifetimeDiagSample(s_diagFenceSeq, seq))
\t\t\tcemuLog_log(LogType::Force, "[VK_FENCE] RESET n={} index={}", seq, m_commandBufferIndex);
\t}
'''
renderer = replace_exact_count(renderer, fence_reset_old, fence_reset_new, 2, "fence reset probes")

fence_wait_old = r'''\tconst bool diagWait = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::CpuWaitBreakdown);
\tconst uint64_t diagWaitStart = diagWait ? RuntimeDiagnostics::NowNs() : 0;
\tVkResult result = vkWaitForFences(m_logicalDevice, 1, &m_cmdBufferFences[m_commandBufferSyncIndex], true, UINT64_MAX);
\tif (diagWait)
\t\tRuntimeDiagnostics::AddWait(RuntimeDiagnostics::WaitKind::Fence, RuntimeDiagnostics::NowNs() - diagWaitStart);
'''
fence_wait_new = r'''\tuint64_t diagFenceLifeSeq = 0;
\tconst bool diagFenceLifeSample = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::FenceLifecycle) && SubmitLifetimeDiagSample(s_diagFenceSeq, diagFenceLifeSeq);
\tif (diagFenceLifeSample)
\t\tcemuLog_log(LogType::Force, "[VK_FENCE] WAIT_BEGIN n={} index={}", diagFenceLifeSeq, m_commandBufferSyncIndex);
\tconst bool diagWait = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::CpuWaitBreakdown);
\tconst uint64_t diagWaitStart = diagWait ? RuntimeDiagnostics::NowNs() : 0;
\tVkResult result = vkWaitForFences(m_logicalDevice, 1, &m_cmdBufferFences[m_commandBufferSyncIndex], true, UINT64_MAX);
\tif (diagWait)
\t\tRuntimeDiagnostics::AddWait(RuntimeDiagnostics::WaitKind::Fence, RuntimeDiagnostics::NowNs() - diagWaitStart);
\tif (diagFenceLifeSample)
\t\tcemuLog_log(LogType::Force, "[VK_FENCE] WAIT_END n={} index={} result={}", diagFenceLifeSeq, m_commandBufferSyncIndex, (sint32)result);
'''
renderer = replace_once(renderer, fence_wait_old, fence_wait_new, "fence wait lifecycle probe")

submit_timing_anchor = r'''\tuint64_t diagSubmitStart = 0;
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::QueueSubmit) || RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::QueueSubmitCount))
'''
submit_timing_new = r'''\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SemaphoreFlow))
\t{
\t\tuint64_t seq = 0;
\t\tif (SubmitLifetimeDiagSample(s_diagSemaphoreSeq, seq))
\t\t{
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[VK_SEM] SUBMIT n={} index={} waits={} signals={} previousWait={} externalWait={} externalSignal={}",
\t\t\t\tseq, m_commandBufferIndex, submitInfo.waitSemaphoreCount, submitInfo.signalSemaphoreCount,
\t\t\t\tm_numSubmittedCmdBuffers > 0 ? 1 : 0, waitSemaphore != VK_NULL_HANDLE ? 1 : 0, signalSemaphore != VK_NULL_HANDLE ? 1 : 0);
\t\t}
\t}
\tuint64_t diagSubmitStart = 0;
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::QueueSubmit) || RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::QueueSubmitCount))
'''
renderer = replace_once(renderer, submit_timing_anchor, submit_timing_new, "semaphore submit-flow probe")

submit_error_old = r'''\tif (result != VK_SUCCESS)
\t\tUnrecoverableError(fmt::format("failed to submit command buffer. Error {}", result).c_str());
'''
submit_error_new = r'''\tif (result != VK_SUCCESS)
\t{
\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DeviceLostSubmitError))
\t\t{
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[VK_SUBMIT_ERROR] result={} deviceLost={} index={} waits={} signals={}",
\t\t\t\t(sint32)result, result == VK_ERROR_DEVICE_LOST ? 1 : 0, m_commandBufferIndex,
\t\t\t\tsubmitInfo.waitSemaphoreCount, submitInfo.signalSemaphoreCount);
\t\t}
\t\tUnrecoverableError(fmt::format("failed to submit command buffer. Error {}", result).c_str());
\t}
'''
renderer = replace_once(renderer, submit_error_old, submit_error_new, "device-lost/submit-error probe")

completion_anchor = "\t\tif (fenceStatus == VK_SUCCESS)\n\t\t{\n"
completion_new = r'''\t\tif (fenceStatus == VK_SUCCESS)
\t\t{
\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SubmitCompletion))
\t\t\t{
\t\t\t\tuint64_t seq = 0;
\t\t\t\tif (SubmitLifetimeDiagSample(s_diagSubmitCompleteSeq, seq))
\t\t\t\t\tcemuLog_log(LogType::Force, "[VK_SUBMIT_COMPLETE] FENCE_SIGNALED n={} index={}", seq, m_commandBufferSyncIndex);
\t\t\t}
'''
renderer = replace_once(renderer, completion_anchor, completion_new, "submit completion probe")

renderer_path.write_text(renderer, encoding="utf-8", newline="\n")


# Extend the exhaustive build-time verifier in the same generated source tree.
verify_path = Path("tools/diagnostics/Verify-DiagnosticCoverage.py")
verify = verify_path.read_text(encoding="utf-8")
verify_anchor = r'''    # Vulkan / pipeline
    "QueueSubmit": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::QueueSubmit")],
'''
verify_new = r'''    # Vulkan / pipeline
    "CommandBufferLifecycle": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::CommandBufferLifecycle"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "[VK_CMD]")],
    "QueueSubmit": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::QueueSubmit")],
    "FenceLifecycle": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::FenceLifecycle"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "[VK_FENCE]")],
    "SemaphoreFlow": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::SemaphoreFlow"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "[VK_SEM]")],
    "SubmitCompletion": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::SubmitCompletion"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "[VK_SUBMIT_COMPLETE]")],
    "DeviceLostSubmitError": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::DeviceLostSubmitError"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "[VK_SUBMIT_ERROR]")],
'''
verify = replace_once(verify, verify_anchor, verify_new, "submit/lifetime coverage verifier entries")
verify_path.write_text(verify, encoding="utf-8", newline="\n")

print("[diagnostics-submit-lifetime] five independent observation-only probes installed")
