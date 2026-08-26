from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


def replace_count(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} anchors, found {count}")
    return text.replace(old, new)


header_path = Path("src/diagnostics/RuntimeDiagnostics.h")
header = header_path.read_text(encoding="utf-8")
header = replace_once(
    header,
    '''    // Vulkan / pipeline diagnostics
    case Flag::QueueSubmit:
''',
    '''    // Vulkan submit / lifetime diagnostics
    case Flag::CommandBufferLifecycle:
    case Flag::FenceLifecycle:
    case Flag::SemaphoreFlow:
    case Flag::SubmitCompletion:
    case Flag::DeviceLostSubmitError:

    // Vulkan / pipeline diagnostics
    case Flag::QueueSubmit:
''',
    "submit/lifetime IsImplemented cases",
)
header_path.write_text(header, encoding="utf-8", newline="\n")

renderer_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
text = renderer_path.read_text(encoding="utf-8")

begin_line = "\tvkBeginCommandBuffer(m_state.currentCommandBuffer, &beginInfo);\n"
begin_new = begin_line + '''\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::CommandBufferLifecycle))
\t{
\t\tstatic std::atomic_uint64_t s_cmdBeginSeq{0};
\t\tconst uint64_t n = s_cmdBeginSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 100 || (n % 1000ULL) == 0)
\t\t\tcemuLog_log(LogType::Force, "[CMD_LIFECYCLE] BEGIN n={} slot={}", n, m_commandBufferIndex);
\t}
'''
text = replace_count(text, begin_line, begin_new, 2, "command-buffer begin hooks")

end_line = "\tvkEndCommandBuffer(m_state.currentCommandBuffer);\n"
end_new = '''\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::CommandBufferLifecycle))
\t\tcemuLog_log(LogType::Force, "[CMD_LIFECYCLE] END slot={}", m_commandBufferIndex);
''' + end_line
text = replace_once(text, end_line, end_new, "command-buffer end hook")

reset_cmd = "\tvkResetCommandBuffer(m_state.currentCommandBuffer, 0);\n"
reset_cmd_new = reset_cmd + '''\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::CommandBufferLifecycle))
\t\tcemuLog_log(LogType::Force, "[CMD_LIFECYCLE] RESET slot={}", m_commandBufferIndex);
'''
text = replace_once(text, reset_cmd, reset_cmd_new, "command-buffer reset hook")

reset_fence = "\tvkResetFences(m_logicalDevice, 1, &m_cmdBufferFences[m_commandBufferIndex]);\n"
reset_fence_new = reset_fence + '''\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::FenceLifecycle))
\t\tcemuLog_log(LogType::Force, "[FENCE_LIFECYCLE] RESET slot={}", m_commandBufferIndex);
'''
text = replace_count(text, reset_fence, reset_fence_new, 2, "fence reset hooks")

fence_status_anchor = '''\t\tVkResult fenceStatus = vkGetFenceStatus(m_logicalDevice, m_cmdBufferFences[m_commandBufferSyncIndex]);
\t\tif (fenceStatus == VK_SUCCESS)
\t\t{
'''
fence_status_new = '''\t\tVkResult fenceStatus = vkGetFenceStatus(m_logicalDevice, m_cmdBufferFences[m_commandBufferSyncIndex]);
\t\tif (fenceStatus == VK_SUCCESS)
\t\t{
\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::FenceLifecycle))
\t\t\t\tcemuLog_log(LogType::Force, "[FENCE_LIFECYCLE] SIGNALED slot={}", m_commandBufferSyncIndex);
\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SubmitCompletion))
\t\t\t\tcemuLog_log(LogType::Force, "[SUBMIT_COMPLETE] slot={} finishedCount={}", m_commandBufferSyncIndex, m_countCommandBufferFinished);
'''
text = replace_once(text, fence_status_anchor, fence_status_new, "fence completion hooks")

unexpected_fence = '''\t\tUnrecoverableError(fmt::format("vkGetFenceStatus returned unexpected error {}", (sint32)fenceStatus).c_str());
'''
unexpected_fence_new = '''\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DeviceLostSubmitError))
\t\t\tcemuLog_log(LogType::Force, "[VK_SUBMIT_ERROR] fenceStatus={} deviceLost={}", (sint32)fenceStatus, fenceStatus == VK_ERROR_DEVICE_LOST ? 1 : 0);
''' + unexpected_fence
text = replace_once(text, unexpected_fence, unexpected_fence_new, "fence error hook")

wait_line = "\tVkResult result = vkWaitForFences(m_logicalDevice, 1, &m_cmdBufferFences[m_commandBufferSyncIndex], true, UINT64_MAX);\n"
wait_new = wait_line + '''\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::FenceLifecycle))
\t\tcemuLog_log(LogType::Force, "[FENCE_LIFECYCLE] WAIT slot={} result={}", m_commandBufferSyncIndex, (sint32)result);
'''
text = replace_once(text, wait_line, wait_new, "fence wait hook")

submit_line = "\tconst VkResult result = vkQueueSubmit(m_graphicsQueue, 1, &submitInfo, m_cmdBufferFences[m_commandBufferIndex]);\n"
submit_new = '''\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SemaphoreFlow))
\t{
\t\tstatic std::atomic_uint64_t s_semFlowSeq{0};
\t\tconst uint64_t n = s_semFlowSeq.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 100 || (n % 1000ULL) == 0)
\t\t\tcemuLog_log(LogType::Force, "[SEMAPHORE_FLOW] SUBMIT n={} slot={} waits={} signals={}", n, m_commandBufferIndex, submitInfo.waitSemaphoreCount, submitInfo.signalSemaphoreCount);
\t}
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::CommandBufferLifecycle))
\t\tcemuLog_log(LogType::Force, "[CMD_LIFECYCLE] SUBMIT slot={} waits={} signals={}", m_commandBufferIndex, submitInfo.waitSemaphoreCount, submitInfo.signalSemaphoreCount);
''' + submit_line + '''\tif (result != VK_SUCCESS && RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DeviceLostSubmitError))
\t\tcemuLog_log(LogType::Force, "[VK_SUBMIT_ERROR] queueSubmit result={} deviceLost={} slot={}", (sint32)result, result == VK_ERROR_DEVICE_LOST ? 1 : 0, m_commandBufferIndex);
'''
text = replace_once(text, submit_line, submit_new, "queue submit diagnostics")

renderer_path.write_text(text, encoding="utf-8", newline="\n")

verify_path = Path("tools/diagnostics/Verify-DiagnosticCoverage.py")
verify = verify_path.read_text(encoding="utf-8")
verify = replace_once(
    verify,
    '''    # Vulkan / pipeline
    "QueueSubmit":''',
    '''    # Vulkan submit / lifetime
    "CommandBufferLifecycle": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::CommandBufferLifecycle"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "[CMD_LIFECYCLE]")],
    "FenceLifecycle": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::FenceLifecycle"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "[FENCE_LIFECYCLE]")],
    "SemaphoreFlow": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::SemaphoreFlow"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "[SEMAPHORE_FLOW]")],
    "SubmitCompletion": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::SubmitCompletion"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "[SUBMIT_COMPLETE]")],
    "DeviceLostSubmitError": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::DeviceLostSubmitError"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "[VK_SUBMIT_ERROR]")],

    # Vulkan / pipeline
    "QueueSubmit":''',
    "coverage verifier submit/lifetime hooks",
)
verify_path.write_text(verify, encoding="utf-8", newline="\n")

print("[submit-lifetime] five independent runtime probes installed; coverage verifier extended")
