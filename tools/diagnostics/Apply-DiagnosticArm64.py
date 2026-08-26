from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


def ensure_include(text, anchors, include_line, label):
    if include_line in text:
        return text
    for anchor in anchors:
        if anchor in text:
            return text.replace(anchor, anchor + include_line, 1)
    raise RuntimeError(f"{label}: include anchor not found")


# -----------------------------------------------------------------------------
# AArch64 code-generation diagnostics: every ARM64/JIT UI item below has a
# concrete observation hook. Detailed logs are runtime-gated and rate-limited
# where they can execute frequently.
# -----------------------------------------------------------------------------
p = Path("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp")
t = p.read_text(encoding="utf-8")
t = ensure_include(
    t,
    ('#include "HW/Espresso/PPCState.h"\n', '#include "Common/precompiled.h"\n'),
    '#include "diagnostics/RuntimeDiagnostics.h"\n',
    "BackendAArch64 diagnostics include",
)

t = replace_once(
    t,
    '\tRuntimeDiagnostics::ScopedJitCompile diagJitCompile;\n',
    '''\tRuntimeDiagnostics::ScopedJitCompile diagJitCompile;
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::JitBlockLifecycle))
\t{
\t\tstatic std::atomic_uint64_t s_compileLogCount{0};
\t\tconst uint64_t n = s_compileLogCount.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 100 || (n % 1000) == 0)
\t\t\tcemuLog_log(LogType::Force, "[ARM64_JIT] COMPILE_BEGIN n={} guest=0x{:08x} guestSize={} segments={}", n, PPCRecFunction->ppcAddress, PPCRecFunction->ppcSize, ppcImlGenContext->segmentList2.size());
\t}
''',
    "JIT compile-begin hook",
)

# Keep branch patching and readyRE anchors independent. Apply-DiagnosticPerformance
# intentionally inserts counters immediately after readyRE(), so a combined
# multi-line anchor is brittle and caused Run #13 to fail before compilation.
branch_block = '''\tif (!aarch64GenContext.processAllJumps())
\t{
\t\tcemuLog_log(LogType::Recompiler, "PPCRecompiler_generateAArch64Code(): some jumps exceeded the +/-128MB offset.");
\t\treturn false;
\t}
'''
branch_replacement = '''\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::BranchPatching))
\t\tcemuLog_log(LogType::Force, "[ARM64_JIT] BRANCH_PATCH_BEGIN guest=0x{:08x} jumps={}", PPCRecFunction->ppcAddress, aarch64GenContext.jumps.size());
\tif (!aarch64GenContext.processAllJumps())
\t{
\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::BranchPatching))
\t\t\tcemuLog_log(LogType::Force, "[ARM64_JIT] BRANCH_PATCH_FAIL guest=0x{:08x} jumps={}", PPCRecFunction->ppcAddress, aarch64GenContext.jumps.size());
\t\tcemuLog_log(LogType::Recompiler, "PPCRecompiler_generateAArch64Code(): some jumps exceeded the +/-128MB offset.");
\t\treturn false;
\t}
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::BranchPatching))
\t\tcemuLog_log(LogType::Force, "[ARM64_JIT] BRANCH_PATCH_OK guest=0x{:08x} jumps={}", PPCRecFunction->ppcAddress, aarch64GenContext.jumps.size());
'''
t = replace_once(t, branch_block, branch_replacement, "branch patch diagnostics")

t = replace_once(
    t,
    '\taarch64GenContext.readyRE();\n',
    '''\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ReadyReICache))
\t\tcemuLog_log(LogType::Force, "[ARM64_JIT] READY_RE_BEGIN guest=0x{:08x} generatedBytes={}", PPCRecFunction->ppcAddress, aarch64GenContext.getSize());
\taarch64GenContext.readyRE();
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ReadyReICache))
\t\tcemuLog_log(LogType::Force, "[ARM64_JIT] READY_RE_END guest=0x{:08x} host={}", PPCRecFunction->ppcAddress, aarch64GenContext.getCode<void*>());
''',
    "readyRE diagnostics",
)

t = replace_once(
    t,
    '\tPPCRecFunction->x86Code = aarch64GenContext.getCode<void*>();\n\tPPCRecFunction->x86Size = aarch64GenContext.getMaxSize();\n',
    '''\tPPCRecFunction->x86Code = aarch64GenContext.getCode<void*>();
\tPPCRecFunction->x86Size = aarch64GenContext.getMaxSize();
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GuestHostMapping))
\t\tcemuLog_log(LogType::Force, "[ARM64_JIT] MAP guest=0x{:08x} guestSize={} host={} hostSize={}", PPCRecFunction->ppcAddress, PPCRecFunction->ppcSize, PPCRecFunction->x86Code, PPCRecFunction->x86Size);
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::JitBlockLifecycle))
\t\tcemuLog_log(LogType::Force, "[ARM64_JIT] COMPILE_END guest=0x{:08x} host={} hostSize={}", PPCRecFunction->ppcAddress, PPCRecFunction->x86Code, PPCRecFunction->x86Size);
''',
    "guest-host mapping hook",
)
p.write_text(t, encoding="utf-8", newline="\n")


# -----------------------------------------------------------------------------
# JIT execution entry. This is hot, so detailed lines use first-N/every-N
# sampling while the checkbox is enabled.
# -----------------------------------------------------------------------------
p = Path("src/Cafe/HW/Espresso/Recompiler/PPCRecompiler.cpp")
t = p.read_text(encoding="utf-8")
t = ensure_include(
    t,
    ('#include "Common/cpu_features.h"\n', '#include "Common/ExceptionHandler/ExceptionHandler.h"\n'),
    '#include "diagnostics/RuntimeDiagnostics.h"\n',
    "PPCRecompiler diagnostics include",
)
t = replace_once(
    t,
    'void PPCRecompiler_enter(PPCInterpreter_t* hCPU, PPCREC_JUMP_ENTRY funcPtr)\n{\n',
    '''void PPCRecompiler_enter(PPCInterpreter_t* hCPU, PPCREC_JUMP_ENTRY funcPtr)
{
#if defined(__aarch64__)
\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::JitExecutionEntry))
\t{
\t\tstatic std::atomic_uint64_t s_entryLogCount{0};
\t\tconst uint64_t n = s_entryLogCount.fetch_add(1, std::memory_order_relaxed) + 1;
\t\tif (n <= 100 || (n % 10000) == 0)
\t\t\tcemuLog_log(LogType::Force, "[ARM64_JIT] ENTER n={} guestPC=0x{:08x} host={}", n, hCPU->instructionPointer, (void*)funcPtr);
\t}
#endif
''',
    "JIT execution-entry hook",
)
p.write_text(t, encoding="utf-8", newline="\n")


# -----------------------------------------------------------------------------
# Windows ARM64 crash context + access-violation memory context.
# -----------------------------------------------------------------------------
p = Path("src/Common/ExceptionHandler/ExceptionHandler_win32.cpp")
t = p.read_text(encoding="utf-8")
t = ensure_include(
    t,
    ('#include "Cafe/HW/Espresso/Debugger/GDBStub.h"\n', '#include "Cafe/HW/Espresso/PPCState.h"\n'),
    '#include "diagnostics/RuntimeDiagnostics.h"\n',
    "ExceptionHandler diagnostics include",
)
t = replace_once(
    t,
    'void createCrashlog(EXCEPTION_POINTERS* e, PCONTEXT context)\n{\n    if(!CrashLog_Create())\n        return; // give up if crashlog was already created\n',
    '''void createCrashlog(EXCEPTION_POINTERS* e, PCONTEXT context)
{
    if(!CrashLog_Create())
        return; // give up if crashlog was already created
#if defined(__aarch64__)
\tif (e && e->ExceptionRecord && context && RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::Arm64ExceptionContext))
\t{
\t\tcemuLog_log(LogType::Force,
\t\t\t"[ARM64_EXCEPTION] code=0x{:08x} exceptionAddress={} PC={} LR={} SP={} FP={}",
\t\t\t(uint32)e->ExceptionRecord->ExceptionCode, e->ExceptionRecord->ExceptionAddress,
\t\t\t(void*)context->Pc, (void*)context->Lr, (void*)context->Sp, (void*)context->Fp);
\t}
\tif (e && e->ExceptionRecord && context && RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GuestMemoryAccess) &&
\t\te->ExceptionRecord->ExceptionCode == EXCEPTION_ACCESS_VIOLATION && e->ExceptionRecord->NumberParameters >= 2)
\t{
\t\tconst ULONG_PTR accessKind = e->ExceptionRecord->ExceptionInformation[0];
\t\tconst ULONG_PTR accessAddress = e->ExceptionRecord->ExceptionInformation[1];
\t\tconst char* kind = accessKind == 0 ? "read" : (accessKind == 1 ? "write" : (accessKind == 8 ? "execute" : "unknown"));
\t\tcemuLog_log(LogType::Force, "[ARM64_MEM] ACCESS_VIOLATION kind={} address={} PC={} LR={}", kind, (void*)accessAddress, (void*)context->Pc, (void*)context->Lr);
\t}
#endif
''',
    "ARM64 exception context hook",
)
p.write_text(t, encoding="utf-8", newline="\n")


# -----------------------------------------------------------------------------
# Session identity: makes it unambiguous in log.txt that the generic ARM64
# diagnostics build is active. If diagnostics are enabled after renderer init,
# UI toggle logging below still records activation.
# -----------------------------------------------------------------------------
p = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
t = p.read_text(encoding="utf-8")
t = replace_once(
    t,
    '\tcemuLog_log(LogType::Force, "Using GPU: {}", properties.properties.deviceName);\n',
    '''\tcemuLog_log(LogType::Force, "Using GPU: {}", properties.properties.deviceName);
\tif (RuntimeDiagnostics::AnyEnabled())
\t{
#if defined(__aarch64__)
\t\tconstexpr const char* diagArch = "ARM64";
#elif defined(ARCH_X86_64)
\t\tconstexpr const char* diagArch = "x86_64";
#else
\t\tconstexpr const char* diagArch = "unknown";
#endif
\t\tcemuLog_log(LogType::Force, "[CEMU_DIAG] Architecture={} GPU={} Diagnostics=active HitchThresholdMs={}", diagArch, properties.properties.deviceName, RuntimeDiagnostics::g_hitchThresholdMs.load(std::memory_order_relaxed));
\t}
''',
    "diagnostic session header",
)
p.write_text(t, encoding="utf-8", newline="\n")


# -----------------------------------------------------------------------------
# UI activation logging. This also proves whether a checkbox/preset was really
# active when the user sends log.txt.
# -----------------------------------------------------------------------------
p = Path("src/gui/wxgui/MainWindow.cpp")
t = p.read_text(encoding="utf-8")
t = replace_once(
    t,
    'explicit RuntimeDiagnosticsDialog(wxWindow* parent)\n        : wxDialog(parent, wxID_ANY, _("ARM64 Diagnostics"), wxDefaultPosition, wxSize(720, 760), wxDEFAULT_DIALOG_STYLE | wxRESIZE_BORDER)\n    {\n',
    '''explicit RuntimeDiagnosticsDialog(wxWindow* parent)
        : wxDialog(parent, wxID_ANY, _("ARM64 Diagnostics"), wxDefaultPosition, wxSize(720, 760), wxDEFAULT_DIALOG_STYLE | wxRESIZE_BORDER)
    {
#if defined(__aarch64__)
        cemuLog_log(LogType::Force, "[CEMU_DIAG] UI_OPEN Architecture=ARM64");
#else
        cemuLog_log(LogType::Force, "[CEMU_DIAG] UI_OPEN Architecture=non-ARM64");
#endif
''',
    "diagnostic UI-open identity log",
)
t = replace_once(
    t,
    'cb->Bind(wxEVT_CHECKBOX, [flag=item.flag](wxCommandEvent& e){ RuntimeDiagnostics::SetEnabled(flag, e.IsChecked()); });',
    'cb->Bind(wxEVT_CHECKBOX, [flag=item.flag,label=item.label](wxCommandEvent& e){ RuntimeDiagnostics::SetEnabled(flag, e.IsChecked()); cemuLog_log(LogType::Force, "[CEMU_DIAG] Toggle {}={}", label, e.IsChecked() ? "ON" : "OFF"); });',
    "diagnostic checkbox activation log",
)
t = replace_once(
    t,
    'm_master->Bind(wxEVT_CHECKBOX, [this](wxCommandEvent& e){ RuntimeDiagnostics::SetAll(e.IsChecked()); for (auto& entry : m_boxes) entry.first->SetValue(e.IsChecked()); });',
    'm_master->Bind(wxEVT_CHECKBOX, [this](wxCommandEvent& e){ RuntimeDiagnostics::SetAll(e.IsChecked()); for (auto& entry : m_boxes) entry.first->SetValue(e.IsChecked()); cemuLog_log(LogType::Force, "[CEMU_DIAG] Master={}", e.IsChecked() ? "ON" : "OFF"); });',
    "diagnostic master activation log",
)
t = replace_once(
    t,
    'for(auto& entry:m_boxes) entry.first->SetValue(RuntimeDiagnostics::Enabled(entry.second)); m_master->SetValue(RuntimeDiagnostics::AnyEnabled());\n        });',
    'for(auto& entry:m_boxes) entry.first->SetValue(RuntimeDiagnostics::Enabled(entry.second)); m_master->SetValue(RuntimeDiagnostics::AnyEnabled()); cemuLog_log(LogType::Force, "[CEMU_DIAG] Preset={}", preset->GetStringSelection().ToStdString());\n        });',
    "diagnostic preset activation log",
)
p.write_text(t, encoding="utf-8", newline="\n")

print("[diagnostics-arm64] concrete ARM64/JIT hooks installed")
