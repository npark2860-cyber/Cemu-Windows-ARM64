from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]


def run(script):
    path = ROOT / script
    print(f"[lean-release-diagnostics] applying {script}")
    subprocess.run([sys.executable, str(path)], cwd=ROOT, check=True)


def replace_once_file(rel, old, new, label):
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


# Order is intentional. Several patches share exact source anchors.
# 1) Pipeline establishes compile/shader/cache probes.
# 2) Shader-failure diagnostics must extend IsImplemented before RT inserts a
#    new section after ShaderAuxHash.
# 3) RT diagnostics must patch the original draw-counter tail before the
#    performance layer adds its per-draw gated counter.
# 4) Performance establishes ScopedJitCompile/readyRE counters required by the
#    ARM64 lifecycle layer.
# 5) Vulkan establishes the queue/fence/timestamp shape used by submit/lifetime.
# 6) Frame, ARM64 and submit probes then layer on observation-only hooks.
run("tools/diagnostics/release/Apply-LeanPipelineDiagnostics.py")
run("tools/diagnostics/Apply-ShaderFailureDiagnostics.py")
run("tools/diagnostics/release/Apply-LeanRTDiagnostics.py")

# CompleteDiagnostics was originally authored against the historical RT probe
# label "forcedSplit". Keep the lean observation semantics but normalize this
# label so its exact source anchor remains reusable.
replace_once_file(
    "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp",
    '"[RT_PASS_SPLIT] draws={} count={}"',
    '"[RT_PASS_SPLIT] draws={} forcedSplit={}"',
    "lean RT pass-split completion anchor",
)

run("tools/diagnostics/release/Apply-LeanPerformanceDiagnostics.py")
run("tools/diagnostics/release/Apply-LeanVulkanDiagnostics.py")
run("tools/diagnostics/release/Apply-LeanFrameDiagnostics.py")
run("tools/diagnostics/release/Apply-LeanArm64Diagnostics.py")
run("tools/diagnostics/release/Apply-LeanSubmitLifetime.py")

# Apply-CompleteDiagnostics contains one legacy rt-stats fallback only in its
# patch anchors. For the release path, replace both anchor occurrences with a
# literal false before executing it. This preserves all observation probes but
# prevents any RuntimeExperiments dependency or behavior-changing A/B switch.
complete = ROOT / "tools/diagnostics/Apply-CompleteDiagnostics.py"
complete_text = complete.read_text(encoding="utf-8")
legacy = 'RuntimeExperiments::Enabled("rt-stats")'
legacy_count = complete_text.count(legacy)
if legacy_count != 2:
    raise RuntimeError(f"CompleteDiagnostics legacy rt-stats anchor count changed: expected 2, found {legacy_count}")
lean_complete_text = complete_text.replace(legacy, "false")
if "RuntimeExperiments::" in lean_complete_text:
    raise RuntimeError("Lean CompleteDiagnostics still contains RuntimeExperiments dependency")

temp = ROOT / "tools/diagnostics/release/_Apply-CompleteDiagnostics-Lean.generated.py"
try:
    temp.write_text(lean_complete_text, encoding="utf-8", newline="\n")
    print("[lean-release-diagnostics] applying transformed CompleteDiagnostics (legacy experiments disabled)")
    subprocess.run([sys.executable, str(temp)], cwd=ROOT, check=True)
finally:
    if temp.exists():
        temp.unlink()

# Adreno incident correlation adds no new checkbox. It reuses the existing
# failure switches to keep a 64-draw in-memory context ring only while a
# relevant failure diagnostic is enabled, then emits one compact incident
# bundle with driver/features/pipeline/shader/descriptors/FBO context.
run("tools/diagnostics/release/Apply-AdrenoIncidentCorrelation.py")

# UI is applied last so RuntimeDiagnostics::IsImplemented already represents
# the final concrete probe set. Unsupported candidate flags are skipped before
# any wxCheckBox is constructed.
run("tools/diagnostics/release/Apply-LeanDiagnosticUI.py")

# Static contract: every selectable flag has a non-UI runtime consumer, no
# legacy A/B experiment dependency leaks into the generated release sources,
# and direct-query loader declarations remain unique.
run("tools/diagnostics/release/Verify-LeanDiagnostics.py")

print("[lean-release-diagnostics] PASS")
