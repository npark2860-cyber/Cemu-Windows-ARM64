"""Preserve tested sources, then prepare the NPU-only release candidate offline."""
from pathlib import Path
import hashlib, json, re, shutil, subprocess

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
SOURCE = LAB.parent / 'LSFG-Release/source'

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')

def replace(text, old, new, count=1):
    assert text.count(old) == count, (old[:100], text.count(old), count)
    return text.replace(old, new)

def edit(relative, transform):
    path = SOURCE / relative
    before = path.read_text(encoding='utf-8')
    after = transform(before)
    write(path, after)

def block_edit(text, transform):
    """Visit outer LSFG guards; keep all unrelated preprocessor conditions intact."""
    lines = text.splitlines(True)
    result = []; i = 0
    while i < len(lines):
        if lines[i].strip() != '#ifdef CEMU_ENABLE_LSFG':
            result.append(lines[i]); i += 1; continue
        start = i; depth = 1; i += 1
        while depth:
            directive = lines[i].strip()
            if re.match(r'#\s*(if|ifdef|ifndef)\b', directive): depth += 1
            elif directive.startswith('#endif'): depth -= 1
            i += 1
        result.append(transform(''.join(lines[start:i])))
    return ''.join(result)

def main():
    snapshot = HERE / 'before-source'
    assert not snapshot.exists(), 'Preserve existing preparation; do not repeat mutation'
    paths = subprocess.check_output(['git','diff','--name-only','-z'], cwd=SOURCE).decode().split('\0')
    paths += ['src/Cafe/HW/Latte/Renderer/Vulkan/VulkanNPU.cpp', 'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanLSFG.cpp', 'dependencies/npu-cemu/npu_cemu.h']
    records = []
    for relative in sorted(set(filter(None, paths))):
        source = SOURCE / relative
        if not source.is_file(): continue
        dest = snapshot / relative; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        records.append({'path': relative, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
    write(HERE / 'before-source.json', json.dumps({'base_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE).decode().strip(), 'files':records},indent=2)+'\n')

    for name in ['npu_cemu.cpp','npu_cemu.h','borrowed_support.h','gpu_resources.h','anvil_async_worker.h','buffered_timeline.h','ort_paths.h','test_buffered_timeline.cpp','test_ort_paths.cpp','build-module.cmd']:
        shutil.copy2(LAB / 'integration-v3' / name, HERE / name)
    header = (HERE/'npu_cemu.h').read_text()
    header = header.replace('// Experimental ABI.', '// Versioned NPU frame-generation ABI.').replace('#define CEMU_NPU_ABI 1u','#define CEMU_NPU_ABI 2u')
    header = replace(header, '    const wchar_t* rpcLibrary;', '    const wchar_t* rpcLibrary;\n    uint32_t processingHeight; // Exactly 1080 or 720; immutable for this context.')
    write(HERE/'npu_cemu.h',header)
    write(SOURCE/'dependencies/npu-cemu/npu_cemu.h',header)

    module = (HERE/'npu_cemu.cpp').read_text()
    module = replace(module, 'constexpr uint32_t width=1920,height=1080;\nconstexpr size_t pixels=size_t(width)*height,inputBytes=pixels*6,outputBytes=pixels*3,rgbaBytes=pixels*4,flowBytes=120*68*16;', '#include "processing_profile.h"')
    module = replace(module, '    Vulkan& vk;\n    Buffer', '    Vulkan& vk;\n    const ProcessingProfile& profile;\n    Buffer')
    module = replace(module, 'Slot(Vulkan& v):vk(v),', 'Slot(Vulkan& v,const ProcessingProfile& p):vk(v),profile(p),')
    module = replace(module, 'compute(v){}', 'compute(v,p){}')
    module = replace(module, 'composed.create();quarterA.create(480,270);quarterB.create(480,270);warpedA.create();warpedB.create();', 'composed.create(profile.width,profile.height);quarterA.create(profile.width/4,profile.height/4);quarterB.create(profile.width/4,profile.height/4);warpedA.create(profile.width,profile.height);warpedB.create(profile.width,profile.height);')
    module = module.replace('{1,1080,1920,6}', '{1,profile.height,profile.width,6}').replace('{1,1080,1920,3}', '{1,profile.height,profile.width,3}')
    for name in ['inputBytes','outputBytes','flowBytes']:
        module = re.sub(r'\b'+name+r'\b', 'profile.'+name, module)
    module = replace(module, 'struct CemuNpu {\n    Vulkan vk;', 'struct CemuNpu {\n    ProcessingProfile profile;\n    Vulkan vk;')
    module = replace(module, '        vk.initialize(info);', '        profile=ProcessingProfile::fromHeight(info.processingHeight);\n        vk.initialize(info);')
    module = module.replace('"cemu-npu-experimental"','"cemu-npu"').replace('directory/L"anvil-1080p-u8nhwc.onnx"','directory/L"npu"/profile.label/L"anvil-u8nhwc.onnx"')
    module = module.replace('Pinned U8 NHWC 1080p model required','U8 NHWC model does not match the selected processing resolution')
    module = replace(module, 'image->create();', 'image->create(profile.width,profile.height);')
    module = replace(module, 'std::make_unique<Slot>(vk)', 'std::make_unique<Slot>(vk,profile)')
    module = replace(module, 'directory/L"shaders"', 'directory/L"npu"/profile.label/L"shaders"')
    module = replace(module, 'timeline.reset(worker->reset(),width,height);', 'timeline.reset(worker->reset(),profile.width,profile.height);')
    module = replace(module, 'index,width,height,queued', 'index,profile.width,profile.height,queued')
    write(HERE/'npu_cemu.cpp',module)
    gpu = (HERE/'gpu_resources.h').read_text()
    gpu = replace(gpu, 'uint32_t imageWidth = width, uint32_t imageHeight = height', 'uint32_t imageWidth, uint32_t imageHeight')
    gpu = replace(gpu, 'struct Compute {\n    Vulkan& vk;', 'struct Compute {\n    Vulkan& vk;\n    const ProcessingProfile& profile;')
    gpu = replace(gpu, 'explicit Compute(Vulkan& v) : vk(v) {}', 'Compute(Vulkan& v,const ProcessingProfile& p) : vk(v),profile(p) {}')
    for name in ['inputBytes','outputBytes','flowBytes','pixels','width','height']:
        gpu = re.sub(r'\b'+name+r'\b','profile.'+name,gpu)
    gpu = replace(gpu, 'vk.command, 30, 17, 1', 'vk.command, (profile.width/4+15)/16, (profile.height/4+15)/16, 1')
    gpu = replace(gpu, 'vk.command, 15, 9, 2', 'vk.command, (profile.flowWidth+7)/8, (profile.flowHeight+7)/8, 2')
    write(HERE/'gpu_resources.h',gpu)

    def cmake(text):
        start=text.index('option(CEMU_ENABLE_LSFG')
        return text[:start]+'''option(CEMU_ENABLE_NPU "Build Windows ARM64 NPU frame generation" OFF)
if(CEMU_ENABLE_NPU)
    if(NOT WIN32 OR NOT CMAKE_CXX_COMPILER_ARCHITECTURE_ID STREQUAL "ARM64" OR NOT ENABLE_VULKAN)
        message(FATAL_ERROR "NPU frame generation requires Windows ARM64 and Vulkan")
    endif()
    add_compile_definitions(CEMU_ENABLE_NPU)
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()
add_subdirectory(src)
'''
    edit('CMakeLists.txt',cmake)
    edit('src/Cafe/CMakeLists.txt',lambda t: re.sub(r'if\(CEMU_ENABLE_LSFG\).*?\nendif\(\)', '''if(CEMU_ENABLE_NPU)
    target_sources(CemuCafe PRIVATE HW/Latte/Renderer/Vulkan/VulkanNPU.cpp)
    target_include_directories(CemuCafe PRIVATE "${CMAKE_SOURCE_DIR}/dependencies/npu-cemu")
endif()''',t,flags=re.S))
    def renderer_block(b):
        if 'bool generated = lsfgPresentGenerated();' in b:
            return '''#ifdef CEMU_ENABLE_NPU
    if (npuPresentGenerated())
    {
        auto& chain = GetChainInfo(true);
        ImGui_ImplVulkan_NewFrame(m_state.currentCommandBuffer, chain.m_swapchainFramebuffers[chain.swapchainImageIndex], chain.getExtent());
        ImGui_ImplVulkan_ReplayDrawData(ImGui::GetDrawData(), m_state.currentCommandBuffer);
        vkCmdEndRenderPass(m_state.currentCommandBuffer);
    }
#endif
'''
        if 'lsfgFeatures' in b or 'lsfgTimeline' in b:
            # Timeline semaphores belonged to the retired GPU backend. NPU uses fences.
            if 'lsfgTimeline' not in b: return ''
            return '''#ifdef CEMU_ENABLE_NPU
    uint32_t npuQueueCount{};
    vkGetPhysicalDeviceQueueFamilyProperties(m_physicalDevice, &npuQueueCount, nullptr);
    std::vector<VkQueueFamilyProperties> npuQueues(npuQueueCount);
    vkGetPhysicalDeviceQueueFamilyProperties(m_physicalDevice, &npuQueueCount, npuQueues.data());
    m_npuSupported = deviceFeatures2.features.shaderStorageImageExtendedFormats &&
        m_indices.graphicsFamily < npuQueueCount &&
        (npuQueues[m_indices.graphicsFamily].queueFlags & VK_QUEUE_COMPUTE_BIT);
    if (m_npuSupported) deviceFeatures.shaderStorageImageExtendedFormats = VK_TRUE;
#endif
'''
        if any(s in b for s in ['lsfgWaitStart','lsfgSubmitStart','lsfgSubmitEnd','lsfgPresentStart','lsfgBeginRealFrameTiming']): return ''
        b = b.replace('#ifdef CEMU_ENABLE_LSFG','#ifdef CEMU_ENABLE_NPU')
        b = re.sub(r'^.*\b(?:lsfgInitialize|lsfgShutdown|lsfgCapture|lsfgInvalidateSwapchain)\(.*\n','',b,flags=re.M)
        b = b.replace('m_lsfgImguiMainWindow','m_npuImguiMainWindow').replace('m_lsfgSwapchainGeneration','m_npuSwapchainGeneration').replace('LSFG-SURFACE','NPU-SURFACE')
        return b
    edit('src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp',lambda t:block_edit(t,renderer_block))
    def renderer_h(t):
        t=t.replace('struct VulkanLSFGState;\n','')
        t=re.sub(r'    VulkanLSFGState\* m_lsfg\{\};.*?    void lsfgFail\(const char\* stage, const char\* message\);', '    bool m_npuSupported{}, m_npuImguiMainWindow{};\n    uint64_t m_npuSwapchainGeneration{};',t,flags=re.S)
        return t.replace('CEMU_ENABLE_LSFG','CEMU_ENABLE_NPU')
    edit('src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h',renderer_h)
    edit('src/Cafe/HW/Latte/Renderer/Renderer.h',lambda t:t.replace('CEMU_ENABLE_LSFG','CEMU_ENABLE_NPU'))
    for path in ['src/Cafe/HW/Latte/Renderer/Vulkan/SwapchainInfoVk.cpp','src/Cafe/HW/Latte/Renderer/Vulkan/SwapchainInfoVk.h']:
        edit(path,lambda t:t.replace('CEMU_ENABLE_LSFG','CEMU_ENABLE_NPU').replace('m_lsfgTransferSource','m_npuTransferSource'))
    def config_h(t):
        return block_edit(t,lambda b:'''#ifdef CEMU_ENABLE_NPU
    ConfigValue<bool> npu_enabled{false}; // Session-only: start with original frames.
    ConfigValue<int> npu_processing_height{1080}; // Applied on the next game start.
#endif
''')
    edit('src/config/CemuConfig.h',config_h)
    def config_cpp(t):
        def block(b):
            if 'graphic.get' in b:
                return '''#ifdef CEMU_ENABLE_NPU
    npu_processing_height = graphic.get("NPUProcessingHeight", 1080) == 720 ? 720 : 1080;
#endif
'''
            return '''#ifdef CEMU_ENABLE_NPU
    graphic.set("NPUProcessingHeight", npu_processing_height);
#endif
'''
        return block_edit(t,block)
    edit('src/config/CemuConfig.cpp',config_cpp)
    def ui_block(b):
        return '''#ifdef CEMU_ENABLE_NPU
        auto* npuCheck = new wxCheckBox(graphics_panel, wxID_ANY, _("NPU frame generation"));
        npuCheck->SetValue(GetConfig().npu_enabled.GetValue());
        npuCheck->SetToolTip(_("Starts off each session. Requires Vulkan and SDR output. When enabled, both original and generated frames use the selected processing resolution and are scaled to the window. Adds one frame of latency. Late generated frames are skipped."));
        npuCheck->Bind(wxEVT_CHECKBOX, [](wxCommandEvent& event) { GetConfig().npu_enabled = event.IsChecked(); });
        npuCheck->Bind(wxEVT_UPDATE_UI, [](wxUpdateUIEvent& event) { event.Check(GetConfig().npu_enabled.GetValue()); });
        graphics_panel_sizer->Add(npuCheck, 0, wxALL, 5);
        auto* npuRow = new wxBoxSizer(wxHORIZONTAL);
        npuRow->Add(new wxStaticText(graphics_panel, wxID_ANY, _("NPU processing")), 0, wxALIGN_CENTER_VERTICAL | wxALL, 5);
        wxString npuModes[] = {_("1080p / Standard"), _("720p / Performance")};
        auto* npuMode = new wxChoice(graphics_panel, wxID_ANY, wxDefaultPosition, wxDefaultSize, std::size(npuModes), npuModes);
        npuMode->SetSelection(GetConfig().npu_processing_height.GetValue() == 720 ? 1 : 0);
        npuMode->SetToolTip(_("Applied on the next game start. 720p reduces GPU and NPU processing, with less image detail. Output follows the current window or fullscreen size."));
        npuMode->Bind(wxEVT_CHOICE, [](wxCommandEvent& event) { GetConfig().npu_processing_height = event.GetSelection() == 1 ? 720 : 1080; });
        npuRow->Add(npuMode, 1, wxALL | wxALIGN_CENTER_VERTICAL, 5);
        graphics_panel_sizer->Add(npuRow, 0, wxLEFT | wxRIGHT | wxBOTTOM | wxEXPAND, 5);
        graphics_panel_sizer->Add(new wxStaticText(graphics_panel, wxID_ANY, _("Processing resolution changes apply on the next game start.")), 0, wxLEFT | wxRIGHT | wxBOTTOM, 10);
#endif
'''
    edit('src/gui/wxgui/GeneralSettings2.cpp',lambda t:block_edit(t,ui_block))
    def overlay(t):
        t=re.sub(r'#ifdef CEMU_ENABLE_NPU\n\s*ImGui::Text\("FPS:.*?\n#endif', '                    ImGui::Text("FPS: %.2lf (NPU FG)", *outputFps);',t,flags=re.S)
        return t.replace('CEMU_ENABLE_LSFG','CEMU_ENABLE_NPU')
    edit('src/Cafe/HW/Latte/Core/LatteOverlay.cpp',overlay)
    def window(t):
        t=re.sub(r'#ifdef CEMU_ENABLE_NPU\n\s*const char\* mode=.*?\n#endif','            const char* mode="NPU FG";',t,flags=re.S)
        t=t.replace('#ifdef CEMU_ENABLE_LSFG','#ifdef CEMU_ENABLE_NPU')
        return t.replace('NPU EXP v4 - Release - Flow Cache','NPU RC1 - Release - 1080p/720p')
    edit('src/gui/wxgui/wxWindowSystem.cpp',window)
    edit('src/gui/wxgui/MainWindow.cpp',lambda t:t.replace('NPU EXP v4 - Release - Flow Cache','NPU RC1 - Release - 1080p/720p'))
    def renderer_npu(t):
        t=t.replace('    CemuNpu* context{};', '    CemuNpu* context{};\n    VkExtent2D processingExtent{1920,1080};')
        t=t.replace('constexpr VkExtent2D npuProcessingExtent{1920,1080};\n','').replace('npuProcessingExtent','state.processingExtent')
        t=t.replace(' && !GetConfig().lsfg_enabled.GetValue()','').replace('m_lsfg','m_npu')
        t=replace(t, '    try {\n        for(const auto format:', '    try {\n        if(!m_npuSupported) throw std::runtime_error("Vulkan compute queue and extended storage image formats are required");\n        const bool performance=GetConfig().npu_processing_height.GetValue()==720;\n        state.processingExtent=performance?VkExtent2D{1280,720}:VkExtent2D{1920,1080};\n        for(const auto format:')
        t=t.replace('path.c_str(),rpc.c_str()};','path.c_str(),rpc.c_str(),state.processingExtent.height};')
        t=t.replace('NPU experiment','NPU runtime').replace("this separate experiment's", "Cemu's")
        t=re.sub(r'        cemuLog_log\(LogType::Force,"\[NPU\] READY/OFF:.*?\);', '        cemuLog_log(LogType::Force,"[NPU] READY/OFF: ANVIL U8 NHWC processing={}x{}, window-sized SDR output, 3 shared slots; QNN worker and borrowed Vulkan queue. No inference at startup. One-frame buffering, cached block motion and immutable overlay replay.",state.processingExtent.width,state.processingExtent.height);',t)
        t=t.replace('processing=1920x1080 output={}x{}', 'processing={}x{} output={}x{}').replace('id,frame.realId,state.pending,extent.width,extent.height);','id,frame.realId,state.pending,state.processingExtent.width,state.processingExtent.height,extent.width,extent.height);')
        t=t.replace('std::optional<double> VulkanRenderer::npuGetFps() const {', 'std::optional<double> VulkanRenderer::GetFrameGenerationFps() const { return npuGetFps(); }\nstd::optional<double> VulkanRenderer::npuGetFps() const {')
        return t
    edit('src/Cafe/HW/Latte/Renderer/Vulkan/VulkanNPU.cpp',renderer_npu)
    print('NPU-only source and ABI v2 module prepared; no device execution.')

if __name__ == '__main__': main()
