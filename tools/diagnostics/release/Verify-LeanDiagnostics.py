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

# UI contract: candidate entries are harmless metadata, but an unsupported flag
# must be rejected before wxCheckBox construction. Therefore an impossible
# diagnostic produces no checkbox at all, rather than a dead/grey control.
main = read("src/gui/wxgui/MainWindow.cpp")
loop_start = main.find("for (const auto& item : kDiagItems)")
continue_pos = main.find("if (!RuntimeDiagnostics::IsImplemented(item.flag))", loop_start)
checkbox_pos = main.find("new wxCheckBox", loop_start)
require(loop_start >= 0 and continue_pos > loop_start and checkbox_pos > continue_pos,
        "unsupported diagnostics are skipped before checkbox construction")
require("Not wired to a runtime probe in this build" not in main,
        "no dead/grey unsupported diagnostic checkbox UI remains")

ui_flags = set(re.findall(r"DiagFlag::([A-Za-z0-9_]+)", main))
missing_ui = sorted(implemented - ui_flags)
require(not missing_ui, f"every implemented diagnostic is reachable from ARM64 Diagnostics UI; missing={missing_ui}")

# The release diagnostic path must not depend on the old A/B experiment
# harness. Any RuntimeExperiments reference in generated src means the lean
# contract was violated.
legacy_refs = []
for rel, data in source_texts.items():
    if "RuntimeExperiments" in data:
        legacy_refs.append(rel)
# MainWindow was excluded above but scan it too for completeness.
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

print(f"[lean-diag-verify] PASS implemented={len(implemented)}")
for flag in sorted(implemented):
    print(f"[lean-diag-verify]   {flag}: {consumer_locations[flag][0]}")
