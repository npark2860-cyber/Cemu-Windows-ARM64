from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# Make six previously grey shader/cache diagnostics selectable only after
# concrete runtime consumers are installed.
header_path = Path("src/diagnostics/RuntimeDiagnostics.h")
header = header_path.read_text(encoding="utf-8")
header = replace_once(
    header,
    '''    case Flag::ShaderGS:\n    case Flag::ShaderAuxHash:\n\n    // Render-target / synchronization diagnostics\n''',
    '''    case Flag::ShaderGS:\n    case Flag::ShaderAuxHash:\n    case Flag::PipelineCacheMismatch:\n    case Flag::ShaderCreation:\n    case Flag::GLSLCompileFailure:\n    case Flag::SPIRVCompileFailure:\n    case Flag::DumpFailedShader:\n    case Flag::DumpEveryShader:\n\n    // Render-target / synchronization diagnostics\n''',
    "shader/cache IsImplemented cases",
)
header_path.write_text(header, encoding="utf-8", newline="\n")

shader_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp")
shader = shader_path.read_text(encoding="utf-8")

if '#include "diagnostics/RuntimeDiagnostics.h"\n' not in shader:
    shader = replace_once(
        shader,
        '#include "Cemu/FileCache/FileCache.h"\n',
        '#include "Cemu/FileCache/FileCache.h"\n#include "diagnostics/RuntimeDiagnostics.h"\n',
        "RendererShaderVk diagnostics include",
    )

if '#include <filesystem>\n' not in shader:
    shader = replace_once(
        shader,
        '#include <glslang/Public/ShaderLang.h>\n',
        '#include <filesystem>\n#include <fstream>\n#include <string_view>\n#include <glslang/Public/ShaderLang.h>\n',
        "shader dump standard includes",
    )

helper_anchor = '''extern std::atomic_int g_compiled_shaders_total;\nextern std::atomic_int g_compiled_shaders_async;\n\n'''
helper_code = '''extern std::atomic_int g_compiled_shaders_total;\nextern std::atomic_int g_compiled_shaders_async;\n\nstatic const char* DiagnosticShaderStageName(RendererShader::ShaderType type)\n{\n\tswitch (type)\n\t{\n\tcase RendererShader::ShaderType::kVertex: return "vs";\n\tcase RendererShader::ShaderType::kFragment: return "ps";\n\tcase RendererShader::ShaderType::kGeometry: return "gs";\n\tdefault: return "unknown";\n\t}\n}\n\nstatic void DiagnosticDumpShaderSource(RendererShader::ShaderType type, uint64 baseHash, uint64 auxHash, std::string_view reason, const std::string& source, const char* marker)\n{\n\tconst auto dir = ActiveSettings::GetCachePath("shaderCache/diagnostics/vulkan");\n\tstd::error_code ec;\n\tstd::filesystem::create_directories(dir, ec);\n\tif (ec)\n\t{\n\t\tcemuLog_log(LogType::Force, "{} directory_error={} path={}", marker, ec.value(), _pathToUtf8(dir));\n\t\treturn;\n\t}\n\n\tconst auto filename = dir / fmt::format("{}_{:016x}_{:016x}_{}.glsl", DiagnosticShaderStageName(type), baseHash, auxHash, reason);\n\tstatic std::mutex s_dumpMutex;\n\tstd::lock_guard<std::mutex> lock(s_dumpMutex);\n\tstd::ofstream file(filename, std::ios::out | std::ios::binary | std::ios::trunc);\n\tif (!file.is_open())\n\t{\n\t\tcemuLog_log(LogType::Force, "{} open_failed path={}", marker, _pathToUtf8(filename));\n\t\treturn;\n\t}\n\tfile.write(source.data(), static_cast<std::streamsize>(source.size()));\n\tfile.close();\n\tcemuLog_log(LogType::Force, "{} stage={} base={:016x} aux={:016x} reason={} bytes={} path={}", marker, DiagnosticShaderStageName(type), baseHash, auxHash, reason, source.size(), _pathToUtf8(filename));\n}\n\n'''
shader = replace_once(shader, helper_anchor, helper_code, "shader diagnostic helpers")

module_anchor = '''\tVkResult result = vkCreateShaderModule(m_device, &createInfo, nullptr, &m_shader_module);\n\tif (result != VK_SUCCESS)\n\t{\n\t\tcemuLog_log(LogType::Force, "Vulkan: Shader error");\n'''
module_new = '''\tVkResult result = vkCreateShaderModule(m_device, &createInfo, nullptr, &m_shader_module);\n\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::ShaderCreation))\n\t\tcemuLog_log(LogType::Force, "[SHADER_CREATE] stage={} base={:016x} aux={:016x} spirvBytes={} result={}", DiagnosticShaderStageName(GetType()), m_baseHash, m_auxHash, spirvBuffer.size_bytes(), (sint32)result);\n\tif (result != VK_SUCCESS)\n\t{\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DumpFailedShader))\n\t\t\tDiagnosticDumpShaderSource(GetType(), m_baseHash, m_auxHash, "module_create", m_glslCode, "[SHADER_DUMP_FAILED]");\n\t\tcemuLog_log(LogType::Force, "Vulkan: Shader error");\n'''
shader = replace_once(shader, module_anchor, module_new, "shader module creation probe")

compile_anchor = '''void RendererShaderVk::CompileInternal(bool isRenderThread)\n{\n\tconst bool compileWithDebugInfo = ((VulkanRenderer*)g_renderer.get())->IsTracingToolEnabled();\n\n'''
compile_new = '''void RendererShaderVk::CompileInternal(bool isRenderThread)\n{\n\tconst bool compileWithDebugInfo = ((VulkanRenderer*)g_renderer.get())->IsTracingToolEnabled();\n\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DumpEveryShader))\n\t\tDiagnosticDumpShaderSource(GetType(), m_baseHash, m_auxHash, "all", m_glslCode, "[SHADER_DUMP_ALL]");\n\n'''
shader = replace_once(shader, compile_anchor, compile_new, "dump-every-shader hook")

preprocess_anchor = '''\tif (!Shader.preprocess(&Resources, 450, ENoProfile, false, false, messagesPreprocess, &PreprocessedGLSL, Includer))\n\t{\n\t\tcemuLog_log(LogType::Force, fmt::format("GLSL Preprocessing Failed For {:016x}_{:016x}: \\\"{}\\\"", m_baseHash, m_auxHash, Shader.getInfoLog()));\n\t\tFinishCompilation();\n'''
preprocess_new = '''\tif (!Shader.preprocess(&Resources, 450, ENoProfile, false, false, messagesPreprocess, &PreprocessedGLSL, Includer))\n\t{\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GLSLCompileFailure))\n\t\t\tcemuLog_log(LogType::Force, "[GLSL_FAIL] phase=preprocess stage={} base={:016x} aux={:016x} info={}", DiagnosticShaderStageName(GetType()), m_baseHash, m_auxHash, Shader.getInfoLog());\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DumpFailedShader))\n\t\t\tDiagnosticDumpShaderSource(GetType(), m_baseHash, m_auxHash, "glsl_preprocess", m_glslCode, "[SHADER_DUMP_FAILED]");\n\t\tcemuLog_log(LogType::Force, fmt::format("GLSL Preprocessing Failed For {:016x}_{:016x}: \\\"{}\\\"", m_baseHash, m_auxHash, Shader.getInfoLog()));\n\t\tFinishCompilation();\n'''
shader = replace_once(shader, preprocess_anchor, preprocess_new, "GLSL preprocess failure probe")

parse_anchor = '''\tif (!Shader.parse(&Resources, 100, false, messagesParseLink))\n\t{\n\t\tcemuLog_log(LogType::Force, fmt::format("GLSL parsing failed for {:016x}_{:016x}: \\\"{}\\\"", m_baseHash, m_auxHash, Shader.getInfoLog()));\n\t\tcemuLog_logDebug(LogType::Force, "GLSL source:\\n{}", m_glslCode);\n'''
parse_new = '''\tif (!Shader.parse(&Resources, 100, false, messagesParseLink))\n\t{\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GLSLCompileFailure))\n\t\t\tcemuLog_log(LogType::Force, "[GLSL_FAIL] phase=parse stage={} base={:016x} aux={:016x} info={}", DiagnosticShaderStageName(GetType()), m_baseHash, m_auxHash, Shader.getInfoLog());\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DumpFailedShader))\n\t\t\tDiagnosticDumpShaderSource(GetType(), m_baseHash, m_auxHash, "glsl_parse", m_glslCode, "[SHADER_DUMP_FAILED]");\n\t\tcemuLog_log(LogType::Force, fmt::format("GLSL parsing failed for {:016x}_{:016x}: \\\"{}\\\"", m_baseHash, m_auxHash, Shader.getInfoLog()));\n\t\tcemuLog_logDebug(LogType::Force, "GLSL source:\\n{}", m_glslCode);\n'''
shader = replace_once(shader, parse_anchor, parse_new, "GLSL parse failure probe")

link_anchor = '''\tif (!Program.link(messagesParseLink))\n\t{\n\t\tcemuLog_log(LogType::Force, fmt::format("GLSL linking failed for {:016x}_{:016x}: \\\"{}\\\"", m_baseHash, m_auxHash, Program.getInfoLog()));\n\t\tcemu_assert_debug(false);\n'''
link_new = '''\tif (!Program.link(messagesParseLink))\n\t{\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GLSLCompileFailure))\n\t\t\tcemuLog_log(LogType::Force, "[GLSL_FAIL] phase=link stage={} base={:016x} aux={:016x} info={}", DiagnosticShaderStageName(GetType()), m_baseHash, m_auxHash, Program.getInfoLog());\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DumpFailedShader))\n\t\t\tDiagnosticDumpShaderSource(GetType(), m_baseHash, m_auxHash, "glsl_link", m_glslCode, "[SHADER_DUMP_FAILED]");\n\t\tcemuLog_log(LogType::Force, fmt::format("GLSL linking failed for {:016x}_{:016x}: \\\"{}\\\"", m_baseHash, m_auxHash, Program.getInfoLog()));\n\t\tcemu_assert_debug(false);\n'''
shader = replace_once(shader, link_anchor, link_new, "GLSL link failure probe")

mapio_anchor = '''\tif (!Program.mapIO())\n\t{\n\t\tcemuLog_log(LogType::Force, fmt::format("GLSL linking failed for {:016x}_{:016x}: \\\"{}\\\"", m_baseHash, m_auxHash, Program.getInfoLog()));\n\t\tFinishCompilation();\n'''
mapio_new = '''\tif (!Program.mapIO())\n\t{\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GLSLCompileFailure))\n\t\t\tcemuLog_log(LogType::Force, "[GLSL_FAIL] phase=mapio stage={} base={:016x} aux={:016x} info={}", DiagnosticShaderStageName(GetType()), m_baseHash, m_auxHash, Program.getInfoLog());\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DumpFailedShader))\n\t\t\tDiagnosticDumpShaderSource(GetType(), m_baseHash, m_auxHash, "glsl_mapio", m_glslCode, "[SHADER_DUMP_FAILED]");\n\t\tcemuLog_log(LogType::Force, fmt::format("GLSL linking failed for {:016x}_{:016x}: \\\"{}\\\"", m_baseHash, m_auxHash, Program.getInfoLog()));\n\t\tFinishCompilation();\n'''
shader = replace_once(shader, mapio_anchor, mapio_new, "GLSL mapIO failure probe")

spirv_anchor = '''\tGlslangToSpv(*Program.getIntermediate(state), spirvBuffer, &logger, &spvOptions);\n\n\t//double timeDur = benchmarkTimer_stop(beginTime);\n'''
spirv_new = '''\tGlslangToSpv(*Program.getIntermediate(state), spirvBuffer, &logger, &spvOptions);\n\tif (spirvBuffer.empty())\n\t{\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::SPIRVCompileFailure))\n\t\t\tcemuLog_log(LogType::Force, "[SPIRV_FAIL] empty_output stage={} base={:016x} aux={:016x}", DiagnosticShaderStageName(GetType()), m_baseHash, m_auxHash);\n\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DumpFailedShader))\n\t\t\tDiagnosticDumpShaderSource(GetType(), m_baseHash, m_auxHash, "spirv_empty", m_glslCode, "[SHADER_DUMP_FAILED]");\n\t}\n\n\t//double timeDur = benchmarkTimer_stop(beginTime);\n'''
shader = replace_once(shader, spirv_anchor, spirv_new, "SPIR-V empty-output probe")

shader_path.write_text(shader, encoding="utf-8", newline="\n")

renderer_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
renderer = renderer_path.read_text(encoding="utf-8")
if '#include "diagnostics/RuntimeDiagnostics.h"\n' not in renderer:
    renderer = replace_once(
        renderer,
        '#include "config/CemuConfig.h"\n',
        '#include "config/CemuConfig.h"\n#include "diagnostics/RuntimeDiagnostics.h"\n',
        "VulkanRenderer diagnostics include",
    )

cache_anchor = '''\tVkResult result = vkCreatePipelineCache(m_logicalDevice, &createInfo, nullptr, &m_pipeline_cache);\n\tif (result != VK_SUCCESS)\n\t{\n\t\tcemuLog_log(LogType::Force, "Failed to open Vulkan pipeline cache: {}", result);\n'''
cache_new = '''\tVkResult result = vkCreatePipelineCache(m_logicalDevice, &createInfo, nullptr, &m_pipeline_cache);\n\tif (result != VK_SUCCESS)\n\t{\n\t\tif (!cacheData.empty() && RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PipelineCacheMismatch))\n\t\t\tcemuLog_log(LogType::Force, "[PIPE_CACHE_MISMATCH] result={} cacheBytes={} title={:016x}", (sint32)result, cacheData.size(), CafeSystem::GetForegroundTitleId());\n\t\tcemuLog_log(LogType::Force, "Failed to open Vulkan pipeline cache: {}", result);\n'''
renderer = replace_once(renderer, cache_anchor, cache_new, "pipeline cache mismatch probe")
renderer_path.write_text(renderer, encoding="utf-8", newline="\n")

verify_path = Path("tools/diagnostics/Verify-DiagnosticCoverage.py")
verify = verify_path.read_text(encoding="utf-8")
verify = replace_once(
    verify,
    '''    "ShaderAuxHash": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::ShaderAuxHash"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[PIPE_VS_AUX]")],\n\n    # Render-target / synchronization\n''',
    '''    "ShaderAuxHash": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "Flag::ShaderAuxHash"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp", "[PIPE_VS_AUX]")],\n    "PipelineCacheMismatch": [("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "Flag::PipelineCacheMismatch"), ("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp", "[PIPE_CACHE_MISMATCH]")],\n    "ShaderCreation": [("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp", "Flag::ShaderCreation"), ("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp", "[SHADER_CREATE]")],\n    "GLSLCompileFailure": [("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp", "Flag::GLSLCompileFailure"), ("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp", "[GLSL_FAIL]")],\n    "SPIRVCompileFailure": [("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp", "Flag::SPIRVCompileFailure"), ("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp", "[SPIRV_FAIL]")],\n    "DumpFailedShader": [("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp", "Flag::DumpFailedShader"), ("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp", "[SHADER_DUMP_FAILED]")],\n    "DumpEveryShader": [("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp", "Flag::DumpEveryShader"), ("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp", "[SHADER_DUMP_ALL]")],\n\n    # Render-target / synchronization\n''',
    "coverage verifier shader/cache hooks",
)
verify_path.write_text(verify, encoding="utf-8", newline="\n")

print("[shader-failure] six independent shader/cache diagnostics installed; coverage verifier extended")
