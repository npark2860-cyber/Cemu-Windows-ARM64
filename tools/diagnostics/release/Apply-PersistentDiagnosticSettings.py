from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# Test/diagnostic builds should remember the exact checkbox state across Cemu
# restarts. Persist only the diagnostics UI state; do not change any renderer
# behavior unless the corresponding flag is enabled at runtime.

# ---------------------------------------------------------------------------
# wxCemuConfig: store one bit per RuntimeDiagnostics::Flag plus hitch threshold.
# A string is used instead of a fixed-width integer because the diagnostic flag
# count is already larger than 64 and may continue to grow.
# ---------------------------------------------------------------------------
hdr_path = Path("src/gui/wxgui/wxCemuConfig.h")
hdr = hdr_path.read_text(encoding="utf-8")
hdr = replace_once(
    hdr,
    '''\tConfigValue<bool> show_icon_column{true};

\tint game_list_style = 0;
''',
    '''\tConfigValue<bool> show_icon_column{true};

\t// ARM64 diagnostic-edition UI persistence. Empty means all diagnostics OFF.
\tstd::string arm64_diagnostics_flags;
\tsint32 arm64_diagnostics_hitch_threshold{50};

\tint game_list_style = 0;
''',
    "wx config diagnostics fields",
)
hdr_path.write_text(hdr, encoding="utf-8", newline="\n")

cpp_path = Path("src/gui/wxgui/wxCemuConfig.cpp")
cpp = cpp_path.read_text(encoding="utf-8")
cpp = replace_once(
    cpp,
    '''\tshow_icon_column = parser.get("show_icon_column", true);

\t// return default width if value in config file out of range
''',
    '''\tshow_icon_column = parser.get("show_icon_column", true);
\tarm64_diagnostics_flags = parser.get("arm64_diagnostics_flags", "");
\tarm64_diagnostics_hitch_threshold = parser.get("arm64_diagnostics_hitch_threshold", 50);

\t// return default width if value in config file out of range
''',
    "wx config diagnostics load",
)
cpp = replace_once(
    cpp,
    '''\tconfig.set<bool>("show_icon_column", show_icon_column);

\tauto gamelist = config.set("GameList");
''',
    '''\tconfig.set<bool>("show_icon_column", show_icon_column);
\tconfig.set("arm64_diagnostics_flags", arm64_diagnostics_flags);
\tconfig.set<sint32>("arm64_diagnostics_hitch_threshold", arm64_diagnostics_hitch_threshold);

\tauto gamelist = config.set("GameList");
''',
    "wx config diagnostics save",
)
cpp_path.write_text(cpp, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Generated ARM64 diagnostics UI: restore flags after normal settings load and
# save immediately whenever a checkbox/master/preset/threshold changes.
# ---------------------------------------------------------------------------
main_path = Path("src/gui/wxgui/MainWindow.cpp")
main = main_path.read_text(encoding="utf-8")

helpers = r'''static void RuntimeDiagnostics_LoadPersistedSettings()
{
    RuntimeDiagnostics::SetAll(false);
    const std::string& bits = GetWxGUIConfig().arm64_diagnostics_flags;
    const size_t count = std::min(bits.size(), RuntimeDiagnostics::kFlagCount);
    for (size_t i = 0; i < count; ++i)
    {
        if (bits[i] == '1')
            RuntimeDiagnostics::SetEnabled(static_cast<DiagFlag>(i), true);
    }

    int threshold = GetWxGUIConfig().arm64_diagnostics_hitch_threshold;
    if (threshold < 1)
        threshold = 1;
    else if (threshold > 5000)
        threshold = 5000;
    RuntimeDiagnostics::g_hitchThresholdMs.store((uint32_t)threshold, std::memory_order_relaxed);
}

static void RuntimeDiagnostics_SavePersistedSettings()
{
    std::string bits(RuntimeDiagnostics::kFlagCount, '0');
    for (size_t i = 0; i < RuntimeDiagnostics::kFlagCount; ++i)
    {
        if (RuntimeDiagnostics::Enabled(static_cast<DiagFlag>(i)))
            bits[i] = '1';
    }
    GetWxGUIConfig().arm64_diagnostics_flags = bits;
    GetWxGUIConfig().arm64_diagnostics_hitch_threshold =
        (sint32)RuntimeDiagnostics::g_hitchThresholdMs.load(std::memory_order_relaxed);
    g_wxConfig.Save();
}

'''
main = replace_once(
    main,
    '''};

class RuntimeDiagnosticsDialog final : public wxDialog
{
''',
    '''};

''' + helpers + '''class RuntimeDiagnosticsDialog final : public wxDialog
{
''',
    "diagnostics persistence helpers",
)

main = replace_once(
    main,
    '''\tLoadSettings();

\t#ifdef ENABLE_DISCORD_RPC
''',
    '''\tLoadSettings();
\tRuntimeDiagnostics_LoadPersistedSettings();

\t#ifdef ENABLE_DISCORD_RPC
''',
    "restore diagnostics after settings load",
)

main = replace_once(
    main,
    '''                const bool active = RuntimeDiagnostics::Enabled(flag);
                cb->SetValue(active);
                cemuLog_log(LogType::Force, "[CEMU_DIAG] Toggle {}={}", label, active ? "ON" : "OFF");
''',
    '''                const bool active = RuntimeDiagnostics::Enabled(flag);
                cb->SetValue(active);
                RuntimeDiagnostics_SavePersistedSettings();
                cemuLog_log(LogType::Force, "[CEMU_DIAG] Toggle {}={}", label, active ? "ON" : "OFF");
''',
    "persist individual checkbox",
)

main = replace_once(
    main,
    '''        threshold->Bind(wxEVT_SPINCTRL, [threshold](wxCommandEvent&){
            RuntimeDiagnostics::g_hitchThresholdMs.store((uint32_t)threshold->GetValue(), std::memory_order_relaxed);
        });
''',
    '''        threshold->Bind(wxEVT_SPINCTRL, [threshold](wxCommandEvent&){
            RuntimeDiagnostics::g_hitchThresholdMs.store((uint32_t)threshold->GetValue(), std::memory_order_relaxed);
            RuntimeDiagnostics_SavePersistedSettings();
        });
''',
    "persist hitch threshold",
)

main = replace_once(
    main,
    '''        m_master->Bind(wxEVT_CHECKBOX, [this](wxCommandEvent& e){
            RuntimeDiagnostics::SetAll(e.IsChecked());
            RefreshChecks();
            cemuLog_log(LogType::Force, "[CEMU_DIAG] Master={}", RuntimeDiagnostics::AnyEnabled() ? "ON" : "OFF");
        });
''',
    '''        m_master->Bind(wxEVT_CHECKBOX, [this](wxCommandEvent& e){
            RuntimeDiagnostics::SetAll(e.IsChecked());
            RefreshChecks();
            RuntimeDiagnostics_SavePersistedSettings();
            cemuLog_log(LogType::Force, "[CEMU_DIAG] Master={}", RuntimeDiagnostics::AnyEnabled() ? "ON" : "OFF");
        });
''',
    "persist diagnostics master",
)

main = replace_once(
    main,
    '''            RefreshChecks();
            cemuLog_log(LogType::Force, "[CEMU_DIAG] Preset={}", preset->GetStringSelection().ToStdString());
        });
''',
    '''            RefreshChecks();
            RuntimeDiagnostics_SavePersistedSettings();
            cemuLog_log(LogType::Force, "[CEMU_DIAG] Preset={}", preset->GetStringSelection().ToStdString());
        });
''',
    "persist diagnostics preset",
)

main_path.write_text(main, encoding="utf-8", newline="\n")

print("[persistent-diagnostics] checkbox state and hitch threshold persist across restarts")
