from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


path = Path("src/gui/wxgui/MainWindow.cpp")
text = path.read_text(encoding="utf-8")

# There must be no one-click path that enables every heavy probe. Replace the
# historical master checkbox with a one-way Disable all button.
text = replace_once(
    text,
    '''        m_master = new wxCheckBox(this, wxID_ANY, _("Diagnostics master"));
        m_master->SetValue(RuntimeDiagnostics::AnyEnabled());
        top->Add(m_master, 0, wxALL | wxALIGN_CENTER_VERTICAL, 5);
''',
    '''        auto* disableAll = new wxButton(this, wxID_ANY, _("Disable all"));
        disableAll->Bind(wxEVT_BUTTON, [this](wxCommandEvent&){
            RuntimeDiagnostics::SetAll(false);
            RuntimeDiagnostics::ClearIncidentContext();
            RefreshChecks();
            cemuLog_log(LogType::Force, "[CEMU_DIAG] All diagnostics OFF");
        });
        top->Add(disableAll, 0, wxALL | wxALIGN_CENTER_VERTICAL, 5);
''',
    "safe disable-all control",
)

text = replace_once(
    text,
    '''        preset->Append(_("Full"));
''',
    '''        preset->Append(_("Adreno Triage"));
''',
    "safe Adreno preset name",
)

master_bind = '''        m_master->Bind(wxEVT_CHECKBOX, [this](wxCommandEvent& e){
            RuntimeDiagnostics::SetAll(e.IsChecked());
            RefreshChecks();
            cemuLog_log(LogType::Force, "[CEMU_DIAG] Master={}", RuntimeDiagnostics::AnyEnabled() ? "ON" : "OFF");
        });

'''
text = replace_once(text, master_bind, "", "remove unsafe master binding")

# Every preset starts from a clean OFF state and clears stale correlation rings.
text = replace_once(
    text,
    '''            RuntimeDiagnostics::SetAll(false);
            if (p == 1)
''',
    '''            RuntimeDiagnostics::SetAll(false);
            RuntimeDiagnostics::ClearIncidentContext();
            if (p == 1)
''',
    "preset incident reset",
)

# The former Full preset enabled all 77 probes including DumpEveryShader. Turn
# that slot into a compact failure-driven Adreno triage preset. Resource and
# layout breadcrumbs piggyback on these failure switches automatically.
text = replace_once(
    text,
    '''            else if (p == 7)
            {
                RuntimeDiagnostics::SetAll(true);
            }
''',
    '''            else if (p == 7)
            {
                for (auto f : {DiagFlag::PipelineFailure,DiagFlag::PipelineCacheMismatch,DiagFlag::GLSLCompileFailure,DiagFlag::SPIRVCompileFailure,DiagFlag::DumpFailedShader,DiagFlag::DeviceLostSubmitError})
                    RuntimeDiagnostics::SetEnabled(f, true);
            }
''',
    "Adreno triage preset",
)

text = replace_once(
    text,
    '''        m_master->SetValue(RuntimeDiagnostics::AnyEnabled());
''',
    "",
    "remove master status refresh",
)
text = replace_once(
    text,
    '''    wxCheckBox* m_master{};
''',
    "",
    "remove master member",
)

if "RuntimeDiagnostics::SetAll(true)" in text:
    raise RuntimeError("unsafe SetAll(true) remains in ARM64 Diagnostics UI")
if "DumpEveryShader" not in text:
    raise RuntimeError("manual DumpEveryShader checkbox unexpectedly disappeared")
if 'DiagFlag::DumpEveryShader' in text[text.find('else if (p == 7)'):text.find('RefreshChecks();', text.find('else if (p == 7)'))]:
    raise RuntimeError("Adreno Triage must never enable DumpEveryShader")

path.write_text(text, encoding="utf-8", newline="\n")
print("[adreno-safe-ui] no bulk-enable master; Adreno Triage is failure-driven and DumpEveryShader remains manual only")
