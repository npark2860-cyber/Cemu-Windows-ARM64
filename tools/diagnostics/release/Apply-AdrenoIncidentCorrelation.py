from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


def replace_count(text, old, new, expected, label):
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} anchors, found {count}")
    return text.replace(old, new)


# ---------------------------------------------------------------------------
# Shared, switch-gated draw breadcrumb ring.
# No new checkbox is introduced: existing failure diagnostics opt in to the
# correlation ring only while they are enabled.
# ---------------------------------------------------------------------------
header_path = Path("src/diagnostics/RuntimeDiagnostics.h")
header = header_path.read_text(encoding="utf-8")
if "#include <mutex>\n" not in header:
    header = replace_once(header, "#include <cstdint>\n", "#include <cstdint>\n#include <mutex>\n", "diagnostic breadcrumb mutex include")

anchor = '''inline bool AnyEnabled()
{
    for (size_t i = 0; i < kFlagCount; ++i)
        if (Enabled(static_cast<Flag>(i)))
            return true;
    return false;
}
'''
insert = anchor + r'''

struct DrawBreadcrumb
{
    uint64_t seq{};
    uint64_t frame{};
    uint64_t draw{};
    uint64_t pipeline{};
    uint64_t fbo{};
    uint64_t vsBase{};
    uint64_t vsAux{};
    uint64_t psBase{};
    uint64_t psAux{};
    uint64_t gsBase{};
    uint64_t gsAux{};
    uint64_t vertexDescriptor{};
    uint64_t pixelDescriptor{};
    uint64_t geometryDescriptor{};
    uint32_t commandBufferSlot{};
    uint32_t indexCount{};
    uint32_t instanceCount{};
};

inline constexpr size_t kDrawBreadcrumbCapacity = 64;
inline std::array<DrawBreadcrumb, kDrawBreadcrumbCapacity> g_drawBreadcrumbs{};
inline std::mutex g_drawBreadcrumbMutex;
inline uint64_t g_drawBreadcrumbSequence{};
inline size_t g_drawBreadcrumbHead{};
inline size_t g_drawBreadcrumbCount{};

inline bool IncidentContextEnabled()
{
    return Enabled(Flag::PipelineFailure) ||
        Enabled(Flag::GLSLCompileFailure) ||
        Enabled(Flag::SPIRVCompileFailure) ||
        Enabled(Flag::DeviceLostSubmitError) ||
        Enabled(Flag::DumpFailedShader);
}

inline void RecordDrawBreadcrumb(DrawBreadcrumb entry)
{
    if (!IncidentContextEnabled())
        return;
    std::lock_guard<std::mutex> lock(g_drawBreadcrumbMutex);
    entry.seq = ++g_drawBreadcrumbSequence;
    g_drawBreadcrumbs[g_drawBreadcrumbHead] = entry;
    g_drawBreadcrumbHead = (g_drawBreadcrumbHead + 1) % kDrawBreadcrumbCapacity;
    if (g_drawBreadcrumbCount < kDrawBreadcrumbCapacity)
        ++g_drawBreadcrumbCount;
}

template<typename TCallback>
inline void ForEachRecentDrawBreadcrumb(TCallback&& callback)
{
    std::lock_guard<std::mutex> lock(g_drawBreadcrumbMutex);
    if (g_drawBreadcrumbCount == 0)
        return;
    const size_t oldest = (g_drawBreadcrumbHead + kDrawBreadcrumbCapacity - g_drawBreadcrumbCount) % kDrawBreadcrumbCapacity;
    for (size_t i = 0; i < g_drawBreadcrumbCount; ++i)
        callback(g_drawBreadcrumbs[(oldest + i) % kDrawBreadcrumbCapacity], g_drawBreadcrumbCount - i - 1);
}
'''
header = replace_once(header, anchor, insert, "incident breadcrumb core")
header_path.write_text(header, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# VulkanRenderer exposes one common incident dumper. It prints a driver and
# feature fingerprint plus the last 64 correlated draws.
# ---------------------------------------------------------------------------
renderer_h_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h")
renderer_h = renderer_h_path.read_text(encoding="utf-8")
getter_anchor = '''\tVkInstance GetVkInstance() const { return m_instance; }
\tVkDevice GetLogicalDevice() const { return m_logicalDevice; }
\tVkPhysicalDevice GetPhysicalDevice() const { return m_physicalDevice; }
'''
getter_new = getter_anchor + '''\tvoid LogDiagnosticIncidentContext(const char* reason) const;
'''
renderer_h = replace_once(renderer_h, getter_anchor, getter_new, "incident logger declaration")
renderer_h_path.write_text(renderer_h, encoding="utf-8", newline="\n")

renderer_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
renderer = renderer_path.read_text(encoding="utf-8")
ctor_anchor = '''VulkanRenderer::VulkanRenderer() : Renderer(RendererAPI::Vulkan)
{
'''
logger_impl = r'''void VulkanRenderer::LogDiagnosticIncidentContext(const char* reason) const
{
	if (!RuntimeDiagnostics::IncidentContextEnabled())
		return;

	VkPhysicalDeviceProperties2 props2{};
	props2.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2;
	VkPhysicalDeviceDriverProperties driverProps{};
	if (m_featureControl.deviceExtensions.driver_properties)
	{
		driverProps.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES;
		props2.pNext = &driverProps;
	}
	vkGetPhysicalDeviceProperties2(m_physicalDevice, &props2);
	const auto& props = props2.properties;

	cemuLog_log(LogType::Force, "[ADRENO_INCIDENT] BEGIN reason={}", reason ? reason : "unknown");
	cemuLog_log(LogType::Force,
		"[ADRENO_DEVICE] name={} vendor=0x{:04x} device=0x{:04x} driverRaw=0x{:08x} driver={}.{}.{} api={}.{}.{}",
		props.deviceName, props.vendorID, props.deviceID, props.driverVersion,
		VK_VERSION_MAJOR(props.driverVersion), VK_VERSION_MINOR(props.driverVersion), VK_VERSION_PATCH(props.driverVersion),
		VK_VERSION_MAJOR(props.apiVersion), VK_VERSION_MINOR(props.apiVersion), VK_VERSION_PATCH(props.apiVersion));
	if (m_featureControl.deviceExtensions.driver_properties)
	{
		cemuLog_log(LogType::Force, "[ADRENO_DRIVER] id={} name={} info={}",
			(uint32)driverProps.driverID, driverProps.driverName, driverProps.driverInfo);
	}
	cemuLog_log(LogType::Force,
		"[ADRENO_FEATURES] sync2={} dynamicRendering={} floatControls={} depthClip={} pipelineRobustness={} feedbackLayout={} feedbackDynamic={} pipelineFeedback={} cacheControl={} customBorder={} minUBOAlign={} nonCoherentAtom={}",
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

	RuntimeDiagnostics::ForEachRecentDrawBreadcrumb([&](const RuntimeDiagnostics::DrawBreadcrumb& b, size_t age)
	{
		cemuLog_log(LogType::Force,
			"[ADRENO_DRAW] age={} seq={} frame={} draw={} cmd={} pipe={:016x} fbo={:016x} vs={:016x}_{:016x} ps={:016x}_{:016x} gs={:016x}_{:016x} vds={:016x} pds={:016x} gds={:016x} indices={} instances={}",
			age, b.seq, b.frame, b.draw, b.commandBufferSlot, b.pipeline, b.fbo,
			b.vsBase, b.vsAux, b.psBase, b.psAux, b.gsBase, b.gsAux,
			b.vertexDescriptor, b.pixelDescriptor, b.geometryDescriptor, b.indexCount, b.instanceCount);
	});
	cemuLog_log(LogType::Force, "[ADRENO_INCIDENT] END reason={}", reason ? reason : "unknown");
}

'''
renderer = replace_once(renderer, ctor_anchor, logger_impl + ctor_anchor, "incident logger implementation")
renderer_path.write_text(renderer, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Record the fully resolved draw context only after descriptors are known.
# ---------------------------------------------------------------------------
core_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
core = core_path.read_text(encoding="utf-8")
descriptor_anchor = '''\tm_state.activeVertexDS = vertexDS;
\tm_state.activePixelDS = pixelDS;
\tm_state.activeGeometryDS = geometryDS;
\tm_state.descriptorSetsChanged = true;

\tdraw_setRenderPass();
'''
descriptor_new = '''\tm_state.activeVertexDS = vertexDS;
\tm_state.activePixelDS = pixelDS;
\tm_state.activeGeometryDS = geometryDS;
\tm_state.descriptorSetsChanged = true;

\tif (RuntimeDiagnostics::IncidentContextEnabled())
\t{
\t\tRuntimeDiagnostics::DrawBreadcrumb b{};
\t\tb.frame = LatteGPUState.frameCounter;
\t\tb.draw = LatteGPUState.drawCallCounter;
\t\tb.commandBufferSlot = (uint32_t)m_commandBufferIndex;
\t\tb.pipeline = pipeline_info ? pipeline_info->stateHash : 0;
\t\tb.fbo = m_state.activeFBO ? m_state.activeFBO->key : 0;
\t\tb.vsBase = vertexShader ? vertexShader->baseHash : 0;
\t\tb.vsAux = vertexShader ? vertexShader->auxHash : 0;
\t\tb.psBase = pixelShader ? pixelShader->baseHash : 0;
\t\tb.psAux = pixelShader ? pixelShader->auxHash : 0;
\t\tb.gsBase = geometryShader ? geometryShader->baseHash : 0;
\t\tb.gsAux = geometryShader ? geometryShader->auxHash : 0;
\t\tb.vertexDescriptor = vertexDS ? vertexDS->stateHash : 0;
\t\tb.pixelDescriptor = pixelDS ? pixelDS->stateHash : 0;
\t\tb.geometryDescriptor = geometryDS ? geometryDS->stateHash : 0;
\t\tb.indexCount = count;
\t\tb.instanceCount = instanceCount;
\t\tRuntimeDiagnostics::RecordDrawBreadcrumb(b);
\t}

\tdraw_setRenderPass();
'''
core = replace_once(core, descriptor_anchor, descriptor_new, "correlated draw breadcrumb hook")
core_path.write_text(core, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Pipeline creation failure -> one correlated incident block.
# ---------------------------------------------------------------------------
pipeline_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp")
pipeline = pipeline_path.read_text(encoding="utf-8")
pipeline_anchor = '''\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PipelineFailure))
\t\t\t\tcemuLog_log(LogType::Force, "[ADRENO_DIAG] PIPELINE_FAIL state={:016x} min={:016x} result={}", m_diagPipelineInfo->stateHash, m_diagPipelineInfo->minimalStateHash, (sint32)result);
'''
pipeline_new = '''\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PipelineFailure))
\t\t\t{
\t\t\t\tcemuLog_log(LogType::Force, "[ADRENO_DIAG] PIPELINE_FAIL state={:016x} min={:016x} result={}", m_diagPipelineInfo->stateHash, m_diagPipelineInfo->minimalStateHash, (sint32)result);
\t\t\t\tvkRenderer->LogDiagnosticIncidentContext("pipeline_create_failure");
\t\t\t}
'''
pipeline = replace_once(pipeline, pipeline_anchor, pipeline_new, "pipeline failure incident hook")
pipeline_path.write_text(pipeline, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Shader failure phases -> the same incident format. Existing shader-specific
# logs/dumps remain authoritative; this only adds correlation context.
# ---------------------------------------------------------------------------
shader_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp")
shader = shader_path.read_text(encoding="utf-8")
module_anchor = '''\tif (result != VK_SUCCESS)
\t{
\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DumpFailedShader))
'''
module_new = '''\tif (result != VK_SUCCESS)
\t{
\t\tVulkanRenderer::GetInstance()->LogDiagnosticIncidentContext("shader_module_create_failure");
\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DumpFailedShader))
'''
shader = replace_once(shader, module_anchor, module_new, "shader module incident hook")

for label, old, reason in (
    ("GLSL preprocess incident hook", 'cemuLog_log(LogType::Force, fmt::format("GLSL Preprocessing Failed For {:016x}_{:016x}: \\\"{}\\\"", m_baseHash, m_auxHash, Shader.getInfoLog()));', "glsl_preprocess_failure"),
    ("GLSL parse incident hook", 'cemuLog_log(LogType::Force, fmt::format("GLSL parsing failed for {:016x}_{:016x}: \\\"{}\\\"", m_baseHash, m_auxHash, Shader.getInfoLog()));', "glsl_parse_failure"),
):
    shader = replace_once(shader, old, f'VulkanRenderer::GetInstance()->LogDiagnosticIncidentContext("{reason}");\n\t\t' + old, label)

link_line = 'cemuLog_log(LogType::Force, fmt::format("GLSL linking failed for {:016x}_{:016x}: \\\"{}\\\"", m_baseHash, m_auxHash, Program.getInfoLog()));'
shader = replace_count(shader, link_line,
    'VulkanRenderer::GetInstance()->LogDiagnosticIncidentContext("glsl_link_or_mapio_failure");\n\t\t' + link_line,
    2, "GLSL link/mapIO incident hooks")

spirv_anchor = '''\tif (spirvBuffer.empty())
\t{
'''
spirv_new = '''\tif (spirvBuffer.empty())
\t{
\t\tVulkanRenderer::GetInstance()->LogDiagnosticIncidentContext("spirv_empty_output");
'''
shader = replace_once(shader, spirv_anchor, spirv_new, "SPIR-V incident hook")
shader_path.write_text(shader, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Submit/fence errors -> incident dump. These calls are inside the already
# switch-gated DeviceLostSubmitError paths.
# ---------------------------------------------------------------------------
renderer = renderer_path.read_text(encoding="utf-8")
queue_line = '''\tif (result != VK_SUCCESS && RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DeviceLostSubmitError))
\t\tcemuLog_log(LogType::Force, "[VK_SUBMIT_ERROR] queueSubmit result={} deviceLost={} slot={}", (sint32)result, result == VK_ERROR_DEVICE_LOST ? 1 : 0, m_commandBufferIndex);
'''
queue_new = '''\tif (result != VK_SUCCESS && RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DeviceLostSubmitError))
\t{
\t\tcemuLog_log(LogType::Force, "[VK_SUBMIT_ERROR] queueSubmit result={} deviceLost={} slot={}", (sint32)result, result == VK_ERROR_DEVICE_LOST ? 1 : 0, m_commandBufferIndex);
\t\tLogDiagnosticIncidentContext(result == VK_ERROR_DEVICE_LOST ? "queue_submit_device_lost" : "queue_submit_error");
\t}
'''
renderer = replace_once(renderer, queue_line, queue_new, "queue-submit incident hook")

fence_line = '''\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DeviceLostSubmitError))
\t\t\tcemuLog_log(LogType::Force, "[VK_SUBMIT_ERROR] fenceStatus={} deviceLost={}", (sint32)fenceStatus, fenceStatus == VK_ERROR_DEVICE_LOST ? 1 : 0);
'''
fence_new = '''\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DeviceLostSubmitError))
\t\t{
\t\t\tcemuLog_log(LogType::Force, "[VK_SUBMIT_ERROR] fenceStatus={} deviceLost={}", (sint32)fenceStatus, fenceStatus == VK_ERROR_DEVICE_LOST ? 1 : 0);
\t\t\tLogDiagnosticIncidentContext(fenceStatus == VK_ERROR_DEVICE_LOST ? "fence_device_lost" : "fence_error");
\t\t}
'''
renderer = replace_once(renderer, fence_line, fence_new, "fence incident hook")
renderer_path.write_text(renderer, encoding="utf-8", newline="\n")

print("[adreno-incident] correlated draw/device/feature incident diagnostics installed")
