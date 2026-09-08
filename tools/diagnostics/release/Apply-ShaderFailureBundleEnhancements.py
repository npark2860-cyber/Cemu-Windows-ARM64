from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp")
text = path.read_text(encoding="utf-8")

# Add a binary SPIR-V dumper next to the existing GLSL diagnostic helper.
ctor_anchor = "RendererShaderVk::RendererShaderVk(ShaderType type, uint64 baseHash, uint64 auxHash, bool isGameShader, bool isGfxPackShader, const std::string& glslCode)\n"
spirv_helper = r'''static void DiagnosticDumpSpirv(RendererShader::ShaderType type, uint64 baseHash, uint64 auxHash, std::string_view reason, std::span<uint32> spirv, const char* marker)
{
	const auto dir = ActiveSettings::GetCachePath("shaderCache/diagnostics/vulkan");
	std::error_code ec;
	std::filesystem::create_directories(dir, ec);
	if (ec)
	{
		cemuLog_log(LogType::Force, "{} directory_error={} path={}", marker, ec.value(), _pathToUtf8(dir));
		return;
	}
	const auto filename = dir / fmt::format("{}_{:016x}_{:016x}_{}.spv", DiagnosticShaderStageName(type), baseHash, auxHash, reason);
	static std::mutex s_spirvDumpMutex;
	std::lock_guard<std::mutex> lock(s_spirvDumpMutex);
	std::ofstream file(filename, std::ios::out | std::ios::binary | std::ios::trunc);
	if (!file.is_open())
	{
		cemuLog_log(LogType::Force, "{} open_failed path={}", marker, _pathToUtf8(filename));
		return;
	}
	file.write(reinterpret_cast<const char*>(spirv.data()), static_cast<std::streamsize>(spirv.size_bytes()));
	file.close();
	cemuLog_log(LogType::Force, "{} stage={} id={}-{:08x} base={:016x} aux={:016x} reason={} bytes={} path={}",
		marker, DiagnosticShaderStageName(type), DiagnosticShaderStageName(type), (uint32)baseHash,
		baseHash, auxHash, reason, spirv.size_bytes(), _pathToUtf8(filename));
}

'''
text = replace_once(text, ctor_anchor, spirv_helper + ctor_anchor, "SPIR-V dump helper")

# If the driver rejects vkCreateShaderModule, preserve both the generated GLSL
# and the exact SPIR-V bytes that were passed to the Adreno driver.
module_old = '''\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DumpFailedShader))
\t\t\tDiagnosticDumpShaderSource(GetType(), m_baseHash, m_auxHash, "module_create", m_glslCode, "[SHADER_DUMP_FAILED]");
'''
module_new = '''\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::DumpFailedShader))
\t\t{
\t\t\tDiagnosticDumpShaderSource(GetType(), m_baseHash, m_auxHash, "module_create", m_glslCode, "[SHADER_DUMP_FAILED]");
\t\t\tDiagnosticDumpSpirv(GetType(), m_baseHash, m_auxHash, "module_create", spirvBuffer, "[SPIRV_DUMP_FAILED]");
\t\t}
'''
text = replace_once(text, module_old, module_new, "shader-module failure bundle")

# glslang parses/links the preprocessed source. Preserve that exact source next
# to the original generated GLSL so compiler line numbers are directly useful.
for reason in ("glsl_parse", "glsl_link", "glsl_mapio"):
    old = f'DiagnosticDumpShaderSource(GetType(), m_baseHash, m_auxHash, "{reason}", m_glslCode, "[SHADER_DUMP_FAILED]");'
    new = old + f'\n\t\t\tDiagnosticDumpShaderSource(GetType(), m_baseHash, m_auxHash, "{reason}_preprocessed", PreprocessedGLSL, "[SHADER_DUMP_PREPROCESSED]");'
    text = replace_once(text, old, new, f"{reason} preprocessed dump")

path.write_text(text, encoding="utf-8", newline="\n")
print("[shader-failure-bundle] original/preprocessed GLSL and rejected SPIR-V bundle installed")
