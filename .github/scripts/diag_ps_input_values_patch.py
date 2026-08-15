from pathlib import Path


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8", newline="\n")


# Store the PS input-control words on the shader object itself. This makes the
# diagnostic safe even when pipeline compilation happens asynchronously: we
# print the state that created that exact pixel shader, not whichever Latte
# registers happen to be active when vkCreateGraphicsPipelines later fails.
hdr = "src/Cafe/HW/Latte/LegacyShaderDecompiler/LatteDecompiler.h"
h = read(hdr)
h_anchor = "\tuint32 outputParameterMask{ 0 };"
if h.count(h_anchor) != 1:
    raise RuntimeError(f"LatteDecompilerShader output anchor count={h.count(h_anchor)}")
h = h.replace(
    h_anchor,
    h_anchor
    + "\n\t// Adreno diagnostic only: SPI_PS_INPUT_CNTL words captured when this PS variant is created"
    + "\n\tuint8 diagPSInputCount{0};"
    + "\n\tuint32 diagPSInputControl[32]{};",
    1,
)
write(hdr, h)

src = "src/Cafe/HW/Latte/Core/LatteShader.cpp"
s = read(src)
func_marker = "LatteDecompilerShader* LatteShader_CreateShaderFromDecompilerOutput"
func_pos = s.find(func_marker)
if func_pos < 0:
    raise RuntimeError("CreateShader function marker not found")
assign = "\tshader->baseHash = baseHash;"
assign_pos = s.find(assign, func_pos)
if assign_pos < 0:
    raise RuntimeError("CreateShader baseHash assignment not found inside function")
next_func = s.find("\nvoid LatteShader_GetDecompilerOptions", func_pos)
if next_func < 0 or assign_pos > next_func:
    raise RuntimeError("CreateShader baseHash assignment resolved outside target function")
insert_pos = assign_pos + len(assign)
insert = (
    "\n\tif (decompilerOutput.shaderType == LatteConst::ShaderType::Pixel && contextRegister)"
    "\n\t{"
    "\n\t\tconst uint32 diagCount = std::min<uint32>(contextRegister[mmSPI_PS_IN_CONTROL_0] & 0x3F, 32u);"
    "\n\t\tshader->diagPSInputCount = (uint8)diagCount;"
    "\n\t\tfor (uint32 i = 0; i < diagCount; ++i)"
    "\n\t\t\tshader->diagPSInputControl[i] = contextRegister[mmSPI_PS_INPUT_CNTL_0 + i];"
    "\n\t}"
)
s = s[:insert_pos] + insert + s[insert_pos:]
write(src, s)

# diag_adreno_patch.py + fix_diag_tail.py have already rewritten the failure
# block at this point. Insert one compact PS-input record per input immediately
# before the existing PIPELINE_FAIL summary.
pc = "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp"
p = read(pc)
log_anchor = '''\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[ADRENO_DIAG] PIPELINE_FAIL state={:016x} min={:016x} result={} vs={:016x} ps={:016x} gs={:016x} prim={} topology={} stages={} attrs={} bindings={} cull={} front={} polygon={} depthClamp={} depthTest={} depthWrite={} depthCompare={} blendAttachments={} samples={} robust={} pnext={} rasterPnext={}",'''
if p.count(log_anchor) != 1:
    raise RuntimeError(f"PIPELINE_FAIL log anchor count={p.count(log_anchor)}")
input_log = '''\t\t\tif (m_diagPipelineInfo->pixelShader)
\t\t\t{
\t\t\t\tconst auto* diagPS = m_diagPipelineInfo->pixelShader;
\t\t\t\tfor (uint32 i = 0; i < diagPS->diagPSInputCount; ++i)
\t\t\t\t{
\t\t\t\t\tconst uint32 raw = diagPS->diagPSInputControl[i];
\t\t\t\t\tconst uint32 semanticId = raw & 0xFF;
\t\t\t\t\tconst uint32 defaultValue = (raw >> 8) & 3;
\t\t\t\t\tconst uint32 flat = (raw >> 10) & 1;
\t\t\t\t\tconst uint32 centroid = (raw >> 11) & 1;
\t\t\t\t\tconst uint32 noPerspective = (raw >> 12) & 1;
\t\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\t"[ADRENO_DIAG] PS_INPUT ps={:016x} idx={} semantic={} raw=0x{:08x} default={} flat={} centroid={} nopersp={}",
\t\t\t\t\t\tpsHash, i, semanticId, raw, defaultValue, flat, centroid, noPerspective);
\t\t\t\t}
\t\t\t}
'''
p = p.replace(log_anchor, input_log + log_anchor, 1)
write(pc, p)

print("PS input-control diagnostic patch applied successfully")
