from pathlib import Path


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


def ensure_include(text, anchor, include_line, label):
    if include_line in text:
        return text
    return replace_once(text, anchor, anchor + include_line, label)


# PS-input-linkage diagnostics need the generated Vulkan GLSL and SPIR-V to
# survive until a failing graphics pipeline is created. Keep them only while
# the PS input linkage checkbox is enabled.
hdr_path = "src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.h"
h = read(hdr_path)
h = replace_once(
    h,
    "\tVkShaderModule& GetShaderModule() { return m_shader_module; }\n",
    "\tVkShaderModule& GetShaderModule() { return m_shader_module; }\n"
    "\tconst std::string& GetDiagnosticGLSL() const { return m_glslCode; }\n"
    "\tconst std::vector<uint32>& GetDiagnosticSPIRV() const { return m_diagSpirvCode; }\n",
    "RendererShaderVk diagnostic getters",
)
h = replace_once(
    h,
    "\tstd::string m_glslCode;\n",
    "\tstd::string m_glslCode;\n\tstd::vector<uint32> m_diagSpirvCode;\n",
    "RendererShaderVk diagnostic SPIR-V storage",
)
write(hdr_path, h)

cpp_path = "src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp"
c = read(cpp_path)
c = ensure_include(
    c,
    '#include "config/CemuConfig.h"\n',
    '#include "diagnostics/RuntimeDiagnostics.h"\n',
    "RendererShaderVk RuntimeDiagnostics include",
)
c = replace_once(
    c,
    "void RendererShaderVk::FinishCompilation()\n{\n\tm_glslCode.clear();\n\tm_glslCode.shrink_to_fit();\n}\n",
    "void RendererShaderVk::FinishCompilation()\n{\n"
    "\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PSInputLinkage))\n"
    "\t\treturn;\n"
    "\tm_glslCode.clear();\n"
    "\tm_glslCode.shrink_to_fit();\n"
    "\tm_diagSpirvCode.clear();\n"
    "\tm_diagSpirvCode.shrink_to_fit();\n"
    "}\n",
    "RendererShaderVk diagnostic source retention",
)
c = replace_once(
    c,
    "\t\t\t// generate shader from cached SPIR-V buffer\n\t\t\tCreateVkShaderModule(std::span<uint32>((uint32*)cacheFileData.data(), cacheFileData.size() / sizeof(uint32)));\n",
    "\t\t\t// generate shader from cached SPIR-V buffer\n"
    "\t\t\tauto cachedSpirv = std::span<uint32>((uint32*)cacheFileData.data(), cacheFileData.size() / sizeof(uint32));\n"
    "\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PSInputLinkage))\n"
    "\t\t\t\tm_diagSpirvCode.assign(cachedSpirv.begin(), cachedSpirv.end());\n"
    "\t\t\tCreateVkShaderModule(cachedSpirv);\n",
    "cached SPIR-V diagnostic retention",
)
c = replace_once(
    c,
    "\tGlslangToSpv(*Program.getIntermediate(state), spirvBuffer, &logger, &spvOptions);\n",
    "\tGlslangToSpv(*Program.getIntermediate(state), spirvBuffer, &logger, &spvOptions);\n"
    "\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PSInputLinkage))\n"
    "\t\tm_diagSpirvCode = spirvBuffer;\n",
    "compiled SPIR-V diagnostic retention",
)
write(cpp_path, c)

# Extend the existing PS-input-linkage failure probe. It now logs the exact GLSL
# lines that mention the failing semantic and writes the complete VS/PS GLSL and
# SPIR-V pair under the user-data directory. Repeated failures overwrite the
# same pair, keeping the diagnostic bounded.
pc_path = "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp"
p = read(pc_path)
p = ensure_include(
    p,
    '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"\n',
    '#include "Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.h"\n',
    "pipeline RendererShaderVk include",
)
p = ensure_include(
    p,
    '#include "HW/Latte/Renderer/RendererCore.h"\n',
    '#include <fstream>\n',
    "pipeline fstream include",
)

helper_anchor = "extern std::atomic_uint64_t g_compiling_pipelines_syncTimeSum;\n"
helpers = r'''

static void _diagLogPSInputGlslLine(const char* stage, const std::string& glsl, uint32 semanticId)
{
	const std::string token = fmt::format("passParameterSem{}", semanticId);
	size_t searchPos = 0;
	uint32 matches = 0;
	while (matches < 8)
	{
		const size_t hit = glsl.find(token, searchPos);
		if (hit == std::string::npos)
			break;
		size_t lineStart = glsl.rfind('\n', hit);
		lineStart = (lineStart == std::string::npos) ? 0 : lineStart + 1;
		size_t lineEnd = glsl.find('\n', hit);
		lineEnd = (lineEnd == std::string::npos) ? glsl.size() : lineEnd;
		std::string line = glsl.substr(lineStart, lineEnd - lineStart);
		if (!line.empty() && line.back() == '\r')
			line.pop_back();
		cemuLog_log(LogType::Force, "[ADRENO_DIAG] PS_INPUT_GLSL stage={} semantic={} line={}", stage, semanticId, line);
		++matches;
		searchPos = lineEnd;
	}
	if (matches == 0)
		cemuLog_log(LogType::Force, "[ADRENO_DIAG] PS_INPUT_GLSL stage={} semantic={} line=<not-found>", stage, semanticId);
}

static bool _diagWritePSInputText(const fs::path& path, const std::string& text)
{
	std::ofstream out(path, std::ios::binary | std::ios::trunc);
	if (!out)
		return false;
	out.write(text.data(), (std::streamsize)text.size());
	return out.good();
}

static bool _diagWritePSInputSpirv(const fs::path& path, const std::vector<uint32>& spirv)
{
	if (spirv.empty())
		return false;
	std::ofstream out(path, std::ios::binary | std::ios::trunc);
	if (!out)
		return false;
	out.write((const char*)spirv.data(), (std::streamsize)(spirv.size() * sizeof(uint32)));
	return out.good();
}

static void _diagDumpPSInputLinkagePair(const LatteDecompilerShader* diagVS, const LatteDecompilerShader* diagPS)
{
	if (!diagVS || !diagPS || !diagVS->shader || !diagPS->shader)
		return;
	const auto* vsVk = static_cast<const RendererShaderVk*>(diagVS->shader);
	const auto* psVk = static_cast<const RendererShaderVk*>(diagPS->shader);
	const fs::path dumpDir = ActiveSettings::GetUserDataPath("shaderDumps/ps_input_linkage");
	std::error_code ec;
	fs::create_directories(dumpDir, ec);
	if (ec)
	{
		cemuLog_log(LogType::Force, "[ADRENO_DIAG] PS_INPUT_DUMP failed dir={} error={}", _pathToUtf8(dumpDir), ec.message());
		return;
	}
	const std::string stem = fmt::format("pipeline_fail_vs_{:016x}_{:016x}_ps_{:016x}_{:016x}",
		diagVS->baseHash, diagVS->auxHash, diagPS->baseHash, diagPS->auxHash);
	const fs::path vsGlsl = dumpDir / (stem + "_vs.glsl");
	const fs::path psGlsl = dumpDir / (stem + "_ps.glsl");
	const fs::path vsSpv = dumpDir / (stem + "_vs.spv");
	const fs::path psSpv = dumpDir / (stem + "_ps.spv");
	const bool vsGlslOk = _diagWritePSInputText(vsGlsl, vsVk->GetDiagnosticGLSL());
	const bool psGlslOk = _diagWritePSInputText(psGlsl, psVk->GetDiagnosticGLSL());
	const bool vsSpvOk = _diagWritePSInputSpirv(vsSpv, vsVk->GetDiagnosticSPIRV());
	const bool psSpvOk = _diagWritePSInputSpirv(psSpv, psVk->GetDiagnosticSPIRV());
	cemuLog_log(LogType::Force,
		"[ADRENO_DIAG] PS_INPUT_DUMP dir={} stem={} vsGLSL={} psGLSL={} vsSPV={} psSPV={}",
		_pathToUtf8(dumpDir), stem, vsGlslOk ? 1 : 0, psGlslOk ? 1 : 0, vsSpvOk ? 1 : 0, psSpvOk ? 1 : 0);
}
'''
p = replace_once(p, helper_anchor, helper_anchor + helpers, "PS input linkage dump helpers")

log_anchor = '''\t\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\t"[ADRENO_DIAG] PS_INPUT_LINK vs={:016x} ps={:016x} idx={} semantic={} raw=0x{:08x} default={} flat={} centroid={} nopersp={} vsProducer={}",
\t\t\t\t\t\tvsHash, psHash, i, semanticId, raw, defaultValue, flat, centroid, noPerspective, vsProducer ? 1 : 0);
'''
log_new = log_anchor + '''\t\t\t\t\tif (!vsProducer && diagVS && diagVS->shader && diagPS->shader)
\t\t\t\t\t{
\t\t\t\t\t\tconst auto* vsVk = static_cast<const RendererShaderVk*>(diagVS->shader);
\t\t\t\t\t\tconst auto* psVk = static_cast<const RendererShaderVk*>(diagPS->shader);
\t\t\t\t\t\t_diagLogPSInputGlslLine("vs", vsVk->GetDiagnosticGLSL(), semanticId);
\t\t\t\t\t\t_diagLogPSInputGlslLine("ps", psVk->GetDiagnosticGLSL(), semanticId);
\t\t\t\t\t}
'''
p = replace_once(p, log_anchor, log_new, "PS input GLSL line logging")

block_end = '''\t\t\t\t}
\t\t\t}
'''
marker = 'RuntimeDiagnostics::Flag::PSInputLinkage'
marker_pos = p.find(marker)
if marker_pos < 0:
    raise RuntimeError("PSInputLinkage block marker not found")
end_pos = p.find(block_end, marker_pos)
if end_pos < 0:
    raise RuntimeError("PSInputLinkage block end not found")
p = p[:end_pos] + '''\t\t\t\t}
\t\t\t\t_diagDumpPSInputLinkagePair(diagVS, diagPS);
\t\t\t}
''' + p[end_pos + len(block_end):]
write(pc_path, p)

# Static contracts: the checkbox remains the sole gate and the new output is
# bounded to failing pipeline pairs.
checks = {
    hdr_path: ["GetDiagnosticGLSL", "GetDiagnosticSPIRV", "m_diagSpirvCode"],
    cpp_path: ["Flag::PSInputLinkage", "m_diagSpirvCode = spirvBuffer", "cachedSpirv"],
    pc_path: ["PS_INPUT_GLSL", "PS_INPUT_DUMP", "shaderDumps/ps_input_linkage", "_diagDumpPSInputLinkagePair"],
}
for path, needles in checks.items():
    text = read(path)
    for needle in needles:
        if needle not in text:
            raise RuntimeError(f"{path}: missing diagnostic contract marker {needle}")

print("[ps-input-linkage-dump] PASS")
