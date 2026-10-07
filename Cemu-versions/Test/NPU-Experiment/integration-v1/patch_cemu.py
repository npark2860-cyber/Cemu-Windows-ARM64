"""Add the opt-in NPU integration without replacing the tested GPU LSFG binary."""
from pathlib import Path
root=Path(__file__).resolve().parents[2]/'LSFG-Release/source'
def edit(path,old,new,count=1):
    file=root/path; text=file.read_text(encoding='utf-8-sig')
    if text.count(new)==count: return
    if text.count(old)!=count: raise RuntimeError(f'{path}: expected {count} anchors, got {text.count(old)}')
    file.write_text(text.replace(old,new),encoding='utf-8')
edit('CMakeLists.txt','add_subdirectory(src)','''option(CEMU_ENABLE_NPU "Build experimental ANVIL NPU integration" OFF)
if(CEMU_ENABLE_NPU)
    if(NOT CEMU_ENABLE_LSFG)
        message(FATAL_ERROR "NPU experiment requires the Windows ARM64 LSFG Release base")
    endif()
    add_compile_definitions(CEMU_ENABLE_NPU)
endif()
add_subdirectory(src)''')
edit('src/Cafe/CMakeLists.txt','    target_sources(CemuCafe PRIVATE HW/Latte/Renderer/Vulkan/VulkanLSFG.cpp)',
'''    target_sources(CemuCafe PRIVATE HW/Latte/Renderer/Vulkan/VulkanLSFG.cpp)
    if(CEMU_ENABLE_NPU)
        target_sources(CemuCafe PRIVATE HW/Latte/Renderer/Vulkan/VulkanNPU.cpp)
        target_include_directories(CemuCafe PRIVATE "${CMAKE_SOURCE_DIR}/dependencies/npu-cemu")
    endif()''')
header='src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h'
edit(header,'struct VulkanLSFGState;','struct VulkanLSFGState;\nstruct VulkanNPUState;')
edit(header,'    VulkanLSFGState* m_lsfg{};','''#ifdef CEMU_ENABLE_NPU
    VulkanNPUState* m_npu{};
    void npuInitialize();
    void npuShutdown();
    void npuCapture();
    void npuInvalidate();
    bool npuPresentGenerated();
    void npuRecordPresent(VkResult result);
    std::optional<double> npuGetFps() const;
#endif
    VulkanLSFGState* m_lsfg{};''')
renderer='src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp'
edit(renderer,'    lsfgInitialize();','''    lsfgInitialize();
#ifdef CEMU_ENABLE_NPU
    npuInitialize();
#endif''')
edit(renderer,'    lsfgShutdown();','''#ifdef CEMU_ENABLE_NPU
    npuShutdown();
#endif
    lsfgShutdown();''',count=2)
edit(renderer,'    if (lsfgPresentGenerated())','''    if (lsfgPresentGenerated()
#ifdef CEMU_ENABLE_NPU
        || npuPresentGenerated()
#endif
    )''')
edit(renderer,'        lsfgInvalidateSwapchain();','''        lsfgInvalidateSwapchain();
#ifdef CEMU_ENABLE_NPU
        npuInvalidate();
#endif''')
edit(renderer,'        if (!padView) lsfgCapture();','''        if (!padView) lsfgCapture();
#ifdef CEMU_ENABLE_NPU
        if (!padView) npuCapture();
#endif''',count=1)
# The non-FSR path uses a different indent in the original.
edit(renderer,'    if (!padView) lsfgCapture();\n#endif\n}', '''    if (!padView) lsfgCapture();
#ifdef CEMU_ENABLE_NPU
    if (!padView) npuCapture();
#endif
#endif
}''')
edit(renderer,'\tVkResult result = vkQueuePresentKHR(m_presentQueue, &presentInfo);', '''\tVkResult result = vkQueuePresentKHR(m_presentQueue, &presentInfo);
#ifdef CEMU_ENABLE_NPU
    if(mainWindow) npuRecordPresent(result);
#endif''')
edit('src/Cafe/HW/Latte/Renderer/Vulkan/VulkanLSFG.cpp',
'''std::optional<double> VulkanRenderer::GetFrameGenerationFps() const
{''','''std::optional<double> VulkanRenderer::GetFrameGenerationFps() const
{
#ifdef CEMU_ENABLE_NPU
    if(GetConfig().npu_enabled.GetValue()) return npuGetFps();
#endif''')
edit('src/config/CemuConfig.h','    ConfigValue<bool> lsfg_enabled{false};', '''#ifdef CEMU_ENABLE_NPU
    ConfigValue<bool> npu_enabled{false}; // Session-only experimental NPU toggle.
#endif
    ConfigValue<bool> lsfg_enabled{false};''')
ui='src/gui/wxgui/GeneralSettings2.cpp'
edit(ui,'        lsfgCheck->Bind(wxEVT_CHECKBOX, [](wxCommandEvent& event) { GetConfig().lsfg_enabled = event.IsChecked(); });',
'''        lsfgCheck->Bind(wxEVT_CHECKBOX, [](wxCommandEvent& event) {
            GetConfig().lsfg_enabled = event.IsChecked();
#ifdef CEMU_ENABLE_NPU
            if(event.IsChecked()) GetConfig().npu_enabled=false;
#endif
        });''')
edit(ui,'        graphics_panel_sizer->Add(lsfgCheck, 0, wxALL, 5);','''        graphics_panel_sizer->Add(lsfgCheck, 0, wxALL, 5);
#ifdef CEMU_ENABLE_NPU
        auto* npuCheck=new wxCheckBox(graphics_panel,wxID_ANY,_("NPU frame generation (experimental, Vulkan, 1080p output)"));
        npuCheck->SetValue(GetConfig().npu_enabled.GetValue());
        npuCheck->SetToolTip(_("Starts off. Requires a 1920x1080 SDR output window; other sizes show original frames. Buffers one real frame, adding one frame of input latency. Late generated frames are skipped. Enabling this turns GPU LSFG off. Motion quality and display cadence are experimental."));
        npuCheck->Bind(wxEVT_CHECKBOX,[](wxCommandEvent& event){GetConfig().npu_enabled=event.IsChecked();if(event.IsChecked())GetConfig().lsfg_enabled=false;});
        npuCheck->Bind(wxEVT_UPDATE_UI,[](wxUpdateUIEvent& event){event.Check(GetConfig().npu_enabled.GetValue());});
        graphics_panel_sizer->Add(npuCheck,0,wxALL,5);
#endif''')
edit('src/gui/wxgui/MainWindow.cpp','#ifdef CEMU_ENABLE_LSFG\n\treturn wxASCII_STR("Cemu ARM64 [LSFG RESIZE]");',
'''#ifdef CEMU_ENABLE_NPU
    return wxASCII_STR("Cemu ARM64 [NPU EXP v1 - Release]");
#elif defined(CEMU_ENABLE_LSFG)
\treturn wxASCII_STR("Cemu ARM64 [LSFG RESIZE]");''')
ws='src/gui/wxgui/wxWindowSystem.cpp'
edit(ws,'#ifdef CEMU_ENABLE_LSFG\n\twindowText = "Cemu ARM64 [LSFG RESIZE]";',
'''#ifdef CEMU_ENABLE_NPU
    windowText = "Cemu ARM64 [NPU EXP v1 - Release]";
#elif defined(CEMU_ENABLE_LSFG)
\twindowText = "Cemu ARM64 [LSFG RESIZE]";''')
edit(ws,'            fpsText = fmt::format("{:.2f} (Native: {:.2f}, LSFG 2X)", *outputFps, fps);',
'''        {
#ifdef CEMU_ENABLE_NPU
            const char* mode=GetConfig().npu_enabled.GetValue()?"NPU FG":"LSFG 2X";
#else
            const char* mode="LSFG 2X";
#endif
            fpsText = fmt::format("{:.2f} (Native: {:.2f}, {})", *outputFps, fps, mode);
        }''')
edit('src/Cafe/HW/Latte/Core/LatteOverlay.cpp','                    ImGui::Text("FPS: %.2lf (LSFG 2X)", *outputFps);',
'''#ifdef CEMU_ENABLE_NPU
                    ImGui::Text("FPS: %.2lf (%s)", *outputFps, config.npu_enabled.GetValue()?"NPU FG":"LSFG 2X");
#else
                    ImGui::Text("FPS: %.2lf (LSFG 2X)", *outputFps);
#endif''')
api=root/'dependencies/npu-cemu/npu_cemu.h';api.parent.mkdir(exist_ok=True)
api.write_bytes((Path(__file__).parent/'npu_cemu.h').read_bytes())
print('Applied explicit NPU option, renderer hooks, UI and experiment identity.')
