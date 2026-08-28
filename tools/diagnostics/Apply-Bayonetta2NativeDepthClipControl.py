from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{path}: expected anchor once, found {count}: {old[:120]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8', newline='')

# 1) Decompiler option: capability/experiment intent only. Primitive filtering stays in GLSL emission.
replace_once(
    'src/Cafe/HW/Latte/LegacyShaderDecompiler/LatteDecompiler.h',
    '\t// Vulkan-specific\n\tbool useTFViaSSBO{ false };\n\tstruct\n',
    '\t// Vulkan-specific\n\tbool useTFViaSSBO{ false };\n\tbool useVulkanNativeNegativeOneToOne{ false }; // Bayonetta 2 A/B: VK_EXT_depth_clip_control\n\tstruct\n'
)

# 2) When the experiment is active, preserve the Wii U/OpenGL-style -1..1 clip Z natively.
replace_once(
    'src/Cafe/HW/Latte/LegacyShaderDecompiler/LatteDecompilerEmitGLSLHeader.hpp',
    '''\t\t\tif (decompilerContext->contextRegistersNew->PA_CL_CLIP_CNTL.get_DX_CLIP_SPACE_DEF())\n\t\t\t{\n\t\t\t\tsrc->add("#define SET_POSITION(_v) gl_Position = _v" _CRLF);\n\t\t\t}\n\t\t\telse\n''',
    '''\t\t\tconst bool useNativeNegativeOneToOne =\n\t\t\t\tdecompilerContext->options->useVulkanNativeNegativeOneToOne &&\n\t\t\t\tdecompilerContext->shaderType == LatteConst::ShaderType::Vertex &&\n\t\t\t\t!decompilerContext->options->usesGeometryShader &&\n\t\t\t\tdecompilerContext->contextRegistersNew->VGT_PRIMITIVE_TYPE.get_PRIMITIVE_MODE() != Latte::LATTE_VGT_PRIMITIVE_TYPE::E_PRIMITIVE_TYPE::RECTS;\n\n\t\t\tif (decompilerContext->contextRegistersNew->PA_CL_CLIP_CNTL.get_DX_CLIP_SPACE_DEF() || useNativeNegativeOneToOne)\n\t\t\t{\n\t\t\t\tsrc->add("#define SET_POSITION(_v) gl_Position = _v" _CRLF);\n\t\t\t}\n\t\t\telse\n'''
)

# 3) Pass Vulkan support/title/no-GS intent into the decompiler.
replace_once(
    'src/Cafe/HW/Latte/Core/LatteShader.cpp',
    '#include "Cafe/GameProfile/GameProfile.h"\n',
    '#include "Cafe/GameProfile/GameProfile.h"\n#include "Cafe/CafeSystem.h"\n'
)
replace_once(
    'src/Cafe/HW/Latte/Core/LatteShader.cpp',
    '''\toptions.usesGeometryShader = geometryShaderEnabled;\n\toptions.spirvInstrinsics.hasRoundingModeRTEFloat32 = false;\n\toptions.useTFViaSSBO = g_renderer->UseTFViaSSBO();\n#ifdef ENABLE_VULKAN\n\tif (g_renderer->GetType() == RendererAPI::Vulkan)\n\t{\n\t\toptions.spirvInstrinsics.hasRoundingModeRTEFloat32 = VulkanRenderer::GetInstance()->HasSPRIVRoundingModeRTE32();\n\t}\n#endif\n''',
    '''\toptions.usesGeometryShader = geometryShaderEnabled;\n\toptions.spirvInstrinsics.hasRoundingModeRTEFloat32 = false;\n\toptions.useTFViaSSBO = g_renderer->UseTFViaSSBO();\n\toptions.useVulkanNativeNegativeOneToOne = false;\n#ifdef ENABLE_VULKAN\n\tif (g_renderer->GetType() == RendererAPI::Vulkan)\n\t{\n\t\tauto* vkRenderer = VulkanRenderer::GetInstance();\n\t\toptions.spirvInstrinsics.hasRoundingModeRTEFloat32 = vkRenderer->HasSPRIVRoundingModeRTE32();\n\n\t\tconst uint64 titleId = CafeSystem::GetForegroundTitleId();\n\t\tconst bool isBayonetta2 =\n\t\t\ttitleId == 0x0005000010172600ULL ||\n\t\t\ttitleId == 0x0005000010172700ULL ||\n\t\t\ttitleId == 0x000500001011B900ULL;\n\t\toptions.useVulkanNativeNegativeOneToOne =\n\t\t\tshaderType == LatteConst::ShaderType::Vertex &&\n\t\t\t!geometryShaderEnabled && isBayonetta2 && vkRenderer->SupportsDepthClipControl();\n\t}\n#endif\n'''
)

# 4) Vulkan feature control and public capability query.
replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h',
    '\t\t\tbool depth_clip_enable = false; // VK_EXT_depth_clip_enable\n',
    '\t\t\tbool depth_clip_enable = false; // VK_EXT_depth_clip_enable\n\t\t\tbool depth_clip_control = false; // VK_EXT_depth_clip_control\n'
)
replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h',
    '\tstatic VulkanRenderer* GetInstance();\n\n\tvoid UnrecoverableError',
    '\tstatic VulkanRenderer* GetInstance();\n\tbool SupportsDepthClipControl() const { return m_featureControl.deviceExtensions.depth_clip_control; }\n\n\tvoid UnrecoverableError'
)

# 5) Detect/query/enable VK_EXT_depth_clip_control on the logical device.
replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp',
    '\tVK_EXT_DEPTH_CLIP_ENABLE_EXTENSION_NAME,\n\tVK_EXT_PIPELINE_ROBUSTNESS_EXTENSION_NAME,\n',
    '''\tVK_EXT_DEPTH_CLIP_ENABLE_EXTENSION_NAME,\n#ifdef VK_EXT_depth_clip_control\n\tVK_EXT_DEPTH_CLIP_CONTROL_EXTENSION_NAME,\n#endif\n\tVK_EXT_PIPELINE_ROBUSTNESS_EXTENSION_NAME,\n'''
)
replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp',
    '''\tVkPhysicalDeviceAttachmentFeedbackLoopLayoutFeaturesEXT attachmentFeedbackLoopLayoutFeature{};\n\tif (m_featureControl.deviceExtensions.attachment_feedback_loop_layout)\n\t{\n\t\tattachmentFeedbackLoopLayoutFeature.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_ATTACHMENT_FEEDBACK_LOOP_LAYOUT_FEATURES_EXT;\n\t\tattachmentFeedbackLoopLayoutFeature.pNext = prevStruct;\n\t\tprevStruct = &attachmentFeedbackLoopLayoutFeature;\n\t}\n\n\tVkPhysicalDeviceFeatures2 physicalDeviceFeatures2{};\n''',
    '''\tVkPhysicalDeviceAttachmentFeedbackLoopLayoutFeaturesEXT attachmentFeedbackLoopLayoutFeature{};\n\tif (m_featureControl.deviceExtensions.attachment_feedback_loop_layout)\n\t{\n\t\tattachmentFeedbackLoopLayoutFeature.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_ATTACHMENT_FEEDBACK_LOOP_LAYOUT_FEATURES_EXT;\n\t\tattachmentFeedbackLoopLayoutFeature.pNext = prevStruct;\n\t\tprevStruct = &attachmentFeedbackLoopLayoutFeature;\n\t}\n\n#ifdef VK_EXT_depth_clip_control\n\tVkPhysicalDeviceDepthClipControlFeaturesEXT depthClipControlFeature{};\n\tif (m_featureControl.deviceExtensions.depth_clip_control)\n\t{\n\t\tdepthClipControlFeature.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DEPTH_CLIP_CONTROL_FEATURES_EXT;\n\t\tdepthClipControlFeature.pNext = prevStruct;\n\t\tprevStruct = &depthClipControlFeature;\n\t}\n#endif\n\n\tVkPhysicalDeviceFeatures2 physicalDeviceFeatures2{};\n'''
)
replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp',
    '''\tif (!m_featureControl.deviceExtensions.depth_clip_enable)\n\t{\n\t\tcemuLog_log(LogType::Force, "VK_EXT_depth_clip_enable not supported");\n\t}\n\tif (m_featureControl.deviceExtensions.pipeline_robustness)\n''',
    '''\tif (!m_featureControl.deviceExtensions.depth_clip_enable)\n\t{\n\t\tcemuLog_log(LogType::Force, "VK_EXT_depth_clip_enable not supported");\n\t}\n#ifdef VK_EXT_depth_clip_control\n\tif (m_featureControl.deviceExtensions.depth_clip_control)\n\t\tm_featureControl.deviceExtensions.depth_clip_control = depthClipControlFeature.depthClipControl == VK_TRUE;\n\tcemuLog_log(LogType::Force, "[BAYO2_NATIVE_DEPTH_CLIP] VK_EXT_depth_clip_control: {}",\n\t\tm_featureControl.deviceExtensions.depth_clip_control ? "supported" : "unsupported");\n#else\n\tm_featureControl.deviceExtensions.depth_clip_control = false;\n\tcemuLog_log(LogType::Force, "[BAYO2_NATIVE_DEPTH_CLIP] VK_EXT_depth_clip_control: unavailable in Vulkan headers");\n#endif\n\tif (m_featureControl.deviceExtensions.pipeline_robustness)\n'''
)
replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp',
    '''\tif (m_featureControl.deviceExtensions.shader_float_controls)\n\t\tused_extensions.emplace_back(VK_KHR_SHADER_FLOAT_CONTROLS_EXTENSION_NAME);\n\tif (m_featureControl.deviceExtensions.depth_clip_enable)\n''',
    '''\tif (m_featureControl.deviceExtensions.shader_float_controls)\n\t\tused_extensions.emplace_back(VK_KHR_SHADER_FLOAT_CONTROLS_EXTENSION_NAME);\n#ifdef VK_EXT_depth_clip_control\n\tif (m_featureControl.deviceExtensions.depth_clip_control)\n\t\tused_extensions.emplace_back(VK_EXT_DEPTH_CLIP_CONTROL_EXTENSION_NAME);\n#endif\n\tif (m_featureControl.deviceExtensions.depth_clip_enable)\n'''
)
replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp',
    '''\tinfo.deviceExtensions.shader_float_controls = isExtensionAvailable(VK_KHR_SHADER_FLOAT_CONTROLS_EXTENSION_NAME);\n\tinfo.deviceExtensions.dynamic_rendering = false; // isExtensionAvailable(VK_KHR_DYNAMIC_RENDERING_EXTENSION_NAME);\n\tinfo.deviceExtensions.depth_clip_enable = isExtensionAvailable(VK_EXT_DEPTH_CLIP_ENABLE_EXTENSION_NAME);\n''',
    '''\tinfo.deviceExtensions.shader_float_controls = isExtensionAvailable(VK_KHR_SHADER_FLOAT_CONTROLS_EXTENSION_NAME);\n\tinfo.deviceExtensions.dynamic_rendering = false; // isExtensionAvailable(VK_KHR_DYNAMIC_RENDERING_EXTENSION_NAME);\n#ifdef VK_EXT_depth_clip_control\n\tinfo.deviceExtensions.depth_clip_control = isExtensionAvailable(VK_EXT_DEPTH_CLIP_CONTROL_EXTENSION_NAME);\n#else\n\tinfo.deviceExtensions.depth_clip_control = false;\n#endif\n\tinfo.deviceExtensions.depth_clip_enable = isExtensionAvailable(VK_EXT_DEPTH_CLIP_ENABLE_EXTENSION_NAME);\n'''
)
replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp',
    '''\t// enable attachment feedback loop layout + dynamic state if both are supported\n\tVkPhysicalDeviceAttachmentFeedbackLoopLayoutFeaturesEXT attachmentFeedbackLoopLayoutFeature{};\n''',
    '''#ifdef VK_EXT_depth_clip_control\n\t// Enable native OpenGL-style [-1, 1] NDC depth range support for the Bayonetta 2 A/B.\n\tVkPhysicalDeviceDepthClipControlFeaturesEXT depthClipControlFeature{};\n\tif (m_featureControl.deviceExtensions.depth_clip_control)\n\t{\n\t\tdepthClipControlFeature.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DEPTH_CLIP_CONTROL_FEATURES_EXT;\n\t\tdepthClipControlFeature.pNext = deviceExtensionFeatures;\n\t\tdeviceExtensionFeatures = &depthClipControlFeature;\n\t\tdepthClipControlFeature.depthClipControl = VK_TRUE;\n\t}\n#endif\n\n\t// enable attachment feedback loop layout + dynamic state if both are supported\n\tVkPhysicalDeviceAttachmentFeedbackLoopLayoutFeaturesEXT attachmentFeedbackLoopLayoutFeature{};\n'''
)

# 6) Pipeline viewport pNext and Bayonetta 2/no-GS/non-RECT activation.
replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h',
    '\tvoid InitViewportState();\n',
    '\tvoid InitViewportState(bool useNativeNegativeOneToOne);\n'
)
replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h',
    '\t/* viewport state */\n\tVkPipelineViewportStateCreateInfo viewportState{};\n',
    '''\t/* viewport state */\n\tVkPipelineViewportStateCreateInfo viewportState{};\n#ifdef VK_EXT_depth_clip_control\n\tVkPipelineViewportDepthClipControlCreateInfoEXT viewportDepthClipControl{};\n#endif\n'''
)
replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp',
    '#include "Cafe/OS/libs/gx2/GX2.h"\n',
    '#include "Cafe/OS/libs/gx2/GX2.h"\n#include "Cafe/CafeSystem.h"\n'
)
replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp',
    '''void PipelineCompiler::InitViewportState()\n{\n\tviewportState.sType = VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO;\n\tviewportState.viewportCount = 1;\n\tviewportState.scissorCount = 1;\n}\n''',
    '''void PipelineCompiler::InitViewportState(bool useNativeNegativeOneToOne)\n{\n\tviewportState.sType = VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO;\n\tviewportState.viewportCount = 1;\n\tviewportState.scissorCount = 1;\n\n#ifdef VK_EXT_depth_clip_control\n\tif (useNativeNegativeOneToOne)\n\t{\n\t\tviewportDepthClipControl.sType = VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_DEPTH_CLIP_CONTROL_CREATE_INFO_EXT;\n\t\tviewportDepthClipControl.pNext = nullptr;\n\t\tviewportDepthClipControl.negativeOneToOne = VK_TRUE;\n\t\tviewportState.pNext = &viewportDepthClipControl;\n\n\t\tstatic std::atomic_bool s_loggedNativeNegativeOneToOne{ false };\n\t\tif (!s_loggedNativeNegativeOneToOne.exchange(true))\n\t\t\tcemuLog_log(LogType::Force, "[BAYO2_NATIVE_DEPTH_CLIP] negativeOneToOne=1 shaderZRemap=0");\n\t}\n#else\n\t(void)useNativeNegativeOneToOne;\n#endif\n}\n'''
)
replace_once(
    'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp',
    '''\tpipelineInfo->primitiveMode = primitiveMode;\n\tInitVertexInputState(latteRegister, pipelineInfo->vertexShader, pipelineInfo->fetchShader);\n\tInitInputAssemblyState(primitiveMode);\n\tInitViewportState();\n\tbool usesDepthBias = false;\n''',
    '''\tpipelineInfo->primitiveMode = primitiveMode;\n\tInitVertexInputState(latteRegister, pipelineInfo->vertexShader, pipelineInfo->fetchShader);\n\tInitInputAssemblyState(primitiveMode);\n\n\tconst uint64 titleId = CafeSystem::GetForegroundTitleId();\n\tconst bool isBayonetta2 =\n\t\ttitleId == 0x0005000010172600ULL ||\n\t\ttitleId == 0x0005000010172700ULL ||\n\t\ttitleId == 0x000500001011B900ULL;\n\tconst bool useNativeNegativeOneToOne =\n\t\tisBayonetta2 && pipelineInfo->geometryShader == nullptr && !isPrimitiveRect &&\n\t\t!latteRegister.PA_CL_CLIP_CNTL.get_DX_CLIP_SPACE_DEF() &&\n\t\tvkRenderer->SupportsDepthClipControl();\n\tInitViewportState(useNativeNegativeOneToOne);\n\tbool usesDepthBias = false;\n'''
)

print('Applied Bayonetta 2 native negativeOneToOne depth-clip-control experiment patch')
