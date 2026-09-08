from pathlib import Path

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)

def ensure_include(text, anchors, include_line, label):
    if include_line in text:
        return text
    for anchor in anchors:
        if anchor in text:
            return text.replace(anchor, anchor + include_line, 1)
    raise RuntimeError(f"{label}: include anchor not found")

api = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanAPI.h")
t = api.read_text(encoding="utf-8")
copy_line = "VKFUNC_DEVICE(vkCmdCopyQueryPoolResults);\n"
if "VKFUNC_DEVICE(vkCmdWriteTimestamp);\n" not in t:
    t = replace_once(t, copy_line, copy_line + "VKFUNC_DEVICE(vkCmdWriteTimestamp);\n", "timestamp API")
if "VKFUNC_DEVICE(vkGetQueryPoolResults);\n" not in t:
    t = replace_once(t, copy_line, copy_line + "VKFUNC_DEVICE(vkGetQueryPoolResults);\n", "query result API")
if t.count("VKFUNC_DEVICE(vkGetQueryPoolResults);") != 1:
    raise RuntimeError("vkGetQueryPoolResults loader must exist exactly once")
api.write_text(t, encoding="utf-8", newline="\n")

h = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h")
t = h.read_text(encoding="utf-8")
t = ensure_include(
    t,
    ('#include "util/containers/robin_hood.h"\n',),
    '#include "diagnostics/RuntimeDiagnostics.h"\n',
    "renderer header diagnostics include",
)
t = replace_once(
    t,
    "\tstd::array<VkFence, kCommandBufferPoolSize> m_cmdBufferFences;\n"
    "\tstd::array<VkCommandBuffer, kCommandBufferPoolSize> m_commandBuffers;\n"
    "\tstd::array<VkSemaphore, kCommandBufferPoolSize> m_commandBufferSemaphores;\n",
    "\tstd::array<VkFence, kCommandBufferPoolSize> m_cmdBufferFences;\n"
    "\tstd::array<VkCommandBuffer, kCommandBufferPoolSize> m_commandBuffers;\n"
    "\tstd::array<VkSemaphore, kCommandBufferPoolSize> m_commandBufferSemaphores;\n"
    "\tVkQueryPool m_diagTimestampQueryPool{VK_NULL_HANDLE};\n"
    "\tstd::array<bool, kCommandBufferPoolSize> m_diagTimestampWritten{};\n"
    "\tfloat m_diagTimestampPeriod{1.0f};\n",
    "diagnostic timestamp members",
)
t = replace_once(
    t,
    "\tvoid WaitDeviceIdle() const { vkDeviceWaitIdle(m_logicalDevice); }\n",
    """\tvoid WaitDeviceIdle() const
\t{
\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::CpuWaitBreakdown))
\t\t{
\t\t\tconst uint64_t start = RuntimeDiagnostics::NowNs();
\t\t\tvkDeviceWaitIdle(m_logicalDevice);
\t\t\tRuntimeDiagnostics::AddWait(RuntimeDiagnostics::WaitKind::DeviceIdle, RuntimeDiagnostics::NowNs() - start);
\t\t}
\t\telse
\t\t\tvkDeviceWaitIdle(m_logicalDevice);
\t}
""",
    "device idle timing",
)
h.write_text(t, encoding="utf-8", newline="\n")

renderer = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
t = renderer.read_text(encoding="utf-8")
t = ensure_include(
    t,
    ('#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"\n', '#include "config/CemuConfig.h"\n'),
    '#include "diagnostics/RuntimeDiagnostics.h"\n',
    "renderer diagnostics include",
)

first_begin = "\tvkBeginCommandBuffer(m_state.currentCommandBuffer, &beginInfo);\n\n\tvkCmdSetViewport(m_state.currentCommandBuffer, 0, 1, &m_state.currentViewport);\n"
first_new = """\tvkBeginCommandBuffer(m_state.currentCommandBuffer, &beginInfo);
\tm_diagTimestampWritten[m_commandBufferIndex] = false;
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GpuTimestamp))
\t{
\t\tif (m_diagTimestampQueryPool == VK_NULL_HANDLE)
\t\t{
\t\t\tVkQueryPoolCreateInfo diagQueryInfo{};
\t\t\tdiagQueryInfo.sType = VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO;
\t\t\tdiagQueryInfo.queryType = VK_QUERY_TYPE_TIMESTAMP;
\t\t\tdiagQueryInfo.queryCount = (uint32_t)(m_commandBuffers.size() * 2);
\t\t\tif (vkCreateQueryPool(m_logicalDevice, &diagQueryInfo, nullptr, &m_diagTimestampQueryPool) == VK_SUCCESS)
\t\t\t{
\t\t\t\tVkPhysicalDeviceProperties props{};
\t\t\t\tvkGetPhysicalDeviceProperties(m_physicalDevice, &props);
\t\t\t\tm_diagTimestampPeriod = props.limits.timestampPeriod;
\t\t\t}
\t\t}
\t\tif (m_diagTimestampQueryPool != VK_NULL_HANDLE)
\t\t{
\t\t\tconst uint32_t q = (uint32_t)m_commandBufferIndex * 2;
\t\t\tvkCmdResetQueryPool(m_state.currentCommandBuffer, m_diagTimestampQueryPool, q, 2);
\t\t\tvkCmdWriteTimestamp(m_state.currentCommandBuffer, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, m_diagTimestampQueryPool, q);
\t\t\tm_diagTimestampWritten[m_commandBufferIndex] = true;
\t\t}
\t}

\tvkCmdSetViewport(m_state.currentCommandBuffer, 0, 1, &m_state.currentViewport);
"""
t = replace_once(t, first_begin, first_new, "first command-buffer timestamp hook")

next_begin = """\tvkResetCommandBuffer(m_state.currentCommandBuffer, 0);

\tVkCommandBufferBeginInfo beginInfo{};
\tbeginInfo.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
\tbeginInfo.flags = VK_COMMAND_BUFFER_USAGE_SIMULTANEOUS_USE_BIT;
\tvkBeginCommandBuffer(m_state.currentCommandBuffer, &beginInfo);

\t// make sure some states are set for this command buffer
"""
next_new = """\tvkResetCommandBuffer(m_state.currentCommandBuffer, 0);

\tVkCommandBufferBeginInfo beginInfo{};
\tbeginInfo.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
\tbeginInfo.flags = VK_COMMAND_BUFFER_USAGE_SIMULTANEOUS_USE_BIT;
\tvkBeginCommandBuffer(m_state.currentCommandBuffer, &beginInfo);
\tm_diagTimestampWritten[m_commandBufferIndex] = false;
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GpuTimestamp))
\t{
\t\tif (m_diagTimestampQueryPool == VK_NULL_HANDLE)
\t\t{
\t\t\tVkQueryPoolCreateInfo diagQueryInfo{};
\t\t\tdiagQueryInfo.sType = VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO;
\t\t\tdiagQueryInfo.queryType = VK_QUERY_TYPE_TIMESTAMP;
\t\t\tdiagQueryInfo.queryCount = (uint32_t)(m_commandBuffers.size() * 2);
\t\t\tif (vkCreateQueryPool(m_logicalDevice, &diagQueryInfo, nullptr, &m_diagTimestampQueryPool) == VK_SUCCESS)
\t\t\t{
\t\t\t\tVkPhysicalDeviceProperties props{};
\t\t\t\tvkGetPhysicalDeviceProperties(m_physicalDevice, &props);
\t\t\t\tm_diagTimestampPeriod = props.limits.timestampPeriod;
\t\t\t}
\t\t}
\t\tif (m_diagTimestampQueryPool != VK_NULL_HANDLE)
\t\t{
\t\t\tconst uint32_t q = (uint32_t)m_commandBufferIndex * 2;
\t\t\tvkCmdResetQueryPool(m_state.currentCommandBuffer, m_diagTimestampQueryPool, q, 2);
\t\t\tvkCmdWriteTimestamp(m_state.currentCommandBuffer, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, m_diagTimestampQueryPool, q);
\t\t\tm_diagTimestampWritten[m_commandBufferIndex] = true;
\t\t}
\t}

\t// make sure some states are set for this command buffer
"""
t = replace_once(t, next_begin, next_new, "next command-buffer timestamp hook")

t = replace_once(
    t,
    "\tocclusionQuery_notifyEndCommandBuffer();\n\n\tvkEndCommandBuffer(m_state.currentCommandBuffer);\n",
    """\tocclusionQuery_notifyEndCommandBuffer();
\tif (m_diagTimestampQueryPool != VK_NULL_HANDLE && m_diagTimestampWritten[m_commandBufferIndex])
\t{
\t\tconst uint32_t q = (uint32_t)m_commandBufferIndex * 2 + 1;
\t\tvkCmdWriteTimestamp(m_state.currentCommandBuffer, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT, m_diagTimestampQueryPool, q);
\t}

\tvkEndCommandBuffer(m_state.currentCommandBuffer);
""",
    "timestamp end hook",
)

t = replace_once(
    t,
    "\tconst VkResult result = vkQueueSubmit(m_graphicsQueue, 1, &submitInfo, m_cmdBufferFences[m_commandBufferIndex]);\n\tif (result != VK_SUCCESS)\n",
    """\tuint64_t diagSubmitStart = 0;
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::QueueSubmit) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::QueueSubmitCount))
\t\tdiagSubmitStart = RuntimeDiagnostics::NowNs();
\tconst VkResult result = vkQueueSubmit(m_graphicsQueue, 1, &submitInfo, m_cmdBufferFences[m_commandBufferIndex]);
\tif (diagSubmitStart)
\t{
\t\tRuntimeDiagnostics::AddAccum(RuntimeDiagnostics::g_queueSubmitCpuTiming, RuntimeDiagnostics::NowNs() - diagSubmitStart);
\t\tRuntimeDiagnostics::g_totalQueueSubmits.fetch_add(1, std::memory_order_relaxed);
\t\tRuntimeDiagnostics::g_frameSubmits.fetch_add(1, std::memory_order_relaxed);
\t}
\tif (result != VK_SUCCESS)
""",
    "queue submit timing",
)

t = replace_once(
    t,
    "\tVkResult result = vkWaitForFences(m_logicalDevice, 1, &m_cmdBufferFences[m_commandBufferSyncIndex], true, UINT64_MAX);\n",
    """\tconst bool diagWait = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::CpuWaitBreakdown);
\tconst uint64_t diagWaitStart = diagWait ? RuntimeDiagnostics::NowNs() : 0;
\tVkResult result = vkWaitForFences(m_logicalDevice, 1, &m_cmdBufferFences[m_commandBufferSyncIndex], true, UINT64_MAX);
\tif (diagWait)
\t\tRuntimeDiagnostics::AddWait(RuntimeDiagnostics::WaitKind::Fence, RuntimeDiagnostics::NowNs() - diagWaitStart);
""",
    "fence wait timing",
)

t = replace_once(
    t,
    "\t\tif (fenceStatus == VK_SUCCESS)\n\t\t{\n\t\t\tProcessDestructionQueue();\n",
    """\t\tif (fenceStatus == VK_SUCCESS)
\t\t{
\t\t\tif (m_diagTimestampQueryPool != VK_NULL_HANDLE && m_diagTimestampWritten[m_commandBufferSyncIndex])
\t\t\t{
\t\t\t\tuint64_t timestamps[2]{};
\t\t\t\tconst uint32_t q = (uint32_t)m_commandBufferSyncIndex * 2;
\t\t\t\tif (vkGetQueryPoolResults(m_logicalDevice, m_diagTimestampQueryPool, q, 2, sizeof(timestamps), timestamps, sizeof(uint64_t), VK_QUERY_RESULT_64_BIT) == VK_SUCCESS)
\t\t\t\t{
\t\t\t\t\tconst uint64_t ticks = timestamps[1] - timestamps[0];
\t\t\t\t\tRuntimeDiagnostics::AddGpuSubmit((uint64_t)((double)ticks * (double)m_diagTimestampPeriod));
\t\t\t\t}
\t\t\t\tm_diagTimestampWritten[m_commandBufferSyncIndex] = false;
\t\t\t}
\t\t\tProcessDestructionQueue();
""",
    "timestamp result read",
)

t = replace_once(
    t,
    "\tVkResult result = vkQueuePresentKHR(m_presentQueue, &presentInfo);\n",
    """\tconst bool diagPresent = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PresentTiming);
\tconst uint64_t diagPresentStart = diagPresent ? RuntimeDiagnostics::NowNs() : 0;
\tVkResult result = vkQueuePresentKHR(m_presentQueue, &presentInfo);
\tif (diagPresent)
\t\tRuntimeDiagnostics::AddAccum(RuntimeDiagnostics::g_presentTiming, RuntimeDiagnostics::NowNs() - diagPresentStart);
""",
    "present timing",
)

t = replace_once(
    t,
    "\t\tif (m_logicalDevice != VK_NULL_HANDLE)\n\t\t{\n\t\t\tvkDestroyDevice(m_logicalDevice, nullptr);\n\t\t}\n",
    """\t\tif (m_logicalDevice != VK_NULL_HANDLE)
\t\t{
\t\t\tif (m_diagTimestampQueryPool != VK_NULL_HANDLE)
\t\t\t{
\t\t\t\tvkDestroyQueryPool(m_logicalDevice, m_diagTimestampQueryPool, nullptr);
\t\t\t\tm_diagTimestampQueryPool = VK_NULL_HANDLE;
\t\t\t}
\t\t\tvkDestroyDevice(m_logicalDevice, nullptr);
\t\t}
""",
    "timestamp pool destroy",
)

t = replace_once(
    t,
    "VulkanRenderer::~VulkanRenderer()\n{\n\tSubmitCommandBuffer();\n",
    """VulkanRenderer::~VulkanRenderer()
{
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SummaryOnExit))
\t{
\t\tconst auto& fence = RuntimeDiagnostics::g_waitStats[(size_t)RuntimeDiagnostics::WaitKind::Fence];
\t\tcemuLog_log(LogType::Force,
\t\t\t"[DIAG_SUMMARY] frames={} submits={} gpuAvgMs={:.3f} fenceWaitMs={:.3f} descHit={} descMiss={} descWrites={} descBinds={} uploadMB={:.2f} copyMB={:.2f} jitCompiles={} diagEvents={} hitches={}",
\t\t\tRuntimeDiagnostics::g_frameId.load(), RuntimeDiagnostics::g_totalQueueSubmits.load(),
\t\t\tRuntimeDiagnostics::g_gpuSubmitTiming.count.load() ? (double)RuntimeDiagnostics::g_gpuSubmitTiming.totalNs.load()/1000000.0/(double)RuntimeDiagnostics::g_gpuSubmitTiming.count.load() : 0.0,
\t\t\t(double)fence.totalNs.load()/1000000.0,
\t\t\tRuntimeDiagnostics::g_descriptorCacheHits.load(), RuntimeDiagnostics::g_descriptorCacheMisses.load(),
\t\t\tRuntimeDiagnostics::g_descriptorUpdateWrites.load(), RuntimeDiagnostics::g_descriptorBinds.load(),
\t\t\t(double)RuntimeDiagnostics::g_uploadBytes.load()/1048576.0, (double)RuntimeDiagnostics::g_copyBytes.load()/1048576.0,
\t\t\tRuntimeDiagnostics::g_jitReadyReCount.load(), RuntimeDiagnostics::g_diagEventCount.load(), RuntimeDiagnostics::g_hitchCount.load());
\t}
\tSubmitCommandBuffer();
""",
    "diagnostic summary",
)

renderer.write_text(t, encoding="utf-8", newline="\n")

swap = Path("src/Cafe/HW/Latte/Renderer/Vulkan/SwapchainInfoVk.cpp")
t = swap.read_text(encoding="utf-8")
t = ensure_include(
    t,
    ('#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h"\n',),
    '#include "diagnostics/RuntimeDiagnostics.h"\n',
    "swapchain diagnostics include",
)
t = replace_once(
    t,
    "\tif(m_awaitableFence != VK_NULL_HANDLE)\n\t\tvkWaitForFences(m_logicalDevice, 1, &m_awaitableFence, VK_TRUE, UINT64_MAX);\n",
    """\tif(m_awaitableFence != VK_NULL_HANDLE)
\t{
\t\tconst bool diagWait = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::CpuWaitBreakdown);
\t\tconst uint64_t start = diagWait ? RuntimeDiagnostics::NowNs() : 0;
\t\tvkWaitForFences(m_logicalDevice, 1, &m_awaitableFence, VK_TRUE, UINT64_MAX);
\t\tif (diagWait)
\t\t\tRuntimeDiagnostics::AddWait(RuntimeDiagnostics::WaitKind::Acquire, RuntimeDiagnostics::NowNs() - start);
\t}
""",
    "swapchain fence timing",
)
t = replace_once(
    t,
    "\tVkSemaphore acquireSemaphore = m_acquireSemaphores[m_acquireIndex];\n\tVkResult result = vkAcquireNextImageKHR(m_logicalDevice, m_swapchain, 1'000'000'000, acquireSemaphore, m_imageAvailableFence, &swapchainImageIndex);\n",
    """\tVkSemaphore acquireSemaphore = m_acquireSemaphores[m_acquireIndex];
\tconst bool diagAcquire = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::CpuWaitBreakdown);
\tconst uint64_t diagAcquireStart = diagAcquire ? RuntimeDiagnostics::NowNs() : 0;
\tVkResult result = vkAcquireNextImageKHR(m_logicalDevice, m_swapchain, 1'000'000'000, acquireSemaphore, m_imageAvailableFence, &swapchainImageIndex);
\tif (diagAcquire)
\t\tRuntimeDiagnostics::AddWait(RuntimeDiagnostics::WaitKind::Acquire, RuntimeDiagnostics::NowNs() - diagAcquireStart);
""",
    "acquire timing",
)
swap.write_text(t, encoding="utf-8", newline="\n")
print("[lean-vulkan] lazy, switch-gated Vulkan diagnostics installed")
