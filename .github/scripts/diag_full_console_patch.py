from pathlib import Path


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8", newline="\n")


# -----------------------------------------------------------------------------
# 1) Always open a real Windows console for this diagnostic release build.
#    cemuLog_log() already mirrors enabled log lines to stdout when Verbose()
#    is true, so keep normal log.txt output while also showing it live.
# -----------------------------------------------------------------------------
main = "src/main.cpp"
s = read(main)
old_console = '''bool isConsoleConnected = false;
void requireConsole()
{
    #if BOOST_OS_WINDOWS
    if (isConsoleConnected)
        return;

    HANDLE hOut = GetStdHandle(STD_OUTPUT_HANDLE);
    DWORD dwFileType = GetFileType(hOut);

    if (dwFileType == FILE_TYPE_UNKNOWN || dwFileType == FILE_TYPE_CHAR)
    {
        if (AttachConsole(ATTACH_PARENT_PROCESS) != FALSE)
        {
            freopen("CONOUT$", "w", stdout);
            freopen("CONOUT$", "w", stderr);
            freopen("CONIN$", "r", stdin);
            isConsoleConnected = true;
        }
    }
    else
    {
        isConsoleConnected = true; 
    }
    #endif
}'''
new_console = '''bool isConsoleConnected = false;
void requireConsole()
{
    #if BOOST_OS_WINDOWS
    if (isConsoleConnected)
        return;

    // If launched from Explorer there is no parent console. Attach when
    // possible, otherwise allocate our own diagnostic console window.
    if (GetConsoleWindow() == nullptr)
    {
        if (AttachConsole(ATTACH_PARENT_PROCESS) == FALSE)
            AllocConsole();
    }

    if (GetConsoleWindow() != nullptr)
    {
        freopen("CONOUT$", "w", stdout);
        freopen("CONOUT$", "w", stderr);
        freopen("CONIN$", "r", stdin);
        SetConsoleOutputCP(CP_UTF8);
        isConsoleConnected = true;
    }
    #endif
}'''
if s.count(old_console) != 1:
    raise RuntimeError(f"requireConsole block count={s.count(old_console)}")
s = s.replace(old_console, new_console, 1)

winmain_anchor = '''int wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPWSTR lpCmdLine, int nShowCmd)
{
'''
if s.count(winmain_anchor) != 1:
    raise RuntimeError(f"wWinMain anchor count={s.count(winmain_anchor)}")
s = s.replace(winmain_anchor, winmain_anchor + '\trequireConsole();\n', 1)
write(main, s)

launch = "src/config/LaunchSettings.h"
s = read(launch)
verbose_old = "\tstatic bool Verbose() { return s_verbose; }"
verbose_new = "\tstatic bool Verbose() { return true; } // full ARM64 diagnostic: mirror enabled log lines to console"
if s.count(verbose_old) != 1:
    raise RuntimeError(f"Verbose getter count={s.count(verbose_old)}")
s = s.replace(verbose_old, verbose_new, 1)
write(launch, s)


# -----------------------------------------------------------------------------
# 2) Preserve the VS semantic routing registers on the exact shader object.
#    The previous PS diagnostic patch already added diagPSInputControl[] here.
# -----------------------------------------------------------------------------
hdr = "src/Cafe/HW/Latte/LegacyShaderDecompiler/LatteDecompiler.h"
h = read(hdr)
h_anchor = "\tuint32 diagPSInputControl[32]{};"
if h.count(h_anchor) != 1:
    raise RuntimeError(f"PS diagnostic field anchor count={h.count(h_anchor)}")
h = h.replace(
    h_anchor,
    h_anchor
    + "\n\t// Full Adreno diagnostic: raw SPI_VS_OUT_ID_0..7 captured with this VS variant"
    + "\n\tuint32 diagVSOutId[8]{};",
    1,
)
write(hdr, h)

src = "src/Cafe/HW/Latte/Core/LatteShader.cpp"
s = read(src)
func_marker = "LatteDecompilerShader* LatteShader_CreateShaderFromDecompilerOutput"
func_pos = s.find(func_marker)
if func_pos < 0:
    raise RuntimeError("CreateShader function marker not found")
resource_anchor = "\n\t// copy resource mapping"
resource_pos = s.find(resource_anchor, func_pos)
if resource_pos < 0:
    raise RuntimeError("CreateShader resource-mapping anchor not found")
vs_capture = '''
\tif (decompilerOutput.shaderType == LatteConst::ShaderType::Vertex && contextRegister)
\t{
\t\tfor (uint32 i = 0; i < 8; ++i)
\t\t\tshader->diagVSOutId[i] = contextRegister[mmSPI_VS_OUT_ID_0 + i];
\t}
'''
s = s[:resource_pos] + vs_capture + s[resource_pos:]

# Force the already-existing shader dump hooks for this diagnostic build only.
# This writes generated GLSL (.txt) and original Latte shader binaries (.bin)
# into the normal dump/shaders directory without changing shader semantics.
dump_guard = '''\tif (!ActiveSettings::DumpShadersEnabled())
\t\treturn;'''
count = s.count(dump_guard)
if count != 2:
    raise RuntimeError(f"Expected 2 shader dump guards, found {count}")
s = s.replace(dump_guard, '''\t// Full ARM64 diagnostic build: always dump generated source/raw shader data.''')
write(src, s)


# -----------------------------------------------------------------------------
# 3) At the exact Vulkan pipeline failure, print everything needed to explain
#    VS -> PS interface generation in one run. This is derived from the same
#    conditions used by _emitVSExports(): outputParameterMask + SPI_VS_OUT_ID.
# -----------------------------------------------------------------------------
pc = "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp"
p = read(pc)

# Insert after the base-hash variables that the existing diagnostic patch adds.
hash_anchor = '''\t\t\tconst uint64 gsHash = m_diagPipelineInfo->geometryShader ? m_diagPipelineInfo->geometryShader->baseHash : 0;
'''
if p.count(hash_anchor) != 1:
    raise RuntimeError(f"hash anchor count={p.count(hash_anchor)}")
full_diag = r'''			const uint64 vsAux = m_diagPipelineInfo->vertexShader ? m_diagPipelineInfo->vertexShader->auxHash : 0;
			const uint64 psAux = m_diagPipelineInfo->pixelShader ? m_diagPipelineInfo->pixelShader->auxHash : 0;
			const uint64 gsAux = m_diagPipelineInfo->geometryShader ? m_diagPipelineInfo->geometryShader->auxHash : 0;
			cemuLog_log(LogType::Force,
				"[ADRENO_FULL] SHADERS vs={:016x}/{:016x} ps={:016x}/{:016x} gs={:016x}/{:016x}",
				vsHash, vsAux, psHash, psAux, gsHash, gsAux);

			if (m_diagPipelineInfo->vertexShader)
			{
				const auto* diagVS = m_diagPipelineInfo->vertexShader;
				cemuLog_log(LogType::Force,
					"[ADRENO_FULL] VS_SUMMARY vs={:016x} aux={:016x} outputMask=0x{:08x} outId0=0x{:08x} outId1=0x{:08x} outId2=0x{:08x} outId3=0x{:08x} outId4=0x{:08x} outId5=0x{:08x} outId6=0x{:08x} outId7=0x{:08x}",
					vsHash, vsAux, diagVS->outputParameterMask,
					diagVS->diagVSOutId[0], diagVS->diagVSOutId[1], diagVS->diagVSOutId[2], diagVS->diagVSOutId[3],
					diagVS->diagVSOutId[4], diagVS->diagVSOutId[5], diagVS->diagVSOutId[6], diagVS->diagVSOutId[7]);

				for (uint32 param = 0; param < 32; ++param)
				{
					const uint32 semanticId = (diagVS->diagVSOutId[param / 4] >> (8 * (param & 3))) & 0xFF;
					const uint32 analyzedExport = (diagVS->outputParameterMask >> param) & 1;
					if (analyzedExport)
					{
						cemuLog_log(LogType::Force,
							"[ADRENO_FULL] VS_PARAM vs={:016x} param={} semantic={} analyzedExport=1",
							vsHash, param, semanticId);
					}
				}
			}

			if (m_diagPipelineInfo->pixelShader)
			{
				const auto* diagPSFull = m_diagPipelineInfo->pixelShader;
				const auto* diagVSFull = m_diagPipelineInfo->vertexShader;
				for (uint32 i = 0; i < diagPSFull->diagPSInputCount; ++i)
				{
					const uint32 raw = diagPSFull->diagPSInputControl[i];
					const uint32 semanticId = raw & 0xFF;
					const uint32 defaultValue = (raw >> 8) & 3;
					sint32 matchingParam = -1;
					uint32 matchingParamAnalyzedExport = 0;
					if (diagVSFull)
					{
						for (uint32 param = 0; param < 32; ++param)
						{
							const uint32 vsSemantic = (diagVSFull->diagVSOutId[param / 4] >> (8 * (param & 3))) & 0xFF;
							if (vsSemantic == semanticId)
							{
								matchingParam = (sint32)param;
								matchingParamAnalyzedExport = (diagVSFull->outputParameterMask >> param) & 1;
								break;
							}
						}
					}
					cemuLog_log(LogType::Force,
						"[ADRENO_FULL] INTERFACE ps={:016x} inputLoc={} semantic={} default={} vsParam={} vsAnalyzedExport={} hostVSOutputExpected={}",
						psHash, i, semanticId, defaultValue, matchingParam, matchingParamAnalyzedExport,
						(matchingParam >= 0 && matchingParamAnalyzedExport) ? 1u : 0u);
				}
			}
'''
p = p.replace(hash_anchor, hash_anchor + full_diag, 1)
write(pc, p)

print("Full console + VS/PS interface diagnostic patch applied successfully")
