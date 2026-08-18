from pathlib import Path
import subprocess

ROOT = Path('.')


def replace_once(path_str: str, old_lf: str, new_lf: str, label: str) -> None:
    path = ROOT / path_str
    raw = path.read_bytes()
    text = raw.decode('utf-8')
    nl = '\r\n' if '\r\n' in text else '\n'
    old = old_lf.replace('\n', nl)
    new = new_lf.replace('\n', nl)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: anchor count={count}, expected 1')
    path.write_bytes(text.replace(old, new, 1).encode('utf-8'))


def replace_exact_count(path_str: str, old_lf: str, new_lf: str, expected: int, label: str) -> None:
    path = ROOT / path_str
    raw = path.read_bytes()
    text = raw.decode('utf-8')
    nl = '\r\n' if '\r\n' in text else '\n'
    old = old_lf.replace('\n', nl)
    new = new_lf.replace('\n', nl)
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f'{label}: anchor count={count}, expected {expected}')
    path.write_bytes(text.replace(old, new).encode('utf-8'))


# The first-stage script provides AMD FSR1 EASU. Complete it here with
# Eden/Yuzu-style RCAS sharpening, a persistent sharpness control, and a
# genuine Vulkan two-pass EASU -> FP16 intermediate -> RCAS present path.

# Keep old filter values stable and promote the experiment name from EASU-only
# to the full FSR1 path.
replace_once(
    'src/config/CemuConfig.h',
    '\tkFidelityFXFSREasuFilter,',
    '\tkFidelityFXFSRFilter,',
    'rename FSR filter enum',
)

replace_once(
    'src/Cafe/HW/Latte/Core/LatteRenderTarget.cpp',
    'kFidelityFXFSREasuFilter',
    'kFidelityFXFSRFilter',
    'rename FSR selection',
)

replace_once(
    'src/config/CemuConfig.h',
    '''\tConfigValue<sint32> upscale_filter{kBicubicFilter};
\tConfigValue<sint32> downscale_filter{kLinearFilter};
\tConfigValue<sint32> fullscreen_scaling{kKeepAspectRatio};''',
    '''\tConfigValue<sint32> upscale_filter{kBicubicFilter};
\tConfigValue<sint32> downscale_filter{kLinearFilter};
\tConfigValue<sint32> fsr_sharpness{25}; // FSR1 RCAS stops * 100, matching Eden/Yuzu semantics
\tConfigValue<sint32> fullscreen_scaling{kKeepAspectRatio};''',
    'FSR sharpness config field',
)

replace_once(
    'src/config/CemuConfig.cpp',
    '''\tupscale_filter = graphic.get("UpscaleFilter", kBicubicHermiteFilter);
\tdownscale_filter = graphic.get("DownscaleFilter", kLinearFilter);
\tfullscreen_scaling = graphic.get("FullscreenScaling", kKeepAspectRatio);''',
    '''\tupscale_filter = graphic.get("UpscaleFilter", kBicubicHermiteFilter);
\tdownscale_filter = graphic.get("DownscaleFilter", kLinearFilter);
\tsint32 fsrSharpnessValue = graphic.get("FSRSharpness", 25);
\tif (fsrSharpnessValue < 0)
\t\tfsrSharpnessValue = 0;
\telse if (fsrSharpnessValue > 200)
\t\tfsrSharpnessValue = 200;
\tfsr_sharpness = fsrSharpnessValue;
\tfullscreen_scaling = graphic.get("FullscreenScaling", kKeepAspectRatio);''',
    'load FSR sharpness',
)

replace_once(
    'src/config/CemuConfig.cpp',
    '''\tgraphic.set("UpscaleFilter", upscale_filter);
\tgraphic.set("DownscaleFilter", downscale_filter);
\tgraphic.set("FullscreenScaling", fullscreen_scaling);''',
    '''\tgraphic.set("UpscaleFilter", upscale_filter);
\tgraphic.set("DownscaleFilter", downscale_filter);
\tgraphic.set("FSRSharpness", fsr_sharpness);
\tgraphic.set("FullscreenScaling", fullscreen_scaling);''',
    'save FSR sharpness',
)

# Graphics settings UI: keep FSR as an upscale filter, expose the same 0..200
# RCAS stops*100 control used by the Eden/Yuzu implementation.
replace_once(
    'src/gui/wxgui/GeneralSettings2.h',
    '''\twxRadioBox* m_upscale_filter, *m_downscale_filter, *m_fullscreen_scaling;
\twxChoice* m_overlay_position,''',
    '''\twxRadioBox* m_upscale_filter, *m_downscale_filter, *m_fullscreen_scaling;
\twxSlider* m_fsr_sharpness;
\twxStaticText* m_fsr_sharpness_value;
\twxChoice* m_overlay_position,''',
    'FSR UI members',
)

replace_once(
    'src/gui/wxgui/GeneralSettings2.cpp',
    '_("FidelityFX FSR (EASU)")',
    '_("AMD FidelityFX FSR")',
    'FSR UI name',
)

replace_once(
    'src/gui/wxgui/GeneralSettings2.cpp',
    '''\t\tm_upscale_filter->Bind(wxEVT_RADIOBOX, [](wxCommandEvent& event) {
\t\t\tGetConfig().upscale_filter = event.GetSelection();
\t\t});
\t\tgraphics_panel_sizer->Add(m_upscale_filter, 0, wxALL | wxEXPAND, 5);

\t\twxString downscale_choices[] = { _("Bilinear"), _("Bicubic"), _("Hermite"), _("Nearest Neighbor") };''',
    '''\t\tm_upscale_filter->Bind(wxEVT_RADIOBOX, [this](wxCommandEvent& event) {
\t\t\tGetConfig().upscale_filter = event.GetSelection();
\t\t\tconst bool fsrSelected = event.GetSelection() == kFidelityFXFSRFilter;
\t\t\tm_fsr_sharpness->Enable(fsrSelected);
\t\t\tm_fsr_sharpness_value->Enable(fsrSelected);
\t\t});
\t\tgraphics_panel_sizer->Add(m_upscale_filter, 0, wxALL | wxEXPAND, 5);

\t\tauto* fsr_sharpness_row = new wxBoxSizer(wxHORIZONTAL);
\t\tfsr_sharpness_row->Add(new wxStaticText(graphics_panel, wxID_ANY, _("FSR RCAS sharpness")), 0, wxALIGN_CENTER_VERTICAL | wxALL, 5);
\t\tm_fsr_sharpness = new wxSlider(graphics_panel, wxID_ANY, 25, 0, 200, wxDefaultPosition, wxSize(250, -1));
\t\tm_fsr_sharpness->SetToolTip(_("AMD FSR1 RCAS sharpness stops x100. Matches Eden/Yuzu semantics: 0 is strongest sharpening, 200 is weakest."));
\t\tfsr_sharpness_row->Add(m_fsr_sharpness, 1, wxALIGN_CENTER_VERTICAL | wxALL, 5);
\t\tm_fsr_sharpness_value = new wxStaticText(graphics_panel, wxID_ANY, "25");
\t\tfsr_sharpness_row->Add(m_fsr_sharpness_value, 0, wxALIGN_CENTER_VERTICAL | wxALL, 5);
\t\tm_fsr_sharpness->Bind(wxEVT_SLIDER, [this](wxCommandEvent& event) {
\t\t\tconst sint32 value = event.GetInt();
\t\t\tGetConfig().fsr_sharpness = value;
\t\t\tm_fsr_sharpness_value->SetLabel(wxString::Format("%d", value));
\t\t});
\t\tgraphics_panel_sizer->Add(fsr_sharpness_row, 0, wxLEFT | wxRIGHT | wxBOTTOM | wxEXPAND, 5);

\t\twxString downscale_choices[] = { _("Bilinear"), _("Bicubic"), _("Hermite"), _("Nearest Neighbor") };''',
    'FSR sharpness UI',
)

replace_once(
    'src/gui/wxgui/GeneralSettings2.cpp',
    '''\tm_upscale_filter->SetSelection(config.upscale_filter);
\tm_downscale_filter->SetSelection(config.downscale_filter);''',
    '''\tm_upscale_filter->SetSelection(config.upscale_filter);
\tm_fsr_sharpness->SetValue(config.fsr_sharpness.GetValue());
\tm_fsr_sharpness_value->SetLabel(wxString::Format("%d", config.fsr_sharpness.GetValue()));
\tconst bool fsrSelected = config.upscale_filter.GetValue() == kFidelityFXFSRFilter;
\tm_fsr_sharpness->Enable(fsrSelected);
\tm_fsr_sharpness_value->Enable(fsrSelected);
\tm_downscale_filter->SetSelection(config.downscale_filter);''',
    'apply FSR UI config',
)

# One extra uniform carries the RCAS "stops" value. Normal output shaders ignore it.
replace_once(
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.h',
    '''\t\tfloat targetGamma;
\t\tfloat displayGamma;
\t};''',
    '''\t\tfloat targetGamma;
\t\tfloat displayGamma;
\t\tfloat fsrSharpness;
\t};''',
    'FSR output uniform',
)

replace_once(
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.h',
    '''\tstatic RendererOutputShader* s_fsr_easu_shader;
\tstatic RendererOutputShader* s_fsr_easu_shader_ud;

\tstatic std::string GetOpenGlVertexSource(bool render_upside_down);''',
    '''\tstatic RendererOutputShader* s_fsr_easu_shader;
\tstatic RendererOutputShader* s_fsr_easu_shader_ud;
\tstatic RendererOutputShader* s_fsr_rcas_shader;

\tstatic std::string GetOpenGlVertexSource(bool render_upside_down);''',
    'RCAS shader pointer declaration',
)

replace_once(
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.h',
    '''\tstatic const std::string s_hermite_shader_source;
\tstatic const std::string s_fsr_easu_shader_source;

\tstatic const std::string s_bicubic_shader_source_vk;''',
    '''\tstatic const std::string s_hermite_shader_source;
\tstatic const std::string s_fsr_easu_shader_source;
\tstatic const std::string s_fsr_rcas_shader_source;

\tstatic const std::string s_bicubic_shader_source_vk;''',
    'RCAS shader source declaration',
)

replace_once(
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.cpp',
    '''uniform float targetGamma;
uniform float displayGamma;
};''',
    '''uniform float targetGamma;
uniform float displayGamma;
uniform float fsrSharpness;
};''',
    'FSR shader uniform preamble',
)

replace_once(
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.cpp',
    '''\tvars.displayGamma = GetConfig().userDisplayGamma;

\treturn vars;''',
    '''\tvars.displayGamma = GetConfig().userDisplayGamma;
\tvars.fsrSharpness = (float)GetConfig().fsr_sharpness.GetValue() / 100.0f;

\treturn vars;''',
    'fill FSR sharpness uniform',
)

rcas_source = r'''
// AMD FidelityFX Super Resolution 1.0 - RCAS sharpening stage.
// This is the 32-bit 5-tap RCAS resolve used after EASU. The AMD FSR1
// license notice carried by the EASU source above applies to this port.

ivec2 fsrClampPixel(ivec2 p, ivec2 size)
{
    return clamp(p, ivec2(0), size - ivec2(1));
}

vec3 fsrRcasLoad(ivec2 p, ivec2 size)
{
    return texelFetch(textureSrc, fsrClampPixel(p, size), 0).rgb;
}

void outputShader()
{
    ivec2 size = max(textureSize(textureSrc, 0), ivec2(1));
    ivec2 p = ivec2(floor(passUV * vec2(size)));
    p = fsrClampPixel(p, size);

    // Cross-shaped 5 tap neighborhood:
    //       b
    //     d e f
    //       h
    vec3 b = fsrRcasLoad(p + ivec2( 0, -1), size);
    vec3 d = fsrRcasLoad(p + ivec2(-1,  0), size);
    vec3 e = fsrRcasLoad(p,                   size);
    vec3 f = fsrRcasLoad(p + ivec2( 1,  0), size);
    vec3 h = fsrRcasLoad(p + ivec2( 0,  1), size);

    vec3 mn4 = min(min(b, d), min(f, h));
    vec3 mx4 = max(max(b, d), max(f, h));

    // RCAS clipping limiters. Guard only the exact zero denominators; the
    // limiter shape and the -0.1875 lobe limit match AMD FSR1.
    vec3 hitMin = min(mn4, e) / max(vec3(1.0e-6), 4.0 * mx4);
    vec3 hitMaxDenom = min(vec3(-1.0e-6), 4.0 * mn4 - vec3(4.0));
    vec3 hitMax = (vec3(1.0) - max(mx4, e)) / hitMaxDenom;
    vec3 lobeRGB = max(-hitMin, hitMax);

    float lobe = max(lobeRGB.r, max(lobeRGB.g, lobeRGB.b));
    lobe = max(-0.1875, min(lobe, 0.0));

    // Eden/Yuzu passes slider/100 to FsrRcasCon(), where the value is in
    // stops and is converted to a linear multiplier with exp2(-stops).
    float sharp = exp2(-clamp(fsrSharpness, 0.0, 2.0));
    lobe *= sharp;

    float rcpL = 1.0 / (4.0 * lobe + 1.0);
    vec3 result = (lobe * (b + d + f + h) + e) * rcpL;
    colorOut0 = vec4(result, 1.0);
}
'''.strip('\n')

rcas_insert = (
    'const std::string RendererOutputShader::s_fsr_rcas_shader_source =\n'
    'R"(\n' + rcas_source + '\n)";\n\n'
    'RendererOutputShader* RendererOutputShader::s_copy_shader;'
)

replace_once(
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.cpp',
    'RendererOutputShader* RendererOutputShader::s_copy_shader;',
    rcas_insert,
    'RCAS GLSL source',
)

replace_once(
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.cpp',
    '''RendererOutputShader* RendererOutputShader::s_fsr_easu_shader;
RendererOutputShader* RendererOutputShader::s_fsr_easu_shader_ud;

std::string RendererOutputShader::GetOpenGlVertexSource(bool render_upside_down)''',
    '''RendererOutputShader* RendererOutputShader::s_fsr_easu_shader;
RendererOutputShader* RendererOutputShader::s_fsr_easu_shader_ud;
RendererOutputShader* RendererOutputShader::s_fsr_rcas_shader;

std::string RendererOutputShader::GetOpenGlVertexSource(bool render_upside_down)''',
    'RCAS shader pointer definition',
)

replace_exact_count(
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.cpp',
    '''    \ts_fsr_easu_shader = new RendererOutputShader(vertex_source, s_fsr_easu_shader_source);
    \ts_fsr_easu_shader_ud = new RendererOutputShader(vertex_source_ud, s_fsr_easu_shader_source);
\t\tbreak;''',
    '''    \ts_fsr_easu_shader = new RendererOutputShader(vertex_source, s_fsr_easu_shader_source);
    \ts_fsr_easu_shader_ud = new RendererOutputShader(vertex_source_ud, s_fsr_easu_shader_source);
    \ts_fsr_rcas_shader = new RendererOutputShader(vertex_source, s_fsr_rcas_shader_source);
\t\tbreak;''',
    2,
    'OpenGL/Vulkan RCAS init',
)

replace_once(
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.cpp',
    '''\tdelete s_fsr_easu_shader;
\tdelete s_fsr_easu_shader_ud;
}''',
    '''\tdelete s_fsr_easu_shader;
\tdelete s_fsr_easu_shader_ud;
\tdelete s_fsr_rcas_shader;
}''',
    'RCAS shutdown',
)

# Vulkan renderer gets a true two-pass FSR1 route. EASU renders to an
# output-sized RGBA16F image, then RCAS samples that image and presents it.
replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h',
    '''\tVkPipeline backbufferBlit_createGraphicsPipeline(VkDescriptorSetLayout descriptorLayout, bool padView, RendererOutputShader* shader);
\tbool AcquireNextSwapchainImage(bool mainWindow);''',
    '''\tVkPipeline backbufferBlit_createGraphicsPipeline(VkDescriptorSetLayout descriptorLayout, bool padView, RendererOutputShader* shader, VkRenderPass overrideRenderPass = VK_NULL_HANDLE);
\tbool AcquireNextSwapchainImage(bool mainWindow);''',
    'backbuffer pipeline override renderpass declaration',
)

replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h',
    '''\tVkDescriptorSetLayout m_swapchainDescriptorSetLayout;

\tVkQueue m_graphicsQueue, m_presentQueue;''',
    '''\tVkDescriptorSetLayout m_swapchainDescriptorSetLayout;

\tstruct FSRIntermediate
\t{
\t\tVkImage image{ VK_NULL_HANDLE };
\t\tVkImageView view{ VK_NULL_HANDLE };
\t\tVkFramebuffer framebuffer{ VK_NULL_HANDLE };
\t\tVkImageMemAllocation* allocation{ nullptr };
\t\tVkDescriptorSet descriptorSet{ VK_NULL_HANDLE };
\t\tuint32 width{ 0 };
\t\tuint32 height{ 0 };
\t};
\tstd::array<FSRIntermediate, 2> m_fsrIntermediate{};
\tVkRenderPass m_fsrRenderPass{ VK_NULL_HANDLE };
\tVkSampler m_fsrSampler{ VK_NULL_HANDLE };

\tvoid fsrEnsureIntermediate(bool padView, uint32 width, uint32 height);
\tvoid fsrDestroyIntermediate(size_t index);
\tvoid fsrDestroyResources();
\tvoid DrawBackbufferQuadFSR(LatteTextureView* texView, RendererOutputShader* easuShader, sint32 imageX, sint32 imageY, sint32 imageWidth, sint32 imageHeight, bool padView);

\tVkQueue m_graphicsQueue, m_presentQueue;''',
    'Vulkan FSR resources',
)

replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp',
    '''\tSubmitCommandBuffer();
\tWaitDeviceIdle();
\t// stop compilation threads''',
    '''\tSubmitCommandBuffer();
\tWaitDeviceIdle();
\tfsrDestroyResources();
\t// stop compilation threads''',
    'Vulkan FSR shutdown cleanup',
)

replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp',
    '''VkPipeline VulkanRenderer::backbufferBlit_createGraphicsPipeline(VkDescriptorSetLayout descriptorLayout, bool padView, RendererOutputShader* shader)
{
\tauto& chainInfo = GetChainInfo(!padView);''',
    '''VkPipeline VulkanRenderer::backbufferBlit_createGraphicsPipeline(VkDescriptorSetLayout descriptorLayout, bool padView, RendererOutputShader* shader, VkRenderPass overrideRenderPass)
{
\tauto& chainInfo = GetChainInfo(!padView);
\tconst VkRenderPass targetRenderPass = overrideRenderPass != VK_NULL_HANDLE ? overrideRenderPass : chainInfo.m_swapchainRenderPass;''',
    'backbuffer pipeline override renderpass implementation',
)

replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp',
    '''\thash += ((uint64)padView) << 1;

\tconst auto it = m_backbufferBlitPipelineCache.find(hash);''',
    '''\thash += ((uint64)padView) << 1;
\thash ^= ((uint64)targetRenderPass * 0x9E3779B185EBCA87ull);

\tconst auto it = m_backbufferBlitPipelineCache.find(hash);''',
    'backbuffer pipeline renderpass hash',
)

replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp',
    '\tpipelineInfo.renderPass = chainInfo.m_swapchainRenderPass;',
    '\tpipelineInfo.renderPass = targetRenderPass;',
    'backbuffer pipeline target renderpass',
)

fsr_vk_helpers = r'''
void VulkanRenderer::fsrDestroyIntermediate(size_t index)
{
    auto& resource = m_fsrIntermediate[index];

    if (resource.framebuffer != VK_NULL_HANDLE)
    {
        vkDestroyFramebuffer(m_logicalDevice, resource.framebuffer, nullptr);
        resource.framebuffer = VK_NULL_HANDLE;
    }
    if (resource.view != VK_NULL_HANDLE)
    {
        vkDestroyImageView(m_logicalDevice, resource.view, nullptr);
        resource.view = VK_NULL_HANDLE;
    }
    if (resource.image != VK_NULL_HANDLE)
    {
        vkDestroyImage(m_logicalDevice, resource.image, nullptr);
        resource.image = VK_NULL_HANDLE;
    }
    if (resource.allocation)
    {
        memoryManager->imageMemoryFree(resource.allocation);
        resource.allocation = nullptr;
    }

    resource.width = 0;
    resource.height = 0;
}

void VulkanRenderer::fsrDestroyResources()
{
    for (size_t i = 0; i < m_fsrIntermediate.size(); ++i)
        fsrDestroyIntermediate(i);

    for (auto& resource : m_fsrIntermediate)
    {
        if (resource.descriptorSet != VK_NULL_HANDLE && m_descriptorPool != VK_NULL_HANDLE)
        {
            vkFreeDescriptorSets(m_logicalDevice, m_descriptorPool, 1, &resource.descriptorSet);
            resource.descriptorSet = VK_NULL_HANDLE;
        }
    }

    if (m_fsrSampler != VK_NULL_HANDLE)
    {
        vkDestroySampler(m_logicalDevice, m_fsrSampler, nullptr);
        m_fsrSampler = VK_NULL_HANDLE;
    }
    if (m_fsrRenderPass != VK_NULL_HANDLE)
    {
        vkDestroyRenderPass(m_logicalDevice, m_fsrRenderPass, nullptr);
        m_fsrRenderPass = VK_NULL_HANDLE;
    }
}

void VulkanRenderer::fsrEnsureIntermediate(bool padView, uint32 width, uint32 height)
{
    if (width == 0 || height == 0)
        return;

    const size_t resourceIndex = padView ? 1 : 0;
    auto& resource = m_fsrIntermediate[resourceIndex];

    if (resource.image != VK_NULL_HANDLE && resource.width == width && resource.height == height)
        return;

    if (resource.image != VK_NULL_HANDLE)
    {
        // Resize is rare and old frames may still sample this image.
        WaitDeviceIdle();
        fsrDestroyIntermediate(resourceIndex);
    }

    constexpr VkFormat kFSRIntermediateFormat = VK_FORMAT_R16G16B16A16_SFLOAT;

    if (m_fsrRenderPass == VK_NULL_HANDLE)
    {
        VkAttachmentDescription colorAttachment{};
        colorAttachment.format = kFSRIntermediateFormat;
        colorAttachment.samples = VK_SAMPLE_COUNT_1_BIT;
        colorAttachment.loadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
        colorAttachment.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
        colorAttachment.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
        colorAttachment.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
        colorAttachment.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
        colorAttachment.finalLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;

        VkAttachmentReference colorReference{};
        colorReference.attachment = 0;
        colorReference.layout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;

        VkSubpassDescription subpass{};
        subpass.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS;
        subpass.colorAttachmentCount = 1;
        subpass.pColorAttachments = &colorReference;

        VkSubpassDependency dependencies[2]{};
        dependencies[0].srcSubpass = VK_SUBPASS_EXTERNAL;
        dependencies[0].dstSubpass = 0;
        dependencies[0].srcStageMask = VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT | VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
        dependencies[0].dstStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
        dependencies[0].srcAccessMask = VK_ACCESS_SHADER_READ_BIT;
        dependencies[0].dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
        dependencies[0].dependencyFlags = VK_DEPENDENCY_BY_REGION_BIT;

        dependencies[1].srcSubpass = 0;
        dependencies[1].dstSubpass = VK_SUBPASS_EXTERNAL;
        dependencies[1].srcStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
        dependencies[1].dstStageMask = VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT;
        dependencies[1].srcAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
        dependencies[1].dstAccessMask = VK_ACCESS_SHADER_READ_BIT;
        dependencies[1].dependencyFlags = VK_DEPENDENCY_BY_REGION_BIT;

        VkRenderPassCreateInfo renderPassInfo{};
        renderPassInfo.sType = VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO;
        renderPassInfo.attachmentCount = 1;
        renderPassInfo.pAttachments = &colorAttachment;
        renderPassInfo.subpassCount = 1;
        renderPassInfo.pSubpasses = &subpass;
        renderPassInfo.dependencyCount = std::size(dependencies);
        renderPassInfo.pDependencies = dependencies;

        if (vkCreateRenderPass(m_logicalDevice, &renderPassInfo, nullptr, &m_fsrRenderPass) != VK_SUCCESS)
            UnrecoverableError("Failed to create FSR intermediate render pass");
    }

    if (m_fsrSampler == VK_NULL_HANDLE)
    {
        VkSamplerCreateInfo samplerInfo{};
        samplerInfo.sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO;
        samplerInfo.magFilter = VK_FILTER_LINEAR;
        samplerInfo.minFilter = VK_FILTER_LINEAR;
        samplerInfo.mipmapMode = VK_SAMPLER_MIPMAP_MODE_NEAREST;
        samplerInfo.addressModeU = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
        samplerInfo.addressModeV = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
        samplerInfo.addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
        samplerInfo.minLod = 0.0f;
        samplerInfo.maxLod = 0.0f;
        samplerInfo.maxAnisotropy = 1.0f;
        samplerInfo.anisotropyEnable = VK_FALSE;
        samplerInfo.compareEnable = VK_FALSE;
        samplerInfo.borderColor = VK_BORDER_COLOR_FLOAT_OPAQUE_BLACK;

        if (vkCreateSampler(m_logicalDevice, &samplerInfo, nullptr, &m_fsrSampler) != VK_SUCCESS)
            UnrecoverableError("Failed to create FSR intermediate sampler");
    }

    VkImageCreateInfo imageInfo{};
    imageInfo.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO;
    imageInfo.imageType = VK_IMAGE_TYPE_2D;
    imageInfo.format = kFSRIntermediateFormat;
    imageInfo.extent = { width, height, 1 };
    imageInfo.mipLevels = 1;
    imageInfo.arrayLayers = 1;
    imageInfo.samples = VK_SAMPLE_COUNT_1_BIT;
    imageInfo.tiling = VK_IMAGE_TILING_OPTIMAL;
    imageInfo.usage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_SAMPLED_BIT;
    imageInfo.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
    imageInfo.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;

    if (vkCreateImage(m_logicalDevice, &imageInfo, nullptr, &resource.image) != VK_SUCCESS)
        UnrecoverableError("Failed to create FSR intermediate image");
    resource.allocation = memoryManager->imageMemoryAllocate(resource.image);

    VkImageViewCreateInfo viewInfo{};
    viewInfo.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
    viewInfo.image = resource.image;
    viewInfo.viewType = VK_IMAGE_VIEW_TYPE_2D;
    viewInfo.format = kFSRIntermediateFormat;
    viewInfo.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    viewInfo.subresourceRange.baseMipLevel = 0;
    viewInfo.subresourceRange.levelCount = 1;
    viewInfo.subresourceRange.baseArrayLayer = 0;
    viewInfo.subresourceRange.layerCount = 1;

    if (vkCreateImageView(m_logicalDevice, &viewInfo, nullptr, &resource.view) != VK_SUCCESS)
        UnrecoverableError("Failed to create FSR intermediate image view");

    VkFramebufferCreateInfo framebufferInfo{};
    framebufferInfo.sType = VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO;
    framebufferInfo.renderPass = m_fsrRenderPass;
    framebufferInfo.attachmentCount = 1;
    framebufferInfo.pAttachments = &resource.view;
    framebufferInfo.width = width;
    framebufferInfo.height = height;
    framebufferInfo.layers = 1;

    if (vkCreateFramebuffer(m_logicalDevice, &framebufferInfo, nullptr, &resource.framebuffer) != VK_SUCCESS)
        UnrecoverableError("Failed to create FSR intermediate framebuffer");

    if (resource.descriptorSet == VK_NULL_HANDLE)
    {
        VkDescriptorSetAllocateInfo allocInfo{};
        allocInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
        allocInfo.descriptorPool = m_descriptorPool;
        allocInfo.descriptorSetCount = 1;
        allocInfo.pSetLayouts = &m_swapchainDescriptorSetLayout;

        if (vkAllocateDescriptorSets(m_logicalDevice, &allocInfo, &resource.descriptorSet) != VK_SUCCESS)
            UnrecoverableError("Failed to allocate FSR intermediate descriptor set");
        performanceMonitor.vk.numDescriptorSets.increment();
    }

    VkDescriptorImageInfo imageDescriptor{};
    imageDescriptor.sampler = m_fsrSampler;
    imageDescriptor.imageView = resource.view;
    imageDescriptor.imageLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;

    VkDescriptorBufferInfo uniformDescriptor{};
    uniformDescriptor.buffer = m_uniformVarBuffer;
    uniformDescriptor.offset = 0;
    uniformDescriptor.range = sizeof(RendererOutputShader::OutputUniformVariables);

    VkWriteDescriptorSet descriptorWrites[2]{};
    descriptorWrites[0].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    descriptorWrites[0].dstSet = resource.descriptorSet;
    descriptorWrites[0].dstBinding = 0;
    descriptorWrites[0].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    descriptorWrites[0].descriptorCount = 1;
    descriptorWrites[0].pImageInfo = &imageDescriptor;

    descriptorWrites[1].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    descriptorWrites[1].dstSet = resource.descriptorSet;
    descriptorWrites[1].dstBinding = 1;
    descriptorWrites[1].descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC;
    descriptorWrites[1].descriptorCount = 1;
    descriptorWrites[1].pBufferInfo = &uniformDescriptor;

    vkUpdateDescriptorSets(m_logicalDevice, std::size(descriptorWrites), descriptorWrites, 0, nullptr);
    performanceMonitor.vk.numDescriptorSamplerTextures.increment();

    resource.width = width;
    resource.height = height;
}

void VulkanRenderer::DrawBackbufferQuadFSR(LatteTextureView* texView, RendererOutputShader* easuShader, sint32 imageX, sint32 imageY, sint32 imageWidth, sint32 imageHeight, bool padView)
{
    if (imageWidth <= 0 || imageHeight <= 0)
        return;

    auto& chainInfo = GetChainInfo(!padView);
    auto* texViewVk = static_cast<LatteTextureViewVk*>(texView);
    const size_t resourceIndex = padView ? 1 : 0;

    fsrEnsureIntermediate(padView, (uint32)imageWidth, (uint32)imageHeight);
    auto& resource = m_fsrIntermediate[resourceIndex];

    // Make the emulated TV/DRC texture visible to the EASU fragment shader.
    VkMemoryBarrier inputBarrier{};
    inputBarrier.sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER;
    inputBarrier.srcAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT | VK_ACCESS_TRANSFER_WRITE_BIT;
    inputBarrier.dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_READ_BIT | VK_ACCESS_SHADER_READ_BIT;
    const VkPipelineStageFlags inputSrcStages = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT | VK_PIPELINE_STAGE_TRANSFER_BIT;
    const VkPipelineStageFlags inputDstStages = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT | VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT;
    vkCmdPipelineBarrier(m_state.currentCommandBuffer, inputSrcStages, inputDstStages, 0, 1, &inputBarrier, 0, nullptr, 0, nullptr);

    const auto easuPipeline = backbufferBlit_createGraphicsPipeline(m_swapchainDescriptorSetLayout, padView, easuShader, m_fsrRenderPass);
    const auto sourceDescriptor = backbufferBlit_createDescriptorSet(m_swapchainDescriptorSetLayout, texViewVk, true);

    VkRenderPassBeginInfo easuPassInfo{};
    easuPassInfo.sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO;
    easuPassInfo.renderPass = m_fsrRenderPass;
    easuPassInfo.framebuffer = resource.framebuffer;
    easuPassInfo.renderArea.offset = { 0, 0 };
    easuPassInfo.renderArea.extent = { (uint32)imageWidth, (uint32)imageHeight };

    VkViewport easuViewport{};
    easuViewport.x = 0.0f;
    easuViewport.y = 0.0f;
    easuViewport.width = (float)imageWidth;
    easuViewport.height = (float)imageHeight;
    easuViewport.minDepth = 0.0f;
    easuViewport.maxDepth = 1.0f;

    VkRect2D easuScissor{};
    easuScissor.offset = { 0, 0 };
    easuScissor.extent = { (uint32)imageWidth, (uint32)imageHeight };

    vkCmdSetViewport(m_state.currentCommandBuffer, 0, 1, &easuViewport);
    vkCmdSetScissor(m_state.currentCommandBuffer, 0, 1, &easuScissor);
    vkCmdBeginRenderPass(m_state.currentCommandBuffer, &easuPassInfo, VK_SUBPASS_CONTENTS_INLINE);
    vkCmdBindPipeline(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, easuPipeline);
    m_state.currentPipeline = easuPipeline;

    auto easuUniforms = easuShader->FillUniformBlockBuffer(*texView, { imageWidth, imageHeight }, padView);
    // The intermediate must remain in the game's linear output space. Gamma and
    // sRGB conversion are applied once, after RCAS, on the final swapchain pass.
    easuUniforms.applySRGBEncoding = 0;
    easuUniforms.targetGamma = 1.0f;
    easuUniforms.displayGamma = 1.0f;

    auto easuUniformOffset = uniformData_uploadUniformDataBufferGetOffset({ (uint8*)&easuUniforms, sizeof(easuUniforms) });
    vkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, m_pipelineLayout, 0, 1, &sourceDescriptor, 1, &easuUniformOffset);
    vkCmdDraw(m_state.currentCommandBuffer, 6, 1, 0, 0);
    vkCmdEndRenderPass(m_state.currentCommandBuffer);

    // The render pass transitions the FP16 image to SHADER_READ_ONLY_OPTIMAL;
    // make the color writes explicitly visible before RCAS samples them.
    VkMemoryBarrier rcasBarrier{};
    rcasBarrier.sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER;
    rcasBarrier.srcAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
    rcasBarrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;
    vkCmdPipelineBarrier(
        m_state.currentCommandBuffer,
        VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,
        VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,
        VK_DEPENDENCY_BY_REGION_BIT,
        1, &rcasBarrier, 0, nullptr, 0, nullptr);

    const auto rcasPipeline = backbufferBlit_createGraphicsPipeline(
        m_swapchainDescriptorSetLayout, padView, RendererOutputShader::s_fsr_rcas_shader);

    VkRenderPassBeginInfo finalPassInfo{};
    finalPassInfo.sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO;
    finalPassInfo.renderPass = chainInfo.m_swapchainRenderPass;
    finalPassInfo.framebuffer = chainInfo.m_swapchainFramebuffers[chainInfo.swapchainImageIndex];
    finalPassInfo.renderArea.offset = { 0, 0 };
    finalPassInfo.renderArea.extent = chainInfo.getExtent();

    VkViewport finalViewport{};
    finalViewport.x = (float)imageX;
    finalViewport.y = (float)imageY;
    finalViewport.width = (float)imageWidth;
    finalViewport.height = (float)imageHeight;
    finalViewport.minDepth = 0.0f;
    finalViewport.maxDepth = 1.0f;

    VkRect2D finalScissor{};
    finalScissor.extent = chainInfo.getExtent();

    vkCmdSetViewport(m_state.currentCommandBuffer, 0, 1, &finalViewport);
    vkCmdSetScissor(m_state.currentCommandBuffer, 0, 1, &finalScissor);
    vkCmdBeginRenderPass(m_state.currentCommandBuffer, &finalPassInfo, VK_SUBPASS_CONTENTS_INLINE);
    vkCmdBindPipeline(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, rcasPipeline);
    m_state.currentPipeline = rcasPipeline;

    auto rcasUniforms = easuShader->FillUniformBlockBuffer(*texView, { imageWidth, imageHeight }, padView);
    rcasUniforms.textureSrcResolution = { (float)imageWidth, (float)imageHeight };
    rcasUniforms.nativeResolution = { (float)imageWidth, (float)imageHeight };
    rcasUniforms.outputResolution = { (float)imageWidth, (float)imageHeight };

    auto rcasUniformOffset = uniformData_uploadUniformDataBufferGetOffset({ (uint8*)&rcasUniforms, sizeof(rcasUniforms) });
    vkCmdBindDescriptorSets(m_state.currentCommandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, m_pipelineLayout, 0, 1, &resource.descriptorSet, 1, &rcasUniformOffset);
    vkCmdDraw(m_state.currentCommandBuffer, 6, 1, 0, 0);
    vkCmdEndRenderPass(m_state.currentCommandBuffer);

    vkCmdSetViewport(m_state.currentCommandBuffer, 0, 1, &m_state.currentViewport);
    chainInfo.hasDefinedSwapchainImage = true;

    static bool s_fsrPathLogged = false;
    if (!s_fsrPathLogged)
    {
        cemuLog_log(LogType::Force, "[FSR1] Vulkan EASU + RCAS active · RCAS setting {}", GetConfig().fsr_sharpness.GetValue());
        s_fsrPathLogged = true;
    }
}

'''.strip('\n')

replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp',
    'void VulkanRenderer::DrawBackbufferQuad(LatteTextureView* texView, RendererOutputShader* shader, bool useLinearTexFilter, sint32 imageX, sint32 imageY, sint32 imageWidth, sint32 imageHeight, bool padView, bool clearBackground)\n{',
    fsr_vk_helpers + '\n\nvoid VulkanRenderer::DrawBackbufferQuad(LatteTextureView* texView, RendererOutputShader* shader, bool useLinearTexFilter, sint32 imageX, sint32 imageY, sint32 imageWidth, sint32 imageHeight, bool padView, bool clearBackground)\n{',
    'Vulkan FSR two-pass helpers',
)

# The workflow's known-good pre-e834 step has already inserted the clear call
# here before this script runs. Branch only the FSR shader; all other paths
# continue through the unchanged Cemu backbuffer code.
replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp',
    '''\tif (clearBackground)
\t\tClearColorbuffer(padView);

\t// barrier for input texture''',
    '''\tif (clearBackground)
\t\tClearColorbuffer(padView);

\tif (shader == RendererOutputShader::s_fsr_easu_shader || shader == RendererOutputShader::s_fsr_easu_shader_ud)
\t{
\t\tDrawBackbufferQuadFSR(texView, shader, imageX, imageY, imageWidth, imageHeight, padView);
\t\treturn;
\t}

\t// barrier for input texture''',
    'route Vulkan FSR through two-pass path',
)

subprocess.run([
    'git', 'diff', '--check', '--',
    'src/config/CemuConfig.h',
    'src/config/CemuConfig.cpp',
    'src/gui/wxgui/GeneralSettings2.h',
    'src/gui/wxgui/GeneralSettings2.cpp',
    'src/Cafe/HW/Latte/Core/LatteRenderTarget.cpp',
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.h',
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.cpp',
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h',
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp',
], check=True)

print('[fsr-full] AMD FidelityFX FSR 1 completed for Vulkan')
print('[fsr-full] Vulkan path: EASU -> RGBA16F intermediate -> RCAS -> present')
print('[fsr-full] Graphics UI: AMD FidelityFX FSR + RCAS sharpness 0..200 (default 25)')
print('[fsr-full] Sharpness is persisted as Graphic/FSRSharpness')
print('[fsr-full] Non-FSR backbuffer path remains unchanged')
