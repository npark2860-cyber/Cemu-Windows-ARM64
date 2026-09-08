from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# RuntimeDiagnostics: make the incident hot-path gate one atomic load and add
# bounded resource/image-layout breadcrumbs plus incident serialization/dedupe.
# ---------------------------------------------------------------------------
header_path = Path("src/diagnostics/RuntimeDiagnostics.h")
header = header_path.read_text(encoding="utf-8")
if "#include <string>\n" not in header:
    header = replace_once(header, "#include <string_view>\n", "#include <string>\n#include <string_view>\n", "diagnostic string include")
if "#include <unordered_map>\n" not in header:
    header = replace_once(header, "#include <string_view>\n", "#include <string_view>\n#include <unordered_map>\n", "diagnostic unordered_map include")

header = replace_once(
    header,
    "inline std::array<std::atomic_bool, kFlagCount> g_flags{};\n",
    "inline std::array<std::atomic_bool, kFlagCount> g_flags{};\n"
    "inline std::atomic_bool g_incidentContextActive{};\n"
    "inline std::atomic_bool g_incidentCaptureActive{};\n",
    "incident atomic gates",
)

set_enabled_anchor = '''inline bool Enabled(Flag flag)
{
    return IsImplemented(flag) && g_flags[static_cast<size_t>(flag)].load(std::memory_order_relaxed);
}
'''
incident_flag_helpers = r'''inline bool IsIncidentContextFlag(Flag flag)
{
    switch (flag)
    {
    case Flag::PipelineFailure:
    case Flag::GLSLCompileFailure:
    case Flag::SPIRVCompileFailure:
    case Flag::DeviceLostSubmitError:
    case Flag::DumpFailedShader:
        return true;
    default:
        return false;
    }
}

inline void RefreshIncidentContextActive()
{
    const bool active =
        g_flags[static_cast<size_t>(Flag::PipelineFailure)].load(std::memory_order_relaxed) ||
        g_flags[static_cast<size_t>(Flag::GLSLCompileFailure)].load(std::memory_order_relaxed) ||
        g_flags[static_cast<size_t>(Flag::SPIRVCompileFailure)].load(std::memory_order_relaxed) ||
        g_flags[static_cast<size_t>(Flag::DeviceLostSubmitError)].load(std::memory_order_relaxed) ||
        g_flags[static_cast<size_t>(Flag::DumpFailedShader)].load(std::memory_order_relaxed);
    g_incidentContextActive.store(active, std::memory_order_relaxed);
    if (!active)
        g_incidentCaptureActive.store(false, std::memory_order_relaxed);
}

'''
header = replace_once(header, set_enabled_anchor, incident_flag_helpers + set_enabled_anchor, "incident flag helpers")

header = replace_once(
    header,
    '''inline void SetEnabled(Flag flag, bool enabled)
{
    g_flags[static_cast<size_t>(flag)].store(IsImplemented(flag) ? enabled : false, std::memory_order_relaxed);
}
''',
    '''inline void SetEnabled(Flag flag, bool enabled)
{
    g_flags[static_cast<size_t>(flag)].store(IsImplemented(flag) ? enabled : false, std::memory_order_relaxed);
    if (IsIncidentContextFlag(flag))
        RefreshIncidentContextActive();
}
''',
    "incident SetEnabled refresh",
)
header = replace_once(
    header,
    '''inline void SetAll(bool enabled)
{
    for (size_t i = 0; i < kFlagCount; ++i)
    {
        const auto flag = static_cast<Flag>(i);
        g_flags[i].store(IsImplemented(flag) ? enabled : false, std::memory_order_relaxed);
    }
}
''',
    '''inline void SetAll(bool enabled)
{
    for (size_t i = 0; i < kFlagCount; ++i)
    {
        const auto flag = static_cast<Flag>(i);
        g_flags[i].store(IsImplemented(flag) ? enabled : false, std::memory_order_relaxed);
    }
    RefreshIncidentContextActive();
}
''',
    "incident SetAll refresh",
)

incident_start = header.find("inline bool IncidentContextEnabled()")
record_start = header.find("inline void RecordDrawBreadcrumb", incident_start)
if incident_start < 0 or record_start < 0:
    raise RuntimeError("incident context section not found")
incident_core = r'''inline bool IncidentContextEnabled()
{
    return g_incidentContextActive.load(std::memory_order_relaxed);
}

inline uint64_t DiagnosticNowNs()
{
    return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}

struct ResourceBreadcrumb
{
    uint64_t seq{};
    uint64_t timestampNs{};
    uint32_t handle{};
    uint64_t offset{};
    uint64_t requestedBytes{};
    uint64_t actualBytes{};
    std::string path;
};

inline constexpr size_t kResourceBreadcrumbCapacity = 32;
inline std::array<ResourceBreadcrumb, kResourceBreadcrumbCapacity> g_resourceBreadcrumbs{};
inline std::unordered_map<uint32_t, std::string> g_resourcePathByHandle;
inline std::mutex g_resourceBreadcrumbMutex;
inline uint64_t g_resourceBreadcrumbSequence{};
inline size_t g_resourceBreadcrumbHead{};
inline size_t g_resourceBreadcrumbCount{};

struct ImageLayoutBreadcrumb
{
    uint64_t seq{};
    uint64_t timestampNs{};
    uint64_t image{};
    uint64_t srcStages{};
    uint64_t dstStages{};
    uint64_t srcAccess{};
    uint64_t dstAccess{};
    uint32_t oldLayout{};
    uint32_t newLayout{};
    uint32_t aspectMask{};
    uint32_t baseMip{};
    uint32_t levelCount{};
    uint32_t baseLayer{};
    uint32_t layerCount{};
};

inline constexpr size_t kImageLayoutBreadcrumbCapacity = 64;
inline std::array<ImageLayoutBreadcrumb, kImageLayoutBreadcrumbCapacity> g_imageLayoutBreadcrumbs{};
inline std::mutex g_imageLayoutBreadcrumbMutex;
inline uint64_t g_imageLayoutBreadcrumbSequence{};
inline size_t g_imageLayoutBreadcrumbHead{};
inline size_t g_imageLayoutBreadcrumbCount{};

struct IncidentDedupEntry
{
    uint64_t key{};
    uint64_t lastEmitNs{};
    uint32_t suppressed{};
};

struct IncidentGateResult
{
    bool emit{};
    uint64_t id{};
    uint64_t key{};
    uint32_t suppressed{};
};

inline std::array<IncidentDedupEntry, 16> g_incidentDedup{};
inline size_t g_incidentDedupReplaceIndex{};
inline std::mutex g_incidentStateMutex;
inline std::mutex g_incidentLogMutex;
inline std::mutex g_incidentStartMutex;
inline std::atomic_uint64_t g_incidentSequence{};

inline void ClearIncidentContext()
{
    {
        std::lock_guard<std::mutex> lock(g_drawBreadcrumbMutex);
        g_drawBreadcrumbHead = 0;
        g_drawBreadcrumbCount = 0;
        g_drawBreadcrumbSequence = 0;
    }
    {
        std::lock_guard<std::mutex> lock(g_resourceBreadcrumbMutex);
        g_resourceBreadcrumbHead = 0;
        g_resourceBreadcrumbCount = 0;
        g_resourceBreadcrumbSequence = 0;
        g_resourcePathByHandle.clear();
    }
    {
        std::lock_guard<std::mutex> lock(g_imageLayoutBreadcrumbMutex);
        g_imageLayoutBreadcrumbHead = 0;
        g_imageLayoutBreadcrumbCount = 0;
        g_imageLayoutBreadcrumbSequence = 0;
    }
    {
        std::lock_guard<std::mutex> lock(g_incidentStateMutex);
        for (auto& entry : g_incidentDedup)
            entry = {};
        g_incidentDedupReplaceIndex = 0;
    }
}

inline bool EnsureIncidentCaptureStarted()
{
    if (!IncidentContextEnabled())
    {
        g_incidentCaptureActive.store(false, std::memory_order_relaxed);
        return false;
    }
    if (g_incidentCaptureActive.load(std::memory_order_acquire))
        return true;

    std::lock_guard<std::mutex> startLock(g_incidentStartMutex);
    if (!g_incidentCaptureActive.load(std::memory_order_relaxed))
    {
        ClearIncidentContext();
        g_incidentCaptureActive.store(true, std::memory_order_release);
    }
    return true;
}

inline uint64_t HashIncidentKey(const char* reason, uint64_t subjectA, uint64_t subjectB)
{
    uint64_t hash = 1469598103934665603ULL;
    const std::string_view text = reason ? std::string_view(reason) : std::string_view("unknown");
    for (const unsigned char ch : text)
    {
        hash ^= static_cast<uint64_t>(ch);
        hash *= 1099511628211ULL;
    }
    hash ^= subjectA + 0x9e3779b97f4a7c15ULL + (hash << 6) + (hash >> 2);
    hash ^= subjectB + 0x9e3779b97f4a7c15ULL + (hash << 6) + (hash >> 2);
    return hash;
}

inline IncidentGateResult AcquireIncident(const char* reason, uint64_t subjectA, uint64_t subjectB)
{
    if (!EnsureIncidentCaptureStarted())
        return {};

    constexpr uint64_t kRepeatWindowNs = 1000000000ULL;
    const uint64_t now = DiagnosticNowNs();
    const uint64_t key = HashIncidentKey(reason, subjectA, subjectB);
    std::lock_guard<std::mutex> lock(g_incidentStateMutex);

    for (auto& entry : g_incidentDedup)
    {
        if (entry.key != key)
            continue;
        if (entry.lastEmitNs != 0 && (now - entry.lastEmitNs) < kRepeatWindowNs)
        {
            ++entry.suppressed;
            return { false, 0, key, entry.suppressed };
        }
        const uint32_t suppressed = entry.suppressed;
        entry.suppressed = 0;
        entry.lastEmitNs = now;
        const uint64_t id = g_incidentSequence.fetch_add(1, std::memory_order_relaxed) + 1;
        return { true, id, key, suppressed };
    }

    auto& entry = g_incidentDedup[g_incidentDedupReplaceIndex++ % g_incidentDedup.size()];
    entry.key = key;
    entry.lastEmitNs = now;
    entry.suppressed = 0;
    const uint64_t id = g_incidentSequence.fetch_add(1, std::memory_order_relaxed) + 1;
    return { true, id, key, 0 };
}

inline void RecordResourceOpen(uint32_t handle, std::string_view path)
{
    if (!EnsureIncidentCaptureStarted())
        return;
    std::lock_guard<std::mutex> lock(g_resourceBreadcrumbMutex);
    g_resourcePathByHandle[handle] = std::string(path);
}

inline void RecordResourceClose(uint32_t handle)
{
    if (!IncidentContextEnabled())
        return;
    std::lock_guard<std::mutex> lock(g_resourceBreadcrumbMutex);
    g_resourcePathByHandle.erase(handle);
}

inline void RecordResourceRead(uint32_t handle, uint64_t offset, uint64_t requestedBytes, uint64_t actualBytes)
{
    if (!EnsureIncidentCaptureStarted())
        return;
    std::lock_guard<std::mutex> lock(g_resourceBreadcrumbMutex);
    ResourceBreadcrumb entry{};
    entry.seq = ++g_resourceBreadcrumbSequence;
    entry.timestampNs = DiagnosticNowNs();
    entry.handle = handle;
    entry.offset = offset;
    entry.requestedBytes = requestedBytes;
    entry.actualBytes = actualBytes;
    auto it = g_resourcePathByHandle.find(handle);
    entry.path = it != g_resourcePathByHandle.end() ? it->second : std::string("<unknown-open-before-diagnostics>");
    g_resourceBreadcrumbs[g_resourceBreadcrumbHead] = std::move(entry);
    g_resourceBreadcrumbHead = (g_resourceBreadcrumbHead + 1) % kResourceBreadcrumbCapacity;
    if (g_resourceBreadcrumbCount < kResourceBreadcrumbCapacity)
        ++g_resourceBreadcrumbCount;
}

template<typename TCallback>
inline void ForEachRecentResourceBreadcrumb(TCallback&& callback)
{
    std::lock_guard<std::mutex> lock(g_resourceBreadcrumbMutex);
    if (g_resourceBreadcrumbCount == 0)
        return;
    const size_t oldest = (g_resourceBreadcrumbHead + kResourceBreadcrumbCapacity - g_resourceBreadcrumbCount) % kResourceBreadcrumbCapacity;
    for (size_t i = 0; i < g_resourceBreadcrumbCount; ++i)
        callback(g_resourceBreadcrumbs[(oldest + i) % kResourceBreadcrumbCapacity], g_resourceBreadcrumbCount - i - 1);
}

inline void RecordImageLayoutBreadcrumb(ImageLayoutBreadcrumb entry)
{
    if (!EnsureIncidentCaptureStarted())
        return;
    std::lock_guard<std::mutex> lock(g_imageLayoutBreadcrumbMutex);
    entry.seq = ++g_imageLayoutBreadcrumbSequence;
    entry.timestampNs = DiagnosticNowNs();
    g_imageLayoutBreadcrumbs[g_imageLayoutBreadcrumbHead] = entry;
    g_imageLayoutBreadcrumbHead = (g_imageLayoutBreadcrumbHead + 1) % kImageLayoutBreadcrumbCapacity;
    if (g_imageLayoutBreadcrumbCount < kImageLayoutBreadcrumbCapacity)
        ++g_imageLayoutBreadcrumbCount;
}

template<typename TCallback>
inline void ForEachRecentImageLayoutBreadcrumb(TCallback&& callback)
{
    std::lock_guard<std::mutex> lock(g_imageLayoutBreadcrumbMutex);
    if (g_imageLayoutBreadcrumbCount == 0)
        return;
    const size_t oldest = (g_imageLayoutBreadcrumbHead + kImageLayoutBreadcrumbCapacity - g_imageLayoutBreadcrumbCount) % kImageLayoutBreadcrumbCapacity;
    for (size_t i = 0; i < g_imageLayoutBreadcrumbCount; ++i)
        callback(g_imageLayoutBreadcrumbs[(oldest + i) % kImageLayoutBreadcrumbCapacity], g_imageLayoutBreadcrumbCount - i - 1);
}

'''
header = header[:incident_start] + incident_core + header[record_start:]
header = replace_once(
    header,
    '''inline void RecordDrawBreadcrumb(DrawBreadcrumb entry)
{
    if (!IncidentContextEnabled())
        return;
''',
    '''inline void RecordDrawBreadcrumb(DrawBreadcrumb entry)
{
    if (!EnsureIncidentCaptureStarted())
        return;
''',
    "draw breadcrumb capture-start gate",
)
header = replace_once(
    header,
    "g_diagEventCount=0; g_hitchCount=0; g_frameId=0; }\n",
    "g_diagEventCount=0; g_hitchCount=0; g_frameId=0; ClearIncidentContext(); }\n",
    "reset incident context with counters",
)
header_path.write_text(header, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Resource breadcrumbs: map handle->virtual path only while incident capture is
# enabled. Existing handles opened before enabling remain explicitly unknown.
# ---------------------------------------------------------------------------
fsa_path = Path("src/Cafe/IOSU/fsa/iosu_fsa.cpp")
fsa = fsa_path.read_text(encoding="utf-8")
if '#include "diagnostics/RuntimeDiagnostics.h"\n' not in fsa:
    fsa = replace_once(
        fsa,
        '#include "util/helpers/helpers.h"\n',
        '#include "util/helpers/helpers.h"\n#include "diagnostics/RuntimeDiagnostics.h"\n',
        "FSA diagnostic include",
    )

fsa = replace_once(
    fsa,
    '''\t\t\t*fileHandle = fsFileHandle;
\t\t\tcemuLog_log(LogType::CoreinitFile, "Open file {} (access: {} result: ok handle: 0x{})", path, accessModifierStr, (uint32)*fileHandle);
''',
    '''\t\t\t*fileHandle = fsFileHandle;
\t\t\tif (RuntimeDiagnostics::IncidentContextEnabled())
\t\t\t\tRuntimeDiagnostics::RecordResourceOpen((uint32)*fileHandle, path);
\t\t\tcemuLog_log(LogType::CoreinitFile, "Open file {} (access: {} result: ok handle: 0x{})", path, accessModifierStr, (uint32)*fileHandle);
''',
    "resource open attribution",
)
fsa = replace_once(
    fsa,
    '''\t\t\t// unregister file
\t\t\tsFileHandleTable.ReleaseHandle(fileHandle); // todo - use the error code of this
''',
    '''\t\t\t// unregister file
\t\t\tif (RuntimeDiagnostics::IncidentContextEnabled())
\t\t\t\tRuntimeDiagnostics::RecordResourceClose(fileHandle);
\t\t\tsFileHandleTable.ReleaseHandle(fileHandle); // todo - use the error code of this
''',
    "resource close attribution",
)
fsa = replace_once(
    fsa,
    '''\t\t\tFSCVirtualFile* fscFile = sFileHandleTable.GetByHandle(fileHandle);
\t\t\tif (!fscFile)
\t\t\t\treturn FSA_RESULT::INVALID_FILE_HANDLE;

\t\t\tuint32 bytesToRead = transferSize;
''',
    '''\t\t\tFSCVirtualFile* fscFile = sFileHandleTable.GetByHandle(fileHandle);
\t\t\tif (!fscFile)
\t\t\t\treturn FSA_RESULT::INVALID_FILE_HANDLE;

\t\t\tconst bool diagResourceRead = RuntimeDiagnostics::IncidentContextEnabled();
\t\t\tuint32 diagResourceOffset = 0;
\t\t\tif (diagResourceRead)
\t\t\t\tdiagResourceOffset = (flags & FSA_CMD_FLAG_SET_POS) != 0 ? filePos : fsc_getFileSeek(fscFile);

\t\t\tuint32 bytesToRead = transferSize;
''',
    "resource read offset capture",
)
fsa = replace_once(
    fsa,
    '''\t\t\tuint32 bytesSuccessfullyRead = fsc_readFile(fscFile, destPtr, bytesToRead);
\t\t\tif (transferElementSize == 0)
''',
    '''\t\t\tuint32 bytesSuccessfullyRead = fsc_readFile(fscFile, destPtr, bytesToRead);
\t\t\tif (diagResourceRead)
\t\t\t\tRuntimeDiagnostics::RecordResourceRead(fileHandle, diagResourceOffset, bytesToRead, bytesSuccessfullyRead);
\t\t\tif (transferElementSize == 0)
''',
    "resource read breadcrumb",
)
fsa_path.write_text(fsa, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Image-layout breadcrumbs: preserve the actual stage/access masks together
# with the subresource transition only while incident context is active.
# ---------------------------------------------------------------------------
renderer_h_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h")
renderer_h = renderer_h_path.read_text(encoding="utf-8")
func_start = renderer_h.find("\tvoid barrier_image(VkImage imageVk, VkImageSubresourceRange& subresourceRange, VkImageLayout oldLayout, VkImageLayout newLayout)")
cmd_pos = renderer_h.find("\t\tvkCmdPipelineBarrier(m_state.currentCommandBuffer,", func_start)
if func_start < 0 or cmd_pos < 0:
    raise RuntimeError("barrier_image diagnostic insertion point not found")
if "RecordImageLayoutBreadcrumb(diagLayout)" in renderer_h[func_start:cmd_pos]:
    raise RuntimeError("image-layout breadcrumb already installed")
layout_code = r'''		if (RuntimeDiagnostics::IncidentContextEnabled())
		{
			RuntimeDiagnostics::ImageLayoutBreadcrumb diagLayout{};
			diagLayout.image = (uint64_t)imageVk;
			diagLayout.srcStages = (uint64_t)srcStages;
			diagLayout.dstStages = (uint64_t)dstStages;
			diagLayout.srcAccess = (uint64_t)imageMemBarrier.srcAccessMask;
			diagLayout.dstAccess = (uint64_t)imageMemBarrier.dstAccessMask;
			diagLayout.oldLayout = (uint32_t)oldLayout;
			diagLayout.newLayout = (uint32_t)newLayout;
			diagLayout.aspectMask = (uint32_t)subresourceRange.aspectMask;
			diagLayout.baseMip = subresourceRange.baseMipLevel;
			diagLayout.levelCount = subresourceRange.levelCount;
			diagLayout.baseLayer = subresourceRange.baseArrayLayer;
			diagLayout.layerCount = subresourceRange.layerCount;
			RuntimeDiagnostics::RecordImageLayoutBreadcrumb(diagLayout);
		}

'''
renderer_h = renderer_h[:cmd_pos] + layout_code + renderer_h[cmd_pos:]

renderer_h = replace_once(
    renderer_h,
    '''\tvoid LogDiagnosticIncidentContext(const char* reason) const;
''',
    '''\tvoid LogDiagnosticIncidentContext(const char* reason, uint64_t subjectA = 0, uint64_t subjectB = 0,
\t\tconst RendererShaderVk* shader = nullptr, const char* shaderSource = nullptr,
\t\tuint64_t cacheH1 = 0, uint64_t cacheH2 = 0, bool isRenderThread = false) const;
''',
    "incident logger extended declaration",
)
renderer_h = replace_once(
    renderer_h,
    '''\tVkDebugUtilsMessengerEXT m_debugCallback = nullptr;
\tvolatile bool m_destructionRequested = false;
''',
    '''\tVkDebugUtilsMessengerEXT m_debugCallback = nullptr;
\tstruct DiagnosticDeviceSnapshot
\t{
\t\tbool valid{};
\t\tstd::string deviceName;
\t\tuint32_t vendorId{};
\t\tuint32_t deviceId{};
\t\tuint32_t driverVersion{};
\t\tuint32_t apiVersion{};
\t\tuint32_t driverId{};
\t\tstd::string driverName;
\t\tstd::string driverInfo;
\t} m_diagDeviceSnapshot{};
\tvolatile bool m_destructionRequested = false;
''',
    "cached diagnostic device snapshot",
)
renderer_h_path.write_text(renderer_h, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Cache device/driver identity from Vulkan queries Cemu already performs.
# Incident handling itself must make no post-device-lost Vulkan calls.
# ---------------------------------------------------------------------------
renderer_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
renderer = renderer_path.read_text(encoding="utf-8")
renderer = replace_once(
    renderer,
    '''\tvkGetPhysicalDeviceProperties2(m_physicalDevice, &properties);
\tswitch (properties.properties.vendorID)
''',
    '''\tvkGetPhysicalDeviceProperties2(m_physicalDevice, &properties);
\tm_diagDeviceSnapshot.valid = true;
\tm_diagDeviceSnapshot.deviceName = properties.properties.deviceName;
\tm_diagDeviceSnapshot.vendorId = properties.properties.vendorID;
\tm_diagDeviceSnapshot.deviceId = properties.properties.deviceID;
\tm_diagDeviceSnapshot.driverVersion = properties.properties.driverVersion;
\tm_diagDeviceSnapshot.apiVersion = properties.properties.apiVersion;
\tif (m_featureControl.deviceExtensions.driver_properties)
\t{
\t\tm_diagDeviceSnapshot.driverId = (uint32_t)driverProperties.driverID;
\t\tm_diagDeviceSnapshot.driverName = driverProperties.driverName;
\t\tm_diagDeviceSnapshot.driverInfo = driverProperties.driverInfo;
\t}
\tswitch (properties.properties.vendorID)
''',
    "cache already-queried Vulkan identity",
)

logger_start = renderer.find("void VulkanRenderer::LogDiagnosticIncidentContext(")
ctor_start = renderer.find("VulkanRenderer::VulkanRenderer() : Renderer(RendererAPI::Vulkan)", logger_start)
if logger_start < 0 or ctor_start < 0:
    raise RuntimeError("existing incident logger body not found")
new_logger = r'''void VulkanRenderer::LogDiagnosticIncidentContext(const char* reason, uint64_t subjectA, uint64_t subjectB,
	const RendererShaderVk* shader, const char* shaderSource, uint64_t cacheH1, uint64_t cacheH2, bool isRenderThread) const
{
	if (!RuntimeDiagnostics::IncidentContextEnabled())
		return;

	const auto gate = RuntimeDiagnostics::AcquireIncident(reason, subjectA, subjectB);
	if (!gate.emit)
		return;

	std::lock_guard<std::mutex> incidentLock(RuntimeDiagnostics::g_incidentLogMutex);
	const uint64_t nowNs = RuntimeDiagnostics::DiagnosticNowNs();
	cemuLog_log(LogType::Force,
		"[ADRENO_INCIDENT] BEGIN incident={} key={:016x} reason={} subjectA={:016x} subjectB={:016x} repeatsSuppressed={}",
		gate.id, gate.key, reason ? reason : "unknown", subjectA, subjectB, gate.suppressed);

	if (m_diagDeviceSnapshot.valid)
	{
		cemuLog_log(LogType::Force,
			"[ADRENO_DEVICE] incident={} name={} vendor=0x{:04x} device=0x{:04x} driverRaw=0x{:08x} driver={}.{}.{} api={}.{}.{}",
			gate.id, m_diagDeviceSnapshot.deviceName, m_diagDeviceSnapshot.vendorId, m_diagDeviceSnapshot.deviceId,
			m_diagDeviceSnapshot.driverVersion,
			VK_VERSION_MAJOR(m_diagDeviceSnapshot.driverVersion), VK_VERSION_MINOR(m_diagDeviceSnapshot.driverVersion), VK_VERSION_PATCH(m_diagDeviceSnapshot.driverVersion),
			VK_VERSION_MAJOR(m_diagDeviceSnapshot.apiVersion), VK_VERSION_MINOR(m_diagDeviceSnapshot.apiVersion), VK_VERSION_PATCH(m_diagDeviceSnapshot.apiVersion));
		if (!m_diagDeviceSnapshot.driverName.empty() || !m_diagDeviceSnapshot.driverInfo.empty())
		{
			cemuLog_log(LogType::Force, "[ADRENO_DRIVER] incident={} id={} name={} info={}",
				gate.id, m_diagDeviceSnapshot.driverId, m_diagDeviceSnapshot.driverName, m_diagDeviceSnapshot.driverInfo);
		}
	}
	else
	{
		cemuLog_log(LogType::Force, "[ADRENO_DEVICE] incident={} cached_snapshot=unavailable", gate.id);
	}

	cemuLog_log(LogType::Force,
		"[ADRENO_FEATURES] incident={} sync2={} dynamicRendering={} floatControls={} depthClip={} pipelineRobustness={} feedbackLayout={} feedbackDynamic={} pipelineFeedback={} cacheControl={} customBorder={} minUBOAlign={} nonCoherentAtom={}",
		gate.id,
		m_featureControl.deviceExtensions.synchronization2 ? 1 : 0,
		m_featureControl.deviceExtensions.dynamic_rendering ? 1 : 0,
		m_featureControl.deviceExtensions.shader_float_controls ? 1 : 0,
		m_featureControl.deviceExtensions.depth_clip_enable ? 1 : 0,
		m_featureControl.deviceExtensions.pipeline_robustness ? 1 : 0,
		m_featureControl.deviceExtensions.attachment_feedback_loop_layout ? 1 : 0,
		m_featureControl.deviceExtensions.attachment_feedback_loop_dynamic_state ? 1 : 0,
		m_featureControl.deviceExtensions.pipeline_feedback ? 1 : 0,
		m_featureControl.deviceExtensions.pipeline_creation_cache_control ? 1 : 0,
		m_featureControl.deviceExtensions.custom_border_color_without_format ? 1 : 0,
		m_featureControl.limits.minUniformBufferOffsetAlignment,
		m_featureControl.limits.nonCoherentAtomSize);

	if (shader)
	{
		const char* stage = "unknown";
		switch (shader->GetType())
		{
		case RendererShader::ShaderType::kVertex: stage = "vs"; break;
		case RendererShader::ShaderType::kFragment: stage = "ps"; break;
		case RendererShader::ShaderType::kGeometry: stage = "gs"; break;
		}

		std::array<std::pair<uint64_t, uint64_t>, 32> dependencies{};
		size_t dependencyCount = 0;
		RendererShaderVk::s_dependencyLock.lock();
		for (const auto* pipeline : shader->list_pipelineInfo)
		{
			if (!pipeline || dependencyCount >= dependencies.size())
				continue;
			dependencies[dependencyCount++] = { pipeline->stateHash, pipeline->minimalStateHash };
		}
		const size_t dependencyTotal = shader->list_pipelineInfo.size();
		RendererShaderVk::s_dependencyLock.unlock();

		cemuLog_log(LogType::Force,
			"[ADRENO_SHADER] incident={} stage={} id={}-{:08x} source={} cacheKey={:016x}:{:016x} renderThread={} dependencies={} dependenciesShown={}",
			gate.id, stage, stage, (uint32_t)subjectA, shaderSource ? shaderSource : "unknown",
			cacheH1, cacheH2, isRenderThread ? 1 : 0, dependencyTotal, dependencyCount);
		for (size_t i = 0; i < dependencyCount; ++i)
		{
			cemuLog_log(LogType::Force,
				"[ADRENO_SHADER_PIPELINE] incident={} index={} state={:016x} minimal={:016x}",
				gate.id, i, dependencies[i].first, dependencies[i].second);
		}
	}

	RuntimeDiagnostics::ForEachRecentResourceBreadcrumb([&](const RuntimeDiagnostics::ResourceBreadcrumb& b, size_t age)
	{
		const double ageMs = nowNs >= b.timestampNs ? (double)(nowNs - b.timestampNs) / 1000000.0 : 0.0;
		cemuLog_log(LogType::Force,
			"[ADRENO_RESOURCE] incident={} age={} ageMs={:.3f} seq={} handle=0x{:08x} offset=0x{:x} requested={} actual={} path={}",
			gate.id, age, ageMs, b.seq, b.handle, b.offset, b.requestedBytes, b.actualBytes, b.path);
	});

	RuntimeDiagnostics::ForEachRecentImageLayoutBreadcrumb([&](const RuntimeDiagnostics::ImageLayoutBreadcrumb& b, size_t age)
	{
		const double ageMs = nowNs >= b.timestampNs ? (double)(nowNs - b.timestampNs) / 1000000.0 : 0.0;
		cemuLog_log(LogType::Force,
			"[ADRENO_IMAGE_LAYOUT] incident={} age={} ageMs={:.3f} seq={} image=0x{:x} old={} new={} srcStage=0x{:x} dstStage=0x{:x} srcAccess=0x{:x} dstAccess=0x{:x} aspect=0x{:x} mip={}+{} layer={}+{}",
			gate.id, age, ageMs, b.seq, b.image, b.oldLayout, b.newLayout, b.srcStages, b.dstStages,
			b.srcAccess, b.dstAccess, b.aspectMask, b.baseMip, b.levelCount, b.baseLayer, b.layerCount);
	});

	RuntimeDiagnostics::ForEachRecentDrawBreadcrumb([&](const RuntimeDiagnostics::DrawBreadcrumb& b, size_t age)
	{
		cemuLog_log(LogType::Force,
			"[ADRENO_DRAW] incident={} age={} seq={} frame={} draw={} cmd={} pipe={:016x} fbo={:016x} fboSize={}x{} colors={} depth={} prim={} flush={} feedback=0x{:x} vsId=VS-{:08x} vs={:016x}_{:016x} psId=PS-{:08x} ps={:016x}_{:016x} gsId=GS-{:08x} gs={:016x}_{:016x} vds={:016x} pds={:016x} gds={:016x} descTex={} descUBO={} descSSBO={} descViews={} descFboCandidates={} indices={} instances={}",
			gate.id, age, b.seq, b.frame, b.draw, b.commandBufferSlot, b.pipeline, b.fbo,
			b.fboWidth, b.fboHeight, b.fboColorCount, b.fboHasDepth, b.primitiveMode, b.flushIndex, b.feedbackAspect,
			(uint32_t)b.vsBase, b.vsBase, b.vsAux, (uint32_t)b.psBase, b.psBase, b.psAux, (uint32_t)b.gsBase, b.gsBase, b.gsAux,
			b.vertexDescriptor, b.pixelDescriptor, b.geometryDescriptor,
			b.descriptorTextures, b.descriptorUniformBuffers, b.descriptorStorageBuffers, b.descriptorViews, b.descriptorFboCandidates,
			b.indexCount, b.instanceCount);
	});
	cemuLog_log(LogType::Force, "[ADRENO_INCIDENT] END incident={} reason={}", gate.id, reason ? reason : "unknown");
}

'''
renderer = renderer[:logger_start] + new_logger + renderer[ctor_start:]
renderer_path.write_text(renderer, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Shader source provenance: distinguish precompiled-cache SPIR-V from a fresh
# glslang translation and carry the exact cache key/render-thread state into a
# serialized shader incident. Direct shader->pipeline dependencies are emitted
# by VulkanRenderer while holding the existing dependency lock only for copyout.
# ---------------------------------------------------------------------------
shader_h_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.h")
shader_h = shader_h_path.read_text(encoding="utf-8")
shader_h = replace_once(
    shader_h,
    "\tvoid CreateVkShaderModule(std::span<uint32> spirvBuffer);\n",
    "\tvoid CreateVkShaderModule(std::span<uint32> spirvBuffer, const char* diagnosticSource, uint64 diagnosticCacheH1, uint64 diagnosticCacheH2, bool isRenderThread);\n",
    "shader module provenance declaration",
)
shader_h_path.write_text(shader_h, encoding="utf-8", newline="\n")

shader_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp")
shader = shader_path.read_text(encoding="utf-8")
shader = replace_once(
    shader,
    "void RendererShaderVk::CreateVkShaderModule(std::span<uint32> spirvBuffer)\n",
    "void RendererShaderVk::CreateVkShaderModule(std::span<uint32> spirvBuffer, const char* diagnosticSource, uint64 diagnosticCacheH1, uint64 diagnosticCacheH2, bool isRenderThread)\n",
    "shader module provenance definition",
)
shader = replace_once(
    shader,
    '''\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ShaderCreation))
\t\tcemuLog_log(LogType::Force, "[SHADER_CREATE] stage={} base={:016x} aux={:016x} spirvBytes={} result={}", DiagnosticShaderStageName(GetType()), m_baseHash, m_auxHash, spirvBuffer.size_bytes(), (sint32)result);
''',
    '''\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ShaderCreation))
\t\tcemuLog_log(LogType::Force, "[SHADER_CREATE] stage={} base={:016x} aux={:016x} source={} cacheKey={:016x}:{:016x} renderThread={} spirvBytes={} result={}",
\t\t\tDiagnosticShaderStageName(GetType()), m_baseHash, m_auxHash, diagnosticSource ? diagnosticSource : "unknown",
\t\t\tdiagnosticCacheH1, diagnosticCacheH2, isRenderThread ? 1 : 0, spirvBuffer.size_bytes(), (sint32)result);
''',
    "shader creation provenance log",
)
shader = replace_once(
    shader,
    'VulkanRenderer::GetInstance()->LogDiagnosticIncidentContext("shader_module_create_failure");',
    'VulkanRenderer::GetInstance()->LogDiagnosticIncidentContext("shader_module_create_failure", m_baseHash, m_auxHash, this, diagnosticSource, diagnosticCacheH1, diagnosticCacheH2, isRenderThread);',
    "shader module provenance incident",
)
shader = replace_once(
    shader,
    '''\t\t\tCreateVkShaderModule(std::span<uint32>((uint32*)cacheFileData.data(), cacheFileData.size() / sizeof(uint32)));
''',
    '''\t\t\tCreateVkShaderModule(std::span<uint32>((uint32*)cacheFileData.data(), cacheFileData.size() / sizeof(uint32)), "spirv_cache", h1, h2, isRenderThread);
''',
    "cached SPIR-V source attribution",
)
store_anchor = '''\t// store in cache, unless it got compiled with debug info or is a modified shader from a gfx pack
\tif (s_spirvCache && m_isGameShader && m_isGfxPackShader == false && !compileWithDebugInfo)
\t{
\t\tuint64 h1, h2;
\t\tGenerateShaderPrecompiledCacheFilename(m_type, m_baseHash, m_auxHash, h1, h2);
\t\ts_spirvCache->AddFile({ h1, h2 }, (const uint8*)spirvBuffer.data(), spirvBuffer.size() * sizeof(uint32));
\t}

\tCreateVkShaderModule(spirvBuffer);
'''
store_new = '''\t// store in cache, unless it got compiled with debug info or is a modified shader from a gfx pack
\tuint64 diagnosticCacheH1 = 0;
\tuint64 diagnosticCacheH2 = 0;
\tconst bool diagnosticNeedsCacheKey = RuntimeDiagnostics::IncidentContextEnabled() ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ShaderCreation) ||
\t\tRuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DumpFailedShader);
\tconst bool canStorePrecompiled = s_spirvCache && m_isGameShader && m_isGfxPackShader == false && !compileWithDebugInfo;
\tif ((canStorePrecompiled || diagnosticNeedsCacheKey) && m_isGameShader && m_isGfxPackShader == false)
\t\tGenerateShaderPrecompiledCacheFilename(m_type, m_baseHash, m_auxHash, diagnosticCacheH1, diagnosticCacheH2);
\tif (canStorePrecompiled)
\t\ts_spirvCache->AddFile({ diagnosticCacheH1, diagnosticCacheH2 }, (const uint8*)spirvBuffer.data(), spirvBuffer.size() * sizeof(uint32));

\tCreateVkShaderModule(spirvBuffer, "fresh_compile", diagnosticCacheH1, diagnosticCacheH2, isRenderThread);
'''
shader = replace_once(shader, store_anchor, store_new, "fresh SPIR-V source attribution")
shader_path.write_text(shader, encoding="utf-8", newline="\n")


# Correlate generic failures with a stable subject so dedupe never collapses
# unrelated shaders/pipelines into one repeating incident.
pipeline_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp")
pipeline = pipeline_path.read_text(encoding="utf-8")
pipeline = replace_once(
    pipeline,
    'vkRenderer->LogDiagnosticIncidentContext("pipeline_create_failure");',
    'vkRenderer->LogDiagnosticIncidentContext("pipeline_create_failure", m_diagPipelineInfo->stateHash, m_diagPipelineInfo->minimalStateHash);',
    "pipeline incident subject",
)
pipeline_path.write_text(pipeline, encoding="utf-8", newline="\n")

renderer = renderer_path.read_text(encoding="utf-8")
renderer = renderer.replace(
    'LogDiagnosticIncidentContext(result == VK_ERROR_DEVICE_LOST ? "queue_submit_device_lost" : "queue_submit_error");',
    'LogDiagnosticIncidentContext(result == VK_ERROR_DEVICE_LOST ? "queue_submit_device_lost" : "queue_submit_error", (uint64_t)(uint32_t)result, (uint64_t)m_commandBufferIndex);'
)
renderer = renderer.replace(
    'LogDiagnosticIncidentContext(fenceStatus == VK_ERROR_DEVICE_LOST ? "fence_device_lost" : "fence_error");',
    'LogDiagnosticIncidentContext(fenceStatus == VK_ERROR_DEVICE_LOST ? "fence_device_lost" : "fence_error", (uint64_t)(uint32_t)fenceStatus, (uint64_t)m_commandBufferSyncIndex);'
)
renderer_path.write_text(renderer, encoding="utf-8", newline="\n")

print("[adreno-final-triage] incident IDs/dedupe, cached device identity, resource/layout history and shader provenance installed")
