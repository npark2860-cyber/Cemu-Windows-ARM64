from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)
    print(f"[adreno-complete-verify] OK {message}")


header_rel = "src/diagnostics/RuntimeDiagnostics.h"
header = read(header_rel)
main = read("src/gui/wxgui/MainWindow.cpp")
renderer_h = read("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h")
renderer = read("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
shader_h = read("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.h")
shader = read("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp")
pipeline = read("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp")
fsa = read("src/Cafe/IOSU/fsa/iosu_fsa.cpp")

# ---------------------------------------------------------------------------
# Base 77/77 lean diagnostic contract
# ---------------------------------------------------------------------------
require("inline std::array<std::atomic_bool, kFlagCount> g_flags{};" in header,
        "all RuntimeDiagnostics flags default OFF")
implemented_match = re.search(
    r"inline bool IsImplemented\(Flag flag\)\s*\{(.*?)\n\}\n\ninline bool IsIncidentContextFlag",
    header,
    re.S,
)
require(implemented_match is not None, "final IsImplemented body found")
implemented = set(re.findall(r"case Flag::([A-Za-z0-9_]+):", implemented_match.group(1)))
require(len(implemented) == 77, f"all 77 diagnostics are concretely implemented; found={len(implemented)}")

items_match = re.search(r"static constexpr DiagItem kDiagItems\[\] = \{(.*?)\n\};", main, re.S)
require(items_match is not None, "ARM64 Diagnostics item list found")
ui_items = set(re.findall(r"DiagFlag::([A-Za-z0-9_]+)", items_match.group(1)))
require(ui_items == implemented,
        f"UI item set exactly equals implemented probes; missing={sorted(implemented-ui_items)} dead={sorted(ui_items-implemented)}")
require("Not wired to a runtime probe in this build" not in main,
        "no dead/grey unsupported diagnostic checkbox remains")

# Consumer check. Remove the declaration-only IsImplemented switch; helper-level
# consumers that legitimately live in RuntimeDiagnostics.h remain visible.
header_without_impl = header[:implemented_match.start()] + header[implemented_match.end():]
source_texts = {header_rel: header_without_impl}
for pattern in ("src/**/*.cpp", "src/**/*.h", "src/**/*.hpp"):
    for path in ROOT.glob(pattern):
        rel = path.relative_to(ROOT).as_posix()
        if rel in (header_rel, "src/gui/wxgui/MainWindow.cpp"):
            continue
        try:
            source_texts[rel] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            pass
missing_consumers = []
for flag in sorted(implemented):
    patterns = (f"RuntimeDiagnostics::Flag::{flag}", f"Flag::{flag}")
    if not any(any(token in data for token in patterns) for data in source_texts.values()):
        missing_consumers.append(flag)
require(not missing_consumers, f"every selectable flag has a runtime consumer; missing={missing_consumers}")

# The final source must not call the behavior-changing experiment harness.
legacy_refs = []
for rel, data in source_texts.items():
    if "RuntimeExperiments::" in data:
        legacy_refs.append(rel)
if "RuntimeExperiments::" in main:
    legacy_refs.append("src/gui/wxgui/MainWindow.cpp")
require(not legacy_refs, f"no RuntimeExperiments dependency survives final release sources; refs={legacy_refs}")

# ---------------------------------------------------------------------------
# Safe UI: never bulk-enable heavy diagnostics
# ---------------------------------------------------------------------------
require('_("Disable all")' in main, "UI exposes one-way Disable all")
require('_("Adreno Triage")' in main, "UI exposes Adreno Triage")
require("Diagnostics master" not in main, "unsafe master checkbox is absent")
require("RuntimeDiagnostics::SetAll(true)" not in main, "no one-click bulk-enable path exists")
require(main.count("DiagFlag::DumpEveryShader") == 1,
        "DumpEveryShader appears only as its manual checkbox, never in a preset")
triage_start = main.find("else if (p == 7)")
triage_end = main.find("RefreshChecks();", triage_start)
require(triage_start >= 0 and triage_end > triage_start, "Adreno Triage preset body found")
triage_body = main[triage_start:triage_end]
for flag in ("PipelineFailure", "PipelineCacheMismatch", "GLSLCompileFailure", "SPIRVCompileFailure", "DumpFailedShader", "DeviceLostSubmitError"):
    require(f"DiagFlag::{flag}" in triage_body, f"Adreno Triage enables {flag}")
require("DumpEveryShader" not in triage_body, "Adreno Triage never enables DumpEveryShader")

# ---------------------------------------------------------------------------
# OFF-path incident gate, bounded rings, serialization and dedupe
# ---------------------------------------------------------------------------
require("inline std::atomic_bool g_incidentContextActive{};" in header,
        "incident hot-path state is an atomic boolean")
incident_match = re.search(r"inline bool IncidentContextEnabled\(\)\s*\{(.*?)\n\}", header, re.S)
require(incident_match is not None and
        "g_incidentContextActive.load(std::memory_order_relaxed)" in incident_match.group(1),
        "IncidentContextEnabled is a single atomic load")
refresh_start = header.find("inline void RefreshIncidentContextActive()")
refresh_end = header.find("inline bool Enabled", refresh_start)
refresh = header[refresh_start:refresh_end]
for flag in ("PipelineFailure", "GLSLCompileFailure", "SPIRVCompileFailure", "DeviceLostSubmitError", "DumpFailedShader"):
    require(f"Flag::{flag}" in refresh, f"incident gate is refreshed from {flag}")
require("if (!EnsureIncidentCaptureStarted())" in header[header.find("inline void RecordDrawBreadcrumb"):],
        "draw breadcrumb capture exits before work while incident diagnostics are OFF")
require("kResourceBreadcrumbCapacity = 32" in header and "kImageLayoutBreadcrumbCapacity = 64" in header and "kDrawBreadcrumbCapacity = 64" in header,
        "all correlation histories are bounded")
for token in ("g_incidentLogMutex", "g_incidentSequence", "IncidentDedupEntry", "AcquireIncident", "kRepeatWindowNs = 1000000000ULL"):
    require(token in header, f"incident state contains {token}")
require("std::lock_guard<std::mutex> incidentLock(RuntimeDiagnostics::g_incidentLogMutex)" in renderer,
        "each full incident is serialized")
require("[ADRENO_INCIDENT] BEGIN incident={}" in renderer and "[ADRENO_INCIDENT] END incident={}" in renderer,
        "incident output has stable BEGIN/END IDs")
require("repeatsSuppressed={}" in renderer, "repeat suppression count is surfaced")
require("if (age >= 12)" in renderer and renderer.count("if (age >= 24)") >= 2,
        "incident output is compact even though the in-memory rings are deeper")

# ---------------------------------------------------------------------------
# Device-lost-safe identity: cached from already-existing healthy queries only
# ---------------------------------------------------------------------------
logger_start = renderer.find("void VulkanRenderer::LogDiagnosticIncidentContext(")
logger_end = renderer.find("VulkanRenderer::VulkanRenderer() : Renderer(RendererAPI::Vulkan)", logger_start)
require(logger_start >= 0 and logger_end > logger_start, "final incident logger found")
logger = renderer[logger_start:logger_end]
for forbidden in ("vkGetPhysicalDeviceProperties", "vkGetPhysicalDeviceFeatures", "vkEnumerate", "vkGetDevice"):
    require(forbidden not in logger, f"post-fault incident logger does not call {forbidden}")
require("m_diagDeviceSnapshot.deviceName = properties.properties.deviceName" in renderer,
        "device identity is cached from DetermineVendor's existing property query")
require("m_diagDeviceSnapshot.driverInfo = driverProperties.driverInfo" in renderer,
        "driver identity is cached while the device is healthy")
require("[ADRENO_DEVICE] incident={}" in logger and "[ADRENO_DRIVER] incident={}" in logger and "[ADRENO_FEATURES] incident={}" in logger,
        "cached device/driver/features are part of each incident")

# ---------------------------------------------------------------------------
# Shader provenance and direct dependencies
# ---------------------------------------------------------------------------
require("diagnosticSource" in shader_h and "diagnosticCacheH1" in shader_h and "isRenderThread" in shader_h,
        "shader-module creation carries provenance metadata")
require('"spirv_cache"' in shader and '"fresh_compile"' in shader,
        "cached SPIR-V and fresh glslang paths are distinguishable")
require("diagnosticIncidentCacheH1" in shader and "diagnosticIncidentCacheH2" in shader,
        "preprocess/parse/link failures get a stable cache key when diagnostics are active")
for reason in ("glsl_preprocess_failure", "glsl_parse_failure", "glsl_link_or_mapio_failure", "spirv_empty_output", "shader_module_create_failure"):
    pos = shader.find(f'LogDiagnosticIncidentContext("{reason}"')
    require(pos >= 0, f"shader incident exists for {reason}")
    snippet = shader[pos:pos+320]
    require("m_baseHash" in snippet and "m_auxHash" in snippet,
            f"{reason} incident is keyed by the exact shader")
require("[ADRENO_SHADER] incident={}" in logger and "[ADRENO_SHADER_PIPELINE] incident={}" in logger,
        "shader incident includes source provenance and direct dependent pipelines")
require("RendererShaderVk::s_dependencyLock.lock()" in logger and "shader->list_pipelineInfo" in logger,
        "shader->pipeline dependency copy is protected by the existing lock")
require("cacheKey={:016x}:{:016x}" in shader and "renderThread={}" in shader,
        "shader creation log reports cache key and execution context")

# Shader dumps remain explicitly gated and DumpEveryShader stays manual-heavy.
require("RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DumpFailedShader)" in shader,
        "failed shader artifacts are gated")
require("RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DumpEveryShader)" in shader,
        "every-shader dump is gated")
require("[SHADER_DUMP_PREPROCESSED]" in shader and "[SPIRV_DUMP_FAILED]" in shader,
        "failure bundle preserves preprocessed GLSL and rejected SPIR-V")

# ---------------------------------------------------------------------------
# Resource attribution
# ---------------------------------------------------------------------------
require('#include "diagnostics/RuntimeDiagnostics.h"' in fsa, "FSA resource hooks are wired")
for token in ("RecordResourceOpen", "RecordResourceRead", "RecordResourceClose"):
    require(token in fsa, f"FSA contains {token}")
require("diagResourceRead = RuntimeDiagnostics::IncidentContextEnabled()" in fsa,
        "file-position lookup is skipped while incident diagnostics are OFF")
require("diagVirtualPath = __FSATranslatePath(client, path)" in fsa,
        "resource attribution stores canonical Wii U virtual paths only while enabled")
require("<unknown-open-before-diagnostics>" in header,
        "pre-existing handles are labeled unknown instead of guessed")
require("[ADRENO_RESOURCE] incident={}" in logger,
        "recent file path/handle/offset reads are inside the same incident")

# ---------------------------------------------------------------------------
# Image-layout/barrier attribution
# ---------------------------------------------------------------------------
require("RuntimeDiagnostics::RecordImageLayoutBreadcrumb(diagLayout)" in renderer_h,
        "barrier_image feeds bounded layout history")
for token in ("diagLayout.srcStages", "diagLayout.dstStages", "diagLayout.srcAccess", "diagLayout.dstAccess", "diagLayout.oldLayout", "diagLayout.newLayout", "diagLayout.aspectMask"):
    require(token in renderer_h, f"layout history captures {token}")
require("[ADRENO_IMAGE_LAYOUT] incident={}" in logger,
        "layout/access/stage history is included in each incident")

# ---------------------------------------------------------------------------
# Existing protected release behavior and lazy diagnostic GPU resources
# ---------------------------------------------------------------------------
query = read("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanQuery.cpp")
api = read("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanAPI.h")
require("UseDirectQueryReadbackWorkaround" in query,
        "protected direct-query workaround is preserved")
require("0x00050000101AFF00ULL" in query and "0x000500001011B900ULL" in query,
        "Star Fox Zero JP and Bayonetta 2 JP direct-readback title gates are preserved")
require(api.count("VKFUNC_DEVICE(vkGetQueryPoolResults);") == 1,
        "vkGetQueryPoolResults loader declaration remains unique")
create_marker = "vkCreateQueryPool(m_logicalDevice, &diagQueryInfo, nullptr, &m_diagTimestampQueryPool)"
positions = [m.start() for m in re.finditer(re.escape(create_marker), renderer)]
require(bool(positions), "GPU timestamp diagnostic has a concrete lazy query-pool path")
for pos in positions:
    prefix = renderer[max(0, pos-1800):pos]
    require("RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GpuTimestamp)" in prefix,
            "diagnostic timestamp query-pool allocation is guarded by GpuTimestamp")

print(f"[adreno-complete-verify] PASS implemented={len(implemented)} ui={len(ui_items)}")
