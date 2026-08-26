from pathlib import Path


def text(path):
    return Path(path).read_text(encoding="utf-8")


def require(path, needle, label):
    data = text(path)
    if needle not in data:
        raise RuntimeError(f"diagnostic coverage missing: {label} ({path}: {needle})")
    print(f"[diag-verify] OK {label}")


# Every ARM64/JIT checkbox must have a real non-UI hook.
require("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp", "Flag::JitBlockLifecycle", "JIT block lifecycle hook")
require("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp", "Flag::GuestHostMapping", "guest-host mapping hook")
require("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp", "Flag::BranchPatching", "branch patching hook")
require("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp", "Flag::ReadyReICache", "readyRE/I-cache hook")
require("src/Cafe/HW/Espresso/Recompiler/PPCRecompiler.cpp", "Flag::JitExecutionEntry", "JIT execution-entry hook")
require("src/Common/ExceptionHandler/ExceptionHandler_win32.cpp", "Flag::Arm64ExceptionContext", "ARM64 exception-context hook")
require("src/Common/ExceptionHandler/ExceptionHandler_win32.cpp", "Flag::GuestMemoryAccess", "guest memory access-fault hook")

# Log identity/activation must be visible in ordinary log.txt.
require("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "[CEMU_DIAG] Architecture=", "diagnostic session header")
require("src/gui/wxgui/MainWindow.cpp", "[CEMU_DIAG] Toggle", "individual checkbox activation log")
require("src/gui/wxgui/MainWindow.cpp", "[CEMU_DIAG] Master=", "master activation log")
require("src/gui/wxgui/MainWindow.cpp", "[CEMU_DIAG] Preset=", "preset activation log")

# The seven added performance diagnostics must have concrete hooks too.
require("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::GpuTimestamp", "GPU timestamp hook")
require("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::CpuWaitBreakdown", "CPU wait hook")
require("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::DescriptorStats", "descriptor statistics hook")
require("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::MemoryUploadStats", "memory/upload statistics hook")
require("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp", "Flag::JitPerformance", "JIT performance hook")
require("src/Cafe/HW/Latte/Core/LattePerformanceMonitor.cpp", "Flag::HitchTrigger", "frame hitch hook")
require("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::SummaryOnExit", "summary-on-exit hook")
require("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp", "RuntimeDiagnostics::NoteEvent", "diagnostic overhead event hook")

# Verify all seven ARM64/JIT controls are present in the UI as well.
ui = text("src/gui/wxgui/MainWindow.cpp")
for flag in (
    "JitBlockLifecycle", "GuestHostMapping", "BranchPatching", "ReadyReICache",
    "JitExecutionEntry", "Arm64ExceptionContext", "GuestMemoryAccess",
):
    if f"DiagFlag::{flag}" not in ui:
        raise RuntimeError(f"diagnostic UI missing ARM64 flag: {flag}")
    print(f"[diag-verify] OK UI {flag}")

print("[diag-verify] PASS: ARM64/JIT and added performance diagnostics are UI-controlled and concretely hooked")
