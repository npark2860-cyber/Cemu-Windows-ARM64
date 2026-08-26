from pathlib import Path
import re


def text(path):
    return Path(path).read_text(encoding="utf-8")


def require(path, needle, label):
    data = text(path)
    if needle not in data:
        raise RuntimeError(f"diagnostic coverage missing: {label} ({path}: {needle})")
    print(f"[diag-verify] OK {label}")


# Every flag declared selectable by RuntimeDiagnostics::IsImplemented must have
# an explicit non-UI runtime consumer. This table is intentionally exhaustive:
# adding a selectable checkbox without extending this verifier fails the build.
HOOKS = {
    # ARM64 / JIT
    "JitBlockLifecycle": [("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp", "Flag::JitBlockLifecycle")],
    "GuestHostMapping": [("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp", "Flag::GuestHostMapping")],
    "BranchPatching": [("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp", "Flag::BranchPatching")],
    "ReadyReICache": [("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp", "Flag::ReadyReICache")],
    "JitExecutionEntry": [("src/Cafe/HW/Espresso/Recompiler/PPCRecompiler.cpp", "Flag::JitExecutionEntry")],
    "Arm64ExceptionContext": [("src/Common/ExceptionHandler/ExceptionHandler_win32.cpp", "Flag::Arm64ExceptionContext")],
    "GuestMemoryAccess": [("src/Common/ExceptionHandler/ExceptionHandler_win32.cpp", "Flag::GuestMemoryAccess")],
    "JitPerformance": [("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp", "Flag::JitPerformance")],

    # Vulkan / pipeline
    "QueueSubmit": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::QueueSubmit")],
    "PipelineCache": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::PipelineCache"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[PIPE_CACHE]")],
    "PipelineCreation": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp", "Flag::PipelineCreation"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp", "[PIPE_CREATE]")],
    "PipelineFailure": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp", "Flag::PipelineFailure"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp", "PIPELINE_FAIL")],
    "PipelineStateSnapshot": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp", "Flag::PipelineStateSnapshot"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp", "PIPELINE_STATE")],
    "ShaderHashAssociation": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp", "Flag::ShaderHashAssociation"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp", "SHADER_HASH")],
    "ShaderVS": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp", "Flag::ShaderVS"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp", "[SHADER_VS]")],
    "ShaderPS": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp", "Flag::ShaderPS"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp", "[SHADER_PS]")],
    "ShaderGS": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp", "Flag::ShaderGS"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp", "[SHADER_GS]")],
    "ShaderAuxHash": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::ShaderAuxHash"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[PIPE_VS_AUX]")],

    # Render-target / synchronization
    "RenderPassBeginEnd": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::RenderPassBeginEnd"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[RT_PASS]")],
    "PipelineBarriers": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::PipelineBarriers"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[RT_BARRIER]")],
    "RAWDependency": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::RAWDependency"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[RT_RAW]")],
    "WAWDependency": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::WAWDependency"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[RT_WAW]")],
    "SelfDependency": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::SelfDependency"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[RT_SELF_DEP]")],
    "RenderPassSplit": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::RenderPassSplit"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[RT_PASS_SPLIT]")],
    "SynchronizationSummary": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::SynchronizationSummary"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[RT_STATS]")],

    # Performance
    "FrameTiming": [("src/diagnostics/RuntimeDiagnostics.h", "Enabled(Flag::FrameTiming)"), ("src/Cafe/HW/Latte/Core/LattePerformanceMonitor.cpp", "RuntimeDiagnostics::BeginFrame")],
    "DrawCallCount": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::DrawCallCount")],
    "PipelineCompileTime": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp", "Flag::PipelineCompileTime")],
    "QueueSubmitCount": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::QueueSubmitCount")],
    "PresentTiming": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::PresentTiming")],
    "GpuTimestamp": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::GpuTimestamp")],
    "CpuWaitBreakdown": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::CpuWaitBreakdown")],
    "DescriptorStats": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::DescriptorStats")],
    "MemoryUploadStats": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::MemoryUploadStats")],
    "HitchTrigger": [("src/Cafe/HW/Latte/Core/LattePerformanceMonitor.cpp", "Flag::HitchTrigger")],
    "DiagnosticOverhead": [("src/diagnostics/RuntimeDiagnostics.h", "Enabled(Flag::DiagnosticOverhead)"), ("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp", "RuntimeDiagnostics::NoteEvent")],
    "SummaryOnExit": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::SummaryOnExit")],
}

header = text("src/diagnostics/RuntimeDiagnostics.h")
match = re.search(r"inline bool IsImplemented\(Flag flag\).*?\{(.*?)\n\}\n\ninline bool Enabled", header, re.S)
if not match:
    raise RuntimeError("diagnostic coverage missing: IsImplemented body")
implemented_cases = set(re.findall(r"case Flag::([A-Za-z0-9_]+):", match.group(1)))
expected_cases = set(HOOKS)
if implemented_cases != expected_cases:
    missing_verifier = sorted(implemented_cases - expected_cases)
    missing_implementation = sorted(expected_cases - implemented_cases)
    raise RuntimeError(f"IsImplemented/verifier mismatch: no-verifier={missing_verifier} not-selectable={missing_implementation}")
print(f"[diag-verify] OK IsImplemented coverage count={len(implemented_cases)}")

for flag, checks in HOOKS.items():
    for path, needle in checks:
        require(path, needle, f"{flag} runtime hook")

# UI must visibly distinguish implemented and not-yet-wired controls.
require("src/gui/wxgui/MainWindow.cpp", "RuntimeDiagnostics::IsImplemented(item.flag)", "UI implementation gate")
require("src/gui/wxgui/MainWindow.cpp", "Not wired to a runtime probe in this build", "UI unsupported tooltip")
require("src/gui/wxgui/MainWindow.cpp", "[CEMU_DIAG] Toggle", "individual checkbox activation log")
require("src/gui/wxgui/MainWindow.cpp", "[CEMU_DIAG] Master=", "master activation log")
require("src/gui/wxgui/MainWindow.cpp", "[CEMU_DIAG] Preset=", "preset activation log")

# The old bridge must not make unrelated UI flags activate one coarse legacy
# experiment. Environment-variable experiments continue to work independently.
require("src/diagnostics/RuntimeDiagnostics.h", "inline bool LegacyBridgeEnabled(std::string_view)", "legacy bridge neutralized")
legacy_match = re.search(r"inline bool LegacyBridgeEnabled\(std::string_view\)\s*\{(.*?)\}", header, re.S)
if not legacy_match or "return false;" not in legacy_match.group(1):
    raise RuntimeError("legacy diagnostic bridge is still fanning UI flags into coarse switches")
print("[diag-verify] OK no coarse UI-to-legacy fanout")

# Session identity must be visible in ordinary log.txt.
require("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "[CEMU_DIAG] Architecture=", "diagnostic session header")

print("[diag-verify] PASS: every selectable diagnostic checkbox has a concrete runtime probe")
