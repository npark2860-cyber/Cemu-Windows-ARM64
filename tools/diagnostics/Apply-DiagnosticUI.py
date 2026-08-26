from pathlib import Path

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)

rp = Path("src/diagnostics/RuntimeExperiments.h")
text = rp.read_text(encoding="utf-8")
text = replace_once(text, '#include <string_view>\n', '#include <string_view>\n#include "diagnostics/RuntimeDiagnostics.h"\n', "RuntimeExperiments include")
text = replace_once(text, 'inline bool Enabled(std::string_view name)\n{\n    const std::string& raw = Raw();', 'inline bool Enabled(std::string_view name)\n{\n    if (RuntimeDiagnostics::LegacyBridgeEnabled(name))\n        return true;\n    const std::string& raw = Raw();', "legacy diagnostic bridge")
rp.write_text(text, encoding="utf-8", newline="\n")

path = Path("src/gui/wxgui/MainWindow.cpp")
text = path.read_text(encoding="utf-8")
text = replace_once(text, '#include "Cafe/HW/Latte/Renderer/Renderer.h" // For renderer API checks\n', '#include "Cafe/HW/Latte/Renderer/Renderer.h" // For renderer API checks\n#include "diagnostics/RuntimeDiagnostics.h"\n#include <wx/spinctrl.h>\n#include <wx/scrolwin.h>\n', "MainWindow diagnostic include")
text = replace_once(text, '\tMAINFRAME_MENU_ID_DEBUG_GPU_CAPTURE,\n', '\tMAINFRAME_MENU_ID_DEBUG_GPU_CAPTURE,\n\tMAINFRAME_MENU_ID_DEBUG_ARM64_DIAGNOSTICS,\n', "diagnostic menu id")

dialog_code = r'''
namespace
{
using DiagFlag = RuntimeDiagnostics::Flag;
struct DiagItem { const char* label; DiagFlag flag; };
static constexpr DiagItem kDiagItems[] = {
    {"JIT block lifecycle",DiagFlag::JitBlockLifecycle},{"Guest/host JIT mapping",DiagFlag::GuestHostMapping},{"Branch patching",DiagFlag::BranchPatching},{"readyRE / I-cache",DiagFlag::ReadyReICache},{"JIT execution entry",DiagFlag::JitExecutionEntry},{"ARM64 exception context",DiagFlag::Arm64ExceptionContext},{"Guest memory access",DiagFlag::GuestMemoryAccess},
    {"Command-buffer lifecycle",DiagFlag::CommandBufferLifecycle},{"Queue submit",DiagFlag::QueueSubmit},{"Fence lifecycle",DiagFlag::FenceLifecycle},{"Semaphore flow",DiagFlag::SemaphoreFlow},{"Submit completion",DiagFlag::SubmitCompletion},{"Device-lost / submit errors",DiagFlag::DeviceLostSubmitError},
    {"Pipeline cache",DiagFlag::PipelineCache},{"Pipeline creation",DiagFlag::PipelineCreation},{"Pipeline failure",DiagFlag::PipelineFailure},{"Pipeline state snapshot",DiagFlag::PipelineStateSnapshot},{"Shader hash association",DiagFlag::ShaderHashAssociation},{"Pipeline-cache mismatch",DiagFlag::PipelineCacheMismatch},
    {"Shader creation",DiagFlag::ShaderCreation},{"VS diagnostics",DiagFlag::ShaderVS},{"PS diagnostics",DiagFlag::ShaderPS},{"GS diagnostics",DiagFlag::ShaderGS},{"Shader auxHash",DiagFlag::ShaderAuxHash},{"Shader interface",DiagFlag::ShaderInterface},{"GLSL compile failure",DiagFlag::GLSLCompileFailure},{"SPIR-V compile failure",DiagFlag::SPIRVCompileFailure},{"Dump failed shader",DiagFlag::DumpFailedShader},{"Dump every shader",DiagFlag::DumpEveryShader},
    {"Render-pass begin/end",DiagFlag::RenderPassBeginEnd},{"FBO changes",DiagFlag::FBOChanges},{"Attachment usage",DiagFlag::AttachmentUsage},{"Load/store behavior",DiagFlag::LoadStoreBehavior},{"Render-target aliasing",DiagFlag::RenderTargetAliasing},
    {"Pipeline barriers",DiagFlag::PipelineBarriers},{"RAW dependency",DiagFlag::RAWDependency},{"WAW dependency",DiagFlag::WAWDependency},{"Self dependency",DiagFlag::SelfDependency},{"Render-pass split",DiagFlag::RenderPassSplit},{"Synchronization summary",DiagFlag::SynchronizationSummary},
    {"Feedback-loop support",DiagFlag::FeedbackSupport},{"Feedback-loop use",DiagFlag::FeedbackUse},{"Feedback fallback",DiagFlag::FeedbackFallback},{"Feedback self-dependency",DiagFlag::FeedbackSelfDependency},{"Image layout transition",DiagFlag::ImageLayoutTransition},{"Feedback pass split",DiagFlag::FeedbackPassSplit},
    {"Texture lifecycle",DiagFlag::TextureLifecycle},{"Texture-view lifecycle",DiagFlag::TextureViewLifecycle},{"Texture cache",DiagFlag::TextureCache},{"Texture aliasing",DiagFlag::TextureAliasing},{"Surface invalidation",DiagFlag::SurfaceInvalidation},{"Suspicious texture state",DiagFlag::SuspiciousTextureState},
    {"VPAD",DiagFlag::VPAD},{"KPAD",DiagFlag::KPAD},{"Controller slot",DiagFlag::ControllerSlot},{"Player index",DiagFlag::PlayerIndex},{"Channel mapping",DiagFlag::ChannelMapping},{"Connect/disconnect",DiagFlag::ConnectDisconnect},{"Input read summary",DiagFlag::InputReadSummary},
    {"Frame timing",DiagFlag::FrameTiming},{"LatteThread timing",DiagFlag::LatteThreadTiming},{"Draw-call count",DiagFlag::DrawCallCount},{"Pipeline compile time",DiagFlag::PipelineCompileTime},{"Pipeline-cache performance",DiagFlag::PerfPipelineCache},{"Barrier count",DiagFlag::BarrierCount},{"Render-pass count",DiagFlag::RenderPassCount},{"Queue-submit count",DiagFlag::QueueSubmitCount},{"Upload/stall timing",DiagFlag::UploadStallTiming},{"Present timing",DiagFlag::PresentTiming},
    {"GPU timestamp",DiagFlag::GpuTimestamp},{"CPU wait breakdown",DiagFlag::CpuWaitBreakdown},{"Descriptor statistics",DiagFlag::DescriptorStats},{"Memory/upload statistics",DiagFlag::MemoryUploadStats},{"JIT performance",DiagFlag::JitPerformance},{"Frame hitch trigger",DiagFlag::HitchTrigger},{"Diagnostic overhead",DiagFlag::DiagnosticOverhead},{"Summary on exit",DiagFlag::SummaryOnExit}
};

class RuntimeDiagnosticsDialog final : public wxDialog
{
public:
    explicit RuntimeDiagnosticsDialog(wxWindow* parent)
        : wxDialog(parent, wxID_ANY, _("ARM64 Diagnostics"), wxDefaultPosition, wxSize(720, 760), wxDEFAULT_DIALOG_STYLE | wxRESIZE_BORDER)
    {
        auto* root = new wxBoxSizer(wxVERTICAL);
        auto* top = new wxBoxSizer(wxHORIZONTAL);
        m_master = new wxCheckBox(this, wxID_ANY, _("Diagnostics master"));
        m_master->SetValue(RuntimeDiagnostics::AnyEnabled());
        top->Add(m_master, 0, wxALL | wxALIGN_CENTER_VERTICAL, 5);
        auto* preset = new wxChoice(this, wxID_ANY);
        preset->Append(_("Custom")); preset->Append(_("Minimal")); preset->Append(_("Performance")); preset->Append(_("Vulkan")); preset->Append(_("JIT")); preset->Append(_("Graphics")); preset->Append(_("Input")); preset->Append(_("Full"));
        preset->SetSelection(0);
        top->Add(new wxStaticText(this, wxID_ANY, _("Preset")), 0, wxLEFT | wxRIGHT | wxALIGN_CENTER_VERTICAL, 8);
        top->Add(preset, 1, wxALL | wxEXPAND, 5);
        root->Add(top, 0, wxEXPAND);

        auto* scroll = new wxScrolledWindow(this, wxID_ANY, wxDefaultPosition, wxDefaultSize, wxVSCROLL | wxBORDER_SIMPLE);
        scroll->SetScrollRate(0, 12);
        auto* grid = new wxFlexGridSizer(2, 4, 12);
        for (const auto& item : kDiagItems)
        {
            auto* cb = new wxCheckBox(scroll, wxID_ANY, wxString::FromUTF8(item.label));
            cb->SetValue(RuntimeDiagnostics::Enabled(item.flag));
            if (!RuntimeDiagnostics::IsImplemented(item.flag))
            {
                cb->Enable(false);
                cb->SetToolTip(_("Not wired to a runtime probe in this build"));
            }
            cb->Bind(wxEVT_CHECKBOX, [cb,flag=item.flag](wxCommandEvent& e){
                RuntimeDiagnostics::SetEnabled(flag, e.IsChecked());
                cb->SetValue(RuntimeDiagnostics::Enabled(flag));
            });
            m_boxes.push_back({cb,item.flag});
            grid->Add(cb, 0, wxALL, 2);
        }
        scroll->SetSizer(grid);
        root->Add(scroll, 1, wxALL | wxEXPAND, 5);

        auto* hitch = new wxBoxSizer(wxHORIZONTAL);
        hitch->Add(new wxStaticText(this, wxID_ANY, _("Hitch threshold (ms)")), 0, wxALL | wxALIGN_CENTER_VERTICAL, 5);
        auto* threshold = new wxSpinCtrl(this, wxID_ANY);
        threshold->SetRange(1, 5000);
        threshold->SetValue((int)RuntimeDiagnostics::g_hitchThresholdMs.load(std::memory_order_relaxed));
        threshold->Bind(wxEVT_SPINCTRL, [threshold](wxCommandEvent&){ RuntimeDiagnostics::g_hitchThresholdMs.store((uint32_t)threshold->GetValue(), std::memory_order_relaxed); });
        hitch->Add(threshold, 0, wxALL, 5);
        auto* reset = new wxButton(this, wxID_ANY, _("Reset counters"));
        reset->Bind(wxEVT_BUTTON, [](wxCommandEvent&){ RuntimeDiagnostics::ResetCounters(); });
        hitch->AddStretchSpacer(); hitch->Add(reset, 0, wxALL, 5); root->Add(hitch, 0, wxEXPAND);

        m_master->Bind(wxEVT_CHECKBOX, [this](wxCommandEvent& e){ RuntimeDiagnostics::SetAll(e.IsChecked()); for (auto& entry : m_boxes) entry.first->SetValue(RuntimeDiagnostics::Enabled(entry.second)); });
        preset->Bind(wxEVT_CHOICE, [this,preset](wxCommandEvent&){
            const int p=preset->GetSelection(); RuntimeDiagnostics::SetAll(false);
            if(p==1){ RuntimeDiagnostics::SetEnabled(DiagFlag::FrameTiming,true); RuntimeDiagnostics::SetEnabled(DiagFlag::QueueSubmit,true); RuntimeDiagnostics::SetEnabled(DiagFlag::CpuWaitBreakdown,true); RuntimeDiagnostics::SetEnabled(DiagFlag::HitchTrigger,true); }
            else if(p==2){ for(auto f:{DiagFlag::FrameTiming,DiagFlag::LatteThreadTiming,DiagFlag::DrawCallCount,DiagFlag::PipelineCompileTime,DiagFlag::PerfPipelineCache,DiagFlag::BarrierCount,DiagFlag::RenderPassCount,DiagFlag::QueueSubmitCount,DiagFlag::UploadStallTiming,DiagFlag::PresentTiming,DiagFlag::GpuTimestamp,DiagFlag::CpuWaitBreakdown,DiagFlag::DescriptorStats,DiagFlag::MemoryUploadStats,DiagFlag::JitPerformance,DiagFlag::HitchTrigger,DiagFlag::DiagnosticOverhead}) RuntimeDiagnostics::SetEnabled(f,true); }
            else if(p==3){ for(auto f:{DiagFlag::CommandBufferLifecycle,DiagFlag::QueueSubmit,DiagFlag::FenceLifecycle,DiagFlag::SemaphoreFlow,DiagFlag::SubmitCompletion,DiagFlag::DeviceLostSubmitError,DiagFlag::PipelineCache,DiagFlag::PipelineCreation,DiagFlag::PipelineFailure,DiagFlag::PipelineStateSnapshot,DiagFlag::RenderPassBeginEnd,DiagFlag::PipelineBarriers,DiagFlag::SynchronizationSummary,DiagFlag::GpuTimestamp,DiagFlag::CpuWaitBreakdown,DiagFlag::DescriptorStats}) RuntimeDiagnostics::SetEnabled(f,true); }
            else if(p==4){ for(auto f:{DiagFlag::JitBlockLifecycle,DiagFlag::GuestHostMapping,DiagFlag::BranchPatching,DiagFlag::ReadyReICache,DiagFlag::JitExecutionEntry,DiagFlag::Arm64ExceptionContext,DiagFlag::GuestMemoryAccess,DiagFlag::JitPerformance}) RuntimeDiagnostics::SetEnabled(f,true); }
            else if(p==5){ for(auto f:{DiagFlag::PipelineCache,DiagFlag::PipelineCreation,DiagFlag::PipelineFailure,DiagFlag::ShaderCreation,DiagFlag::ShaderVS,DiagFlag::ShaderPS,DiagFlag::ShaderGS,DiagFlag::ShaderAuxHash,DiagFlag::RenderPassBeginEnd,DiagFlag::FBOChanges,DiagFlag::AttachmentUsage,DiagFlag::PipelineBarriers,DiagFlag::FeedbackUse,DiagFlag::ImageLayoutTransition,DiagFlag::TextureCache}) RuntimeDiagnostics::SetEnabled(f,true); }
            else if(p==6){ for(auto f:{DiagFlag::VPAD,DiagFlag::KPAD,DiagFlag::ControllerSlot,DiagFlag::PlayerIndex,DiagFlag::ChannelMapping,DiagFlag::ConnectDisconnect,DiagFlag::InputReadSummary}) RuntimeDiagnostics::SetEnabled(f,true); }
            else if(p==7){ RuntimeDiagnostics::SetAll(true); }
            for(auto& entry:m_boxes) entry.first->SetValue(RuntimeDiagnostics::Enabled(entry.second)); m_master->SetValue(RuntimeDiagnostics::AnyEnabled());
        });
        root->Add(new wxButton(this, wxID_OK, _("Close")), 0, wxALL | wxALIGN_RIGHT, 6);
        SetSizer(root); CentreOnParent();
    }
private:
    wxCheckBox* m_master{};
    std::vector<std::pair<wxCheckBox*,DiagFlag>> m_boxes;
};
}
'''
text = replace_once(text, 'class wxGameDropTarget : public wxFileDropTarget\n', dialog_code + '\nclass wxGameDropTarget : public wxFileDropTarget\n', "diagnostic dialog insertion")
text = replace_once(text, '\tdebugMenu->AppendSeparator();\n\n#ifdef CEMU_DEBUG_ASSERT\n', '\tdebugMenu->AppendSeparator();\n\tauto* arm64Diagnostics = debugMenu->Append(MAINFRAME_MENU_ID_DEBUG_ARM64_DIAGNOSTICS, _("ARM64 Diagnostics..."));\n\tBind(wxEVT_MENU, [this](wxCommandEvent&){ RuntimeDiagnosticsDialog dlg(this); dlg.ShowModal(); }, arm64Diagnostics->GetId());\n\tdebugMenu->AppendSeparator();\n\n#ifdef CEMU_DEBUG_ASSERT\n', "debug menu item")
path.write_text(text, encoding="utf-8", newline="\n")
print("[diagnostics-ui] runtime UI installed")
