from pathlib import Path
import shutil

lab = Path(__file__).parent / 'Cemu-versions/Test/LSFG-Release'
root = lab / 'source'

def edit(relative, before, after, count=1):
    path = root / relative
    text = path.read_text(encoding='utf-8-sig')
    found = text.count(before)
    if found != count:
        raise RuntimeError(f'{relative}: expected {count} anchors, got {found}: {before[:70]!r}')
    path.write_text(text.replace(before, after), encoding='utf-8', newline='\n')

# No preprocessing from another role is imported; this experiment starts from
# the already reproduced stock Release workflow.
shutil.copytree(lab / 'module-work', root / 'dependencies/lsfg-cemu-arm64')
shutil.copy2(lab / 'integration/VulkanLSFG.cpp', root / 'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanLSFG.cpp')
edit('CMakeLists.txt', 'add_subdirectory(src)', '''option(CEMU_ENABLE_LSFG "Build experimental Windows ARM64 LSFG integration" OFF)
if(CEMU_ENABLE_LSFG)
    if(NOT WIN32 OR NOT CMAKE_CXX_COMPILER_ARCHITECTURE_ID STREQUAL "ARM64" OR NOT ENABLE_VULKAN)
        message(FATAL_ERROR "LSFG integration requires Windows ARM64 and Vulkan")
    endif()
    add_compile_definitions(CEMU_ENABLE_LSFG)
    add_subdirectory(dependencies/lsfg-cemu-arm64)
endif()
add_subdirectory(src)''')
edit('src/Cafe/CMakeLists.txt', 'cemu_use_precompiled_header(CemuCafe)', '''if(CEMU_ENABLE_LSFG)
    target_sources(CemuCafe PRIVATE HW/Latte/Renderer/Vulkan/VulkanLSFG.cpp)
    target_link_libraries(CemuCafe PRIVATE LSFGCemu::LSFGCemu)
endif()
cemu_use_precompiled_header(CemuCafe)''')
edit('src/config/CemuConfig.h', '\tConfigValue<sint32> fsr_sharpness{25};', '''#ifdef CEMU_ENABLE_LSFG
    ConfigValue<bool> lsfg_enabled{false}; // Session-only: always start OFF.
    ConfigValue<std::string> lsfg_dll_path{""};
#endif
\tConfigValue<sint32> fsr_sharpness{25};''')
edit('src/config/CemuConfig.cpp', '\tfsr_sharpness = fsrSharpnessValue;', '''\tfsr_sharpness = fsrSharpnessValue;
#ifdef CEMU_ENABLE_LSFG
    lsfg_dll_path = graphic.get("LSFGDllPath", std::string{});
#endif''')
edit('src/config/CemuConfig.cpp', '\tgraphic.set("FSRSharpness", fsr_sharpness);', '''\tgraphic.set("FSRSharpness", fsr_sharpness);
#ifdef CEMU_ENABLE_LSFG
    graphic.set("LSFGDllPath", lsfg_dll_path);
#endif''')
edit('src/gui/wxgui/GeneralSettings2.cpp', '\t\tgraphics_panel_sizer->Add(fsr_sharpness_row, 0, wxLEFT | wxRIGHT | wxBOTTOM | wxEXPAND, 5);', '''\t\tgraphics_panel_sizer->Add(fsr_sharpness_row, 0, wxLEFT | wxRIGHT | wxBOTTOM | wxEXPAND, 5);
#ifdef CEMU_ENABLE_LSFG
        auto* lsfgCheck = new wxCheckBox(graphics_panel, wxID_ANY, _("LSFG 2x frame generation (experimental, Vulkan)"));
        lsfgCheck->SetValue(GetConfig().lsfg_enabled.GetValue());
        lsfgCheck->SetToolTip(_("Generates an intermediate frame after scaling. Starts off each session. Requires a compatible Lossless.dll."));
        lsfgCheck->Bind(wxEVT_CHECKBOX, [](wxCommandEvent& event) { GetConfig().lsfg_enabled = event.IsChecked(); });
        graphics_panel_sizer->Add(lsfgCheck, 0, wxALL, 5);
        auto* lsfgPath = new wxTextCtrl(graphics_panel, wxID_ANY, wxString::FromUTF8(GetConfig().lsfg_dll_path.GetValue()));
        lsfgPath->SetHint(_("Lossless.dll path (empty: auto-detect). Restart game after changing."));
        lsfgPath->Bind(wxEVT_TEXT, [lsfgPath](wxCommandEvent&) { GetConfig().lsfg_dll_path = lsfgPath->GetValue().ToStdString(wxConvUTF8); });
        graphics_panel_sizer->Add(lsfgPath, 0, wxLEFT | wxRIGHT | wxBOTTOM | wxEXPAND, 5);
#endif''')
header = 'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h'
edit(header, 'struct VkSupportedFormatInfo_t', 'struct VulkanLSFGState;\n\nstruct VkSupportedFormatInfo_t')
edit(header, '\tstd::array<FSRIntermediate, 2> m_fsrIntermediate{};', '''#ifdef CEMU_ENABLE_LSFG
    VulkanLSFGState* m_lsfg{};
    bool m_lsfgSupported{}, m_lsfgImguiMainWindow{};
    void lsfgInitialize();
    void lsfgShutdown();
    bool lsfgEnsureContext();
    bool lsfgReleaseContext();
    void lsfgCapture();
    bool lsfgPresentGenerated();
    void lsfgFail(const char* stage, const char* message);
#endif
\tstd::array<FSRIntermediate, 2> m_fsrIntermediate{};''')
renderer = 'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp'
edit(renderer, '\tvkGetPhysicalDeviceFeatures2(m_physicalDevice, &deviceFeatures2);', '''#ifdef CEMU_ENABLE_LSFG
    VkPhysicalDeviceVulkan12Features lsfgFeatures{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES};
    deviceFeatures2.pNext = &lsfgFeatures;
#endif
\tvkGetPhysicalDeviceFeatures2(m_physicalDevice, &deviceFeatures2);''')
edit(renderer, '\tvoid* deviceExtensionFeatures = nullptr;', '''\tvoid* deviceExtensionFeatures = nullptr;
#ifdef CEMU_ENABLE_LSFG
    VkPhysicalDeviceProperties lsfgProperties{};
    vkGetPhysicalDeviceProperties(m_physicalDevice, &lsfgProperties);
    uint32_t lsfgQueueCount{};
    vkGetPhysicalDeviceQueueFamilyProperties(m_physicalDevice, &lsfgQueueCount, nullptr);
    std::vector<VkQueueFamilyProperties> lsfgQueues(lsfgQueueCount);
    vkGetPhysicalDeviceQueueFamilyProperties(m_physicalDevice, &lsfgQueueCount, lsfgQueues.data());
    m_lsfgSupported = lsfgProperties.apiVersion >= VK_API_VERSION_1_2 && lsfgFeatures.timelineSemaphore &&
        deviceFeatures2.features.shaderStorageImageExtendedFormats && m_indices.graphicsFamily < lsfgQueueCount &&
        (lsfgQueues[m_indices.graphicsFamily].queueFlags & VK_QUEUE_COMPUTE_BIT);
    VkPhysicalDeviceTimelineSemaphoreFeatures lsfgTimeline{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_TIMELINE_SEMAPHORE_FEATURES};
    if (m_lsfgSupported)
    {
        lsfgTimeline.timelineSemaphore = VK_TRUE;
        deviceExtensionFeatures = &lsfgTimeline;
        deviceFeatures.shaderStorageImageExtendedFormats = VK_TRUE;
    }
#endif''')
edit(renderer, '\tCreateNullObjects();\n}', '''\tCreateNullObjects();
#ifdef CEMU_ENABLE_LSFG
    lsfgInitialize();
#endif
}''')
edit(renderer, '\tfsrDestroyResources();', '''#ifdef CEMU_ENABLE_LSFG
    lsfgShutdown();
#endif
\tfsrDestroyResources();''')
edit(renderer, '\t// shut down pipeline save thread', '''#ifdef CEMU_ENABLE_LSFG
    lsfgShutdown(); // Covers shutdown after partial initialization.
#endif
\t// shut down pipeline save thread''')
edit(renderer, '\t\tDrawBackbufferQuadFSR(texView, shader, imageX, imageY, imageWidth, imageHeight, padView);', '''\t\tDrawBackbufferQuadFSR(texView, shader, imageX, imageY, imageWidth, imageHeight, padView);
#ifdef CEMU_ENABLE_LSFG
        if (!padView) lsfgCapture();
#endif''')
edit(renderer, '\t// mark current swapchain image as well defined\n\tchainInfo.hasDefinedSwapchainImage = true;\n}', '''\t// mark current swapchain image as well defined
\tchainInfo.hasDefinedSwapchainImage = true;
#ifdef CEMU_ENABLE_LSFG
    if (!padView) lsfgCapture();
#endif
}''')
edit(renderer, 'bool VulkanRenderer::ImguiBegin(bool mainWindow)\n{', '''bool VulkanRenderer::ImguiBegin(bool mainWindow)
{
#ifdef CEMU_ENABLE_LSFG
    m_lsfgImguiMainWindow = mainWindow;
#endif''')
edit(renderer, '''void VulkanRenderer::ImguiEnd()
{
\tImGui::Render();
\tImGui_ImplVulkan_RenderDrawData(ImGui::GetDrawData(), m_state.currentCommandBuffer);
\tvkCmdEndRenderPass(m_state.currentCommandBuffer);
}''', '''void VulkanRenderer::ImguiEnd()
{
\tImGui::Render();
\tImGui_ImplVulkan_RenderDrawData(ImGui::GetDrawData(), m_state.currentCommandBuffer);
\tvkCmdEndRenderPass(m_state.currentCommandBuffer);
#ifdef CEMU_ENABLE_LSFG
    if (lsfgPresentGenerated())
    {
        auto& chain = GetChainInfo(true);
        ImGui_ImplVulkan_NewFrame(m_state.currentCommandBuffer, chain.m_swapchainFramebuffers[chain.swapchainImageIndex], chain.getExtent());
        ImGui_ImplVulkan_RenderDrawData(ImGui::GetDrawData(), m_state.currentCommandBuffer);
        vkCmdEndRenderPass(m_state.currentCommandBuffer);
    }
#endif
}''')
edit('src/Cafe/HW/Latte/Renderer/Vulkan/SwapchainInfoVk.h', '\tbool hasDefinedSwapchainImage{};', '\tbool m_lsfgTransferSource{};\n\tbool hasDefinedSwapchainImage{};')
edit('src/Cafe/HW/Latte/Renderer/Vulkan/SwapchainInfoVk.cpp', '\tcreate_info.imageUsage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT;', '''\tcreate_info.imageUsage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT;
#ifdef CEMU_ENABLE_LSFG
    m_lsfgTransferSource = mainWindow && (details.capabilities.supportedUsageFlags & VK_IMAGE_USAGE_TRANSFER_SRC_BIT);
    if (m_lsfgTransferSource) create_info.imageUsage |= VK_IMAGE_USAGE_TRANSFER_SRC_BIT;
#endif''')
print('Applied LSFG experiment to stock Release source; active four baselines untouched.')
