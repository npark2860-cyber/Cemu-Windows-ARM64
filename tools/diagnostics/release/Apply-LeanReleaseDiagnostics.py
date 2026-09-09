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
run("tools/diagnostics/release/Apply-LeanPipelineDiagnostics.py")
run("tools/diagnostics/Apply-ShaderFailureDiagnostics.py")
run("tools/diagnostics/release/Apply-ShaderFailureBundleEnhancements.py")
run("tools/diagnostics/release/Apply-LeanRTDiagnostics.py")

replace_once_file(
    "tools/diagnostics/Verify-DiagnosticCoverage.py",
    '''    # Render-target / synchronization
''',
    '''    # Shader / render-target / feedback
    "ShaderInterface": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::ShaderInterface"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[SHADER_INTERFACE]")],
    "FBOChanges": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::FBOChanges"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[FBO_CHANGE]")],
    "AttachmentUsage": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::AttachmentUsage"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[ATTACHMENT_USE]")],
    "LoadStoreBehavior": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::LoadStoreBehavior"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[LOAD_STORE]")],
    "RenderTargetAliasing": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::RenderTargetAliasing"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[RT_ALIAS]")],
    "FeedbackSupport": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::FeedbackSupport"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[FEEDBACK_SUPPORT]")],
    "FeedbackUse": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::FeedbackUse"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[FEEDBACK_USE]")],

    # Render-target / synchronization
''',
    "lean RT coverage verifier hooks",
)

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

run("tools/diagnostics/release/Apply-AdrenoIncidentCorrelation.py")
run("tools/diagnostics/release/Apply-AdrenoIncidentDetails.py")
run("tools/diagnostics/release/Apply-LeanDiagnosticUI.py")
run("tools/diagnostics/release/Apply-PersistentDiagnosticSettings.py")
run("tools/diagnostics/release/Apply-AdrenoFinalTriage.py")
run("tools/diagnostics/release/Apply-AdrenoFinalPolish.py")
run("tools/diagnostics/release/Apply-AdrenoSafeUI.py")

# The current Adreno driver baseline no longer uses the historical title-gated
# direct-query workaround. Reuse the mature verifier with only that obsolete
# preservation assertion normalized to the new standard query-path contract.
verifier = ROOT / "tools/diagnostics/release/Verify-AdrenoDiagnosticsComplete.py"
verifier_text = verifier.read_text(encoding="utf-8")
legacy_verify = '''require("UseDirectQueryReadbackWorkaround" in query,
        "protected direct-query workaround is preserved")
require("0x00050000101AFF00ULL" in query and "0x000500001011B900ULL" in query,
        "Star Fox Zero JP and Bayonetta 2 JP direct-readback title gates are preserved")
'''
normalized_verify = '''require("UseDirectQueryReadbackWorkaround" not in query,
        "legacy title-gated direct-query workaround is absent")
require("0x00050000101AFF00ULL" not in query and "0x000500001011B900ULL" not in query and "0x0005000010116100ULL" not in query,
        "Bayonetta 2 / Star Fox Zero / XCX title-specific query gates are absent")
'''
if verifier_text.count(legacy_verify) != 1:
    raise RuntimeError("Adreno verifier legacy query contract anchor changed")
verifier_text = verifier_text.replace(legacy_verify, normalized_verify, 1)
verifier_temp = ROOT / "tools/diagnostics/release/_Verify-AdrenoDiagnosticsComplete-DriverNormalized.generated.py"
try:
    verifier_temp.write_text(verifier_text, encoding="utf-8", newline="\n")
    print("[lean-release-diagnostics] verifying driver-normalized Adreno diagnostics")
    subprocess.run([sys.executable, str(verifier_temp)], cwd=ROOT, check=True)
finally:
    if verifier_temp.exists():
        verifier_temp.unlink()

# Keep the two narrow observation-only probes, but adapt the generic Vulkan
# query probe to the upstream mapped-result path. It may log query lifecycle and
# values, but it must not install or observe a title-specific direct-readback path.
targeted = ROOT / "tools/diagnostics/release/Apply-TargetedShaderQueryDiagnostics.py"
targeted_text = targeted.read_text(encoding="utf-8")
old_include = '''if '#include "diagnostics/RuntimeDiagnostics.h"\\n' not in v:
    v = replace_once(v, '#include "Cafe/CafeSystem.h"\\n', '#include "Cafe/CafeSystem.h"\\n#include "diagnostics/RuntimeDiagnostics.h"\\n', "Vulkan query diagnostic include")
'''
new_include = '''if '#include "Cafe/CafeSystem.h"\\n' not in v:
    v = replace_once(v, '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h"\\n', '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h"\\n#include "Cafe/CafeSystem.h"\\n', "Vulkan query title include")
if '#include "diagnostics/RuntimeDiagnostics.h"\\n' not in v:
    v = replace_once(v, '#include "Cafe/CafeSystem.h"\\n', '#include "Cafe/CafeSystem.h"\\n#include "diagnostics/RuntimeDiagnostics.h"\\n', "Vulkan query diagnostic include")
'''
if targeted_text.count(old_include) != 1:
    raise RuntimeError("Targeted diagnostics Vulkan include anchor changed")
targeted_text = targeted_text.replace(old_include, new_include, 1)

direct_start_marker = '''v = replace_once(
    v,
    "\\t\\t\\tif (result == VK_NOT_READY)'''
fragment_start_marker = '''v = replace_once(
    v,
    "\\t\\tm_acccumulatedSum += fragmentResult;'''
direct_start = targeted_text.find(direct_start_marker)
fragment_start = targeted_text.find(fragment_start_marker, direct_start)
if direct_start < 0 or fragment_start < 0:
    raise RuntimeError("Targeted diagnostics legacy direct-readback block anchors changed")
targeted_text = targeted_text[:direct_start] + targeted_text[fragment_start:]

fragment_start = targeted_text.find(fragment_start_marker)
final_start_marker = '''v = replace_once(
    v,
    "\\tnumSamplesPassed = m_acccumulatedSum;'''
final_start = targeted_text.find(final_start_marker, fragment_start)
if fragment_start < 0 or final_start < 0:
    raise RuntimeError("Targeted diagnostics fragment-result block anchors changed")
new_fragment_block = '''v = replace_once(
    v,
    "\\t\\tm_acccumulatedSum += m_rendererVk->m_occlusionQueries.ptrQueryResults[it.queryIndex];\\n\\t\\treleaseQueryIndex(it.queryIndex);",
    "\\t\\tconst uint64 diagFragmentResult = m_rendererVk->m_occlusionQueries.ptrQueryResults[it.queryIndex];\\n"
    "\\t\\tm_acccumulatedSum += diagFragmentResult;\\n"
    "\\t\\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GPUOcclusionQueryVisibility))\\n"
    "\\t\\t\\tcemuLog_log(LogType::Force, \\\"[QUERY_VIS] layer=VK event=FRAGMENT_RESULT title={:016x} index={} samples={} accumulated={}\\\", CafeSystem::GetForegroundTitleId(), it.queryIndex, diagFragmentResult, m_acccumulatedSum);\\n"
    "\\t\\treleaseQueryIndex(it.queryIndex);",
    "Vulkan fragment result diagnostic",
)
'''
targeted_text = targeted_text[:fragment_start] + new_fragment_block + targeted_text[final_start:]

old_check = '    vkq_path: ("[QUERY_VIS] layer=VK", "event=DIRECT_READBACK"),'
new_check = '    vkq_path: ("[QUERY_VIS] layer=VK", "event=FRAGMENT_RESULT"),'
if targeted_text.count(old_check) != 1:
    raise RuntimeError("Targeted diagnostics legacy direct-readback verification token changed")
targeted_text = targeted_text.replace(old_check, new_check, 1)

targeted_temp = ROOT / "tools/diagnostics/release/_Apply-TargetedShaderQueryDiagnostics-DriverNormalized.generated.py"
try:
    targeted_temp.write_text(targeted_text, encoding="utf-8", newline="\n")
    print("[lean-release-diagnostics] applying driver-normalized targeted diagnostics")
    subprocess.run([sys.executable, str(targeted_temp)], cwd=ROOT, check=True)
finally:
    if targeted_temp.exists():
        targeted_temp.unlink()

query_text = (ROOT / "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanQuery.cpp").read_text(encoding="utf-8")
for forbidden in (
    "UseDirectQueryReadbackWorkaround",
    "UseXCXDirectQueryReadbackExperiment",
    "XCX_QUERY_FORCE_VISIBLE",
    "0x00050000101AFF00",
    "0x000500001011B900",
    "0x0005000010116100",
    "vkGetQueryPoolResults(",
    "event=DIRECT_READBACK",
):
    if forbidden in query_text:
        raise RuntimeError(f"driver-normalized query source contains retired workaround token: {forbidden}")
if "[QUERY_VIS] layer=VK" not in query_text or "event=FRAGMENT_RESULT" not in query_text:
    raise RuntimeError("generic Vulkan query visibility diagnostics were not installed")

print("[lean-release-diagnostics] PASS")
