from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)
    print(f"[lean-diag-verify] OK {message}")


header_rel = "src/diagnostics/RuntimeDiagnostics.h"
header = read(header_rel)

# Runtime flags must default to OFF.
require("inline std::array<std::atomic_bool, kFlagCount> g_flags{};" in header,
        "all RuntimeDiagnostics flags default OFF")

# Determine the exact selectable set from IsImplemented().
match = re.search(
    r"inline bool IsImplemented\(Flag flag\)\s*\{(.*?)\n\}\n\ninline bool Enabled",
    header,
    re.S,
)
require(match is not None, "IsImplemented body found")
implemented = set(re.findall(r"case Flag::([A-Za-z0-9_]+):", match.group(1)))
require(bool(implemented), "at least one concrete diagnostic is implemented")

# Every implemented flag must have a real consumer outside the UI and outside
# the IsImplemented declaration itself. Keep RuntimeDiagnostics.h in the scan
# after removing IsImplemented because helper-level consumers (FrameTiming,
# DiagnosticOverhead, etc.) legitimately live there.
header_without_implemented = header[:match.start()] + header[match.end():]
source_texts = {header_rel: header_without_implemented}
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
consumer_locations = {}
for flag in sorted(implemented):
    patterns = (f"RuntimeDiagnostics::Flag::{flag}", f"Flag::{flag}")
    hits = []
    for rel, data in source_texts.items():
        if any(token in data for token in patterns):
            hits.append(rel)
    if not hits:
        missing_consumers.append(flag)
    else:
        consumer_locations[flag] = hits
require(not missing_consumers,
        f"every selectable flag has a non-UI runtime consumer; missing={missing_consumers}")

# UI contract: the final kDiagItems list and the concrete IsImplemented set
# must be identical. If a probe cannot be implemented, its item must be removed
# from kDiagItems rather than left behind as a dead/grey checkbox.
main = read("src/gui/wxgui/MainWindow.cpp")
items_match = re.search(r"static constexpr DiagItem kDiagItems\[\] = \{(.*?)\n\};", main, re.S)
require(items_match is not None, "ARM64 Diagnostics item list found")
ui_items = set(re.findall(r"DiagFlag::([A-Za-z0-9_]+)", items_match.group(1)))
missing_ui = sorted(implemented - ui_items)
dead_ui = sorted(ui_items - implemented)
require(not missing_ui and not dead_ui,
        f"UI items exactly match concrete probes; missing={missing_ui} dead={dead_ui}")

# Defense in depth: even if the candidate list is edited later, unsupported
# items must still be rejected before wxCheckBox construction.
loop_start = main.find("for (const auto& item : kDiagItems)")
continue_pos = main.find("if (!RuntimeDiagnostics::IsImplemented(item.flag))", loop_start)
checkbox_pos = main.find("new wxCheckBox", loop_start)
require(loop_start >= 0 and continue_pos > loop_start and checkbox_pos > continue_pos,
        "unsupported diagnostics are skipped before checkbox construction")
require("Not wired to a runtime probe in this build" not in main,
        "no dead/grey unsupported diagnostic checkbox UI remains")

# The release diagnostic path must not depend on the old A/B experiment
# harness. Any RuntimeExperiments reference in generated src means the lean
# contract was violated.
legacy_refs = []
for rel, data in source_texts.items():
    if "RuntimeExperiments" in data:
        legacy_refs.append(rel)
if "RuntimeExperiments" in main:
    legacy_refs.append("src/gui/wxgui/MainWindow.cpp")
require(not legacy_refs, f"no legacy RuntimeExperiments dependency in release sources; refs={legacy_refs}")

# Protect the accepted direct-query workaround and prevent the diagnostic
# timestamp path from duplicating its Vulkan loader declaration.
api = read("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanAPI.h")
require(api.count("VKFUNC_DEVICE(vkGetQueryPoolResults);") == 1,
        "vkGetQueryPoolResults loader declaration remains unique")
query = read("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanQuery.cpp")
require("UseDirectQueryReadbackWorkaround" in query,
        "title-gated direct query readback workaround is preserved")
require("0x00050000101AFF00ULL" in query and "0x000500001011B900ULL" in query,
        "Star Fox Zero JP and Bayonetta 2 JP direct-readback title gates are preserved")
require("vkGetQueryPoolResults" in query,
        "direct query readback still calls vkGetQueryPoolResults")

# GPU timestamp resources must be lazy. The diagnostic query pool is allowed to
# be created only from a branch guarded by GpuTimestamp; OFF must not allocate
# it or emit timestamp commands.
renderer = read("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
create_marker = "vkCreateQueryPool(m_logicalDevice, &diagQueryInfo, nullptr, &m_diagTimestampQueryPool)"
create_positions = [m.start() for m in re.finditer(re.escape(create_marker), renderer)]
require(bool(create_positions), "GPU timestamp diagnostic has a concrete lazy query-pool path")
for pos in create_positions:
    prefix = renderer[max(0, pos - 1800):pos]
    require("RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GpuTimestamp)" in prefix,
            "each diagnostic timestamp query-pool creation is guarded by GpuTimestamp")

# Shader dumping is useful but potentially very heavy. It must never happen
# unconditionally.
shader = read("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp")
require("RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DumpFailedShader)" in shader,
        "failed-shader dump is individually gated")
require("RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DumpEveryShader)" in shader,
        "dump-every-shader is individually gated")
require("[SPIRV_DUMP_FAILED]" in shader and "DiagnosticDumpSpirv" in shader,
        "driver-rejected shader module preserves exact SPIR-V when failed-shader dump is enabled")
require("[SHADER_DUMP_PREPROCESSED]" in shader and "PreprocessedGLSL" in shader,
        "failed shader bundle preserves preprocessed GLSL for compiler line correlation")

# Adreno incident correlation must itself obey the OFF-is-silent contract.
# Existing failure switches opt into the ring; there is deliberately no extra
# checkbox and no unconditional per-draw tracking.
incident_match = re.search(r"inline bool IncidentContextEnabled\(\)\s*\{(.*?)\n\}", header, re.S)
require(incident_match is not None, "Adreno incident-context gate exists")
incident_body = incident_match.group(1)
for required_flag in ("PipelineFailure", "GLSLCompileFailure", "SPIRVCompileFailure", "DeviceLostSubmitError", "DumpFailedShader"):
    require(f"Enabled(Flag::{required_flag})" in incident_body,
            f"incident context is controlled by existing {required_flag} switch")
record_match = re.search(r"inline void RecordDrawBreadcrumb\(DrawBreadcrumb entry\)\s*\{(.*?)\n\}", header, re.S)
require(record_match is not None and "if (!IncidentContextEnabled())" in record_match.group(1),
        "draw breadcrumb recording exits immediately while incident diagnostics are OFF")
core = read("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
require("RuntimeDiagnostics::IncidentContextEnabled()" in core and "RuntimeDiagnostics::RecordDrawBreadcrumb(b)" in core,
        "resolved draw context is recorded only through the incident gate")
require("[ADRENO_INCIDENT] BEGIN" in renderer and "[ADRENO_DEVICE]" in renderer and "[ADRENO_FEATURES]" in renderer and "[ADRENO_DRAW]" in renderer,
        "incident dump contains device/features/recent draw correlation")
require("vsId=VS-" in renderer and "psId=PS-" in renderer and "gsId=GS-" in renderer,
        "incident draw lines expose stable short shader IDs alongside full hashes")
require(all(token in header for token in ("descriptorTextures", "descriptorUniformBuffers", "descriptorStorageBuffers", "fboWidth", "fboHeight", "fboColorCount", "feedbackAspect", "flushIndex")),
        "incident breadcrumb carries compact descriptor/FBO/flush/feedback details")
require(all(token in renderer for token in ("descTex=", "descUBO=", "descSSBO=", "fboSize=", "feedback=", "flush=")),
        "incident log renders compact descriptor/FBO/synchronization details")
require("LogDiagnosticIncidentContext(\"pipeline_create_failure\")" in read("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp"),
        "pipeline failure emits correlated incident context")
require("LogDiagnosticIncidentContext(\"glsl_parse_failure\")" in shader and "LogDiagnosticIncidentContext(\"spirv_empty_output\")" in shader,
        "shader failures emit correlated incident context")
require("queue_submit_device_lost" in renderer and "fence_device_lost" in renderer,
        "submit/fence device-lost paths emit correlated incident context")

# No source-level legacy A/B switches may be injected by the release diagnostic
# path. This catches the historical failure mode where a diagnostic build
# silently modified execution behavior.
for forbidden in (
    'RuntimeExperiments::Enabled("rt-force-sync")',
    'RuntimeExperiments::Enabled("perf-skip-waw-barrier")',
    'RuntimeExperiments::Enabled("perf-skip-rt-load-barrier")',
    'RuntimeExperiments::Enabled("perf-force-pass-reuse")',
    'RuntimeExperiments::Enabled("depthclip-off")',
    'RuntimeExperiments::Enabled("pipeline-pnext-off")',
):
    offenders = [rel for rel, data in source_texts.items() if forbidden in data]
    require(not offenders, f"behavior-changing diagnostic experiment absent: {forbidden}")

print(f"[lean-diag-verify] PASS implemented={len(implemented)} ui={len(ui_items)}")
for flag in sorted(implemented):
    print(f"[lean-diag-verify]   {flag}: {consumer_locations[flag][0]}")
