from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)
    print(f"[adreno-final-verify] OK {message}")


header = read("src/diagnostics/RuntimeDiagnostics.h")
main = read("src/gui/wxgui/MainWindow.cpp")
renderer_h = read("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h")
renderer = read("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
shader_h = read("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.h")
shader = read("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp")
pipeline = read("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp")
fsa = read("src/Cafe/IOSU/fsa/iosu_fsa.cpp")

# ---------------------------------------------------------------------------
# OFF path and safe UI
# ---------------------------------------------------------------------------
require("inline std::atomic_bool g_incidentContextActive{};" in header,
        "incident context has a single atomic hot-path gate")
incident_match = re.search(r"inline bool IncidentContextEnabled\(\)\s*\{(.*?)\n\}", header, re.S)
require(incident_match is not None, "IncidentContextEnabled body found")
incident_body = incident_match.group(1)
require("g_incidentContextActive.load(std::memory_order_relaxed)" in incident_body,
        "incident hot path is one atomic load")
for flag in ("PipelineFailure", "GLSLCompileFailure", "SPIRVCompileFailure", "DeviceLostSubmitError", "DumpFailedShader"):
    require(f"Flag::{flag}" in header[header.find("RefreshIncidentContextActive"):header.find("inline bool Enabled")],
            f"{flag} participates in incident gate refresh")

require('_("Disable all")' in main, "UI exposes a one-way Disable all control")
require('_("Adreno Triage")' in main, "UI exposes Adreno Triage preset")
require("Diagnostics master" not in main, "unsafe bulk-enable master checkbox is absent")
require("RuntimeDiagnostics::SetAll(true)" not in main, "no UI code can bulk-enable every diagnostic")
require("DiagFlag::DumpEveryShader" in main, "DumpEveryShader remains available as a manual checkbox")
triage_start = main.find("else if (p == 7)")
triage_end = main.find("RefreshChecks();", triage_start)
require(triage_start >= 0 and triage_end > triage_start, "Adreno Triage preset body found")
triage_body = main[triage_start:triage_end]
for flag in ("PipelineFailure", "PipelineCacheMismatch", "GLSLCompileFailure", "SPIRVCompileFailure", "DumpFailedShader", "DeviceLostSubmitError"):
    require(f"DiagFlag::{flag}" in triage_body, f"Adreno Triage enables {flag}")
require("DumpEveryShader" not in triage_body, "Adreno Triage never enables DumpEveryShader")

# ---------------------------------------------------------------------------
# Incident serialization, stable IDs, and duplicate suppression
# ---------------------------------------------------------------------------
for token in (
    "g_incidentLogMutex",
    "g_incidentSequence",
    "IncidentDedupEntry",
    "AcquireIncident",
    "repeatsSuppressed",
):
    require(token in header or token in renderer, f"incident mechanism contains {token}")
require("std::lock_guard<std::mutex> incidentLock(RuntimeDiagnostics::g_incidentLogMutex)" in renderer,
        "a full incident block is serialized")
require("[ADRENO_INCIDENT] BEGIN incident={}" in renderer and "[ADRENO_INCIDENT] END incident={}" in renderer,
        "incident BEGIN/END carry the same stable incident ID")
require("kRepeatWindowNs = 1000000000ULL" in header,
        "rapid duplicate incidents are bounded by a repeat window")

# ---------------------------------------------------------------------------
# Device-lost safety: incident logging may use only data cached while healthy.
# ---------------------------------------------------------------------------
logger_start = renderer.find("void VulkanRenderer::LogDiagnosticIncidentContext(")
logger_end = renderer.find("VulkanRenderer::VulkanRenderer() : Renderer(RendererAPI::Vulkan)", logger_start)
require(logger_start >= 0 and logger_end > logger_start, "final incident logger body found")
logger = renderer[logger_start:logger_end]
for forbidden in (
    "vkGetPhysicalDeviceProperties",
    "vkGetPhysicalDeviceFeatures",
    "vkGetDevice",
    "vkEnumerate",
):
    require(forbidden not in logger, f"incident logger makes no post-fault Vulkan query: {forbidden}")
require("m_diagDeviceSnapshot" in logger, "incident logger uses cached device identity")
require("m_diagDeviceSnapshot.deviceName = properties.properties.deviceName" in renderer,
        "device identity is cached from Cemu's existing healthy-state query")
require("m_diagDeviceSnapshot.driverInfo = driverProperties.driverInfo" in renderer,
        "driver identity is cached from Cemu's existing healthy-state query")

# ---------------------------------------------------------------------------
# Shader provenance and direct shader->pipeline correlation
# ---------------------------------------------------------------------------
require("diagnosticSource" in shader_h and "diagnosticCacheH1" in shader_h and "isRenderThread" in shader_h,
        "shader module creation carries provenance metadata")
require('"spirv_cache"' in shader and '"fresh_compile"' in shader,
        "shader incidents distinguish cached SPIR-V from fresh translation")
require("cacheKey={:016x}:{:016x}" in shader and "renderThread={}" in shader,
        "shader creation log includes cache key and render-thread state")
require('LogDiagnosticIncidentContext("shader_module_create_failure", m_baseHash, m_auxHash, this, diagnosticSource' in shader,
        "shader module failure uses base/aux hash as incident subject")
require("[ADRENO_SHADER] incident={}" in renderer and "[ADRENO_SHADER_PIPELINE] incident={}" in renderer,
        "serialized incident contains shader provenance and direct pipeline dependencies")
require("RendererShaderVk::s_dependencyLock.lock()" in logger and "shader->list_pipelineInfo" in logger,
        "shader dependency list is copied under its existing lock")

# ---------------------------------------------------------------------------
# Resource context: path/handle/offset tracking is active only with incident
# diagnostics and explicitly identifies handles opened before diagnostics.
# ---------------------------------------------------------------------------
require('#include "diagnostics/RuntimeDiagnostics.h"' in fsa, "FSA resource hooks include RuntimeDiagnostics")
for token in ("RecordResourceOpen", "RecordResourceRead", "RecordResourceClose"):
    require(token in fsa, f"FSA resource hook wired: {token}")
require("diagResourceRead = RuntimeDiagnostics::IncidentContextEnabled()" in fsa,
        "FSA read offset lookup is skipped while incident diagnostics are OFF")
require("<unknown-open-before-diagnostics>" in header,
        "already-open file handles are labeled honestly instead of guessed")
require("[ADRENO_RESOURCE] incident={}" in logger,
        "recent file reads are emitted inside the same incident block")
require("kResourceBreadcrumbCapacity = 32" in header,
        "resource history is bounded")

# ---------------------------------------------------------------------------
# Image-layout history: preserve actual stage/access/layout/subresource facts.
# ---------------------------------------------------------------------------
require("RuntimeDiagnostics::RecordImageLayoutBreadcrumb(diagLayout)" in renderer_h,
        "barrier_image feeds incident layout history")
for token in ("srcStages", "dstStages", "srcAccess", "dstAccess", "oldLayout", "newLayout", "aspectMask", "baseMip", "baseLayer"):
    require(token in renderer_h or token in header, f"layout breadcrumb preserves {token}")
require("[ADRENO_IMAGE_LAYOUT] incident={}" in logger,
        "recent image transitions are emitted inside the same incident block")
require("kImageLayoutBreadcrumbCapacity = 64" in header,
        "image-layout history is bounded")

# ---------------------------------------------------------------------------
# Existing protected release behavior remains mandatory.
# ---------------------------------------------------------------------------
query = read("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanQuery.cpp")
api = read("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanAPI.h")
require("UseDirectQueryReadbackWorkaround" in query,
        "protected direct-query workaround remains present")
require("0x00050000101AFF00ULL" in query and "0x000500001011B900ULL" in query,
        "Star Fox Zero JP and Bayonetta 2 JP title gates remain present")
require(api.count("VKFUNC_DEVICE(vkGetQueryPoolResults);") == 1,
        "vkGetQueryPoolResults loader remains unique")

# Final generated release sources must remain free of the old behavior-changing
# experiment harness.
legacy = []
for pattern in ("src/**/*.cpp", "src/**/*.h", "src/**/*.hpp"):
    for path in ROOT.glob(pattern):
        try:
            data = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "RuntimeExperiments" in data:
            legacy.append(path.relative_to(ROOT).as_posix())
require(not legacy, f"no RuntimeExperiments dependency survives final triage; refs={legacy}")

print("[adreno-final-verify] PASS")
