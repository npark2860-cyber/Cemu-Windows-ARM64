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


# Append new flags so saved bit positions for all existing diagnostics stay stable.
hdr_path = "src/diagnostics/RuntimeDiagnostics.h"
h = read(hdr_path)
h = replace_once(
    h,
    "    GpuTimestamp, CpuWaitBreakdown, DescriptorStats, MemoryUploadStats, JitPerformance, HitchTrigger, DiagnosticOverhead, SummaryOnExit,\n    Count",
    "    GpuTimestamp, CpuWaitBreakdown, DescriptorStats, MemoryUploadStats, JitPerformance, HitchTrigger, DiagnosticOverhead, SummaryOnExit,\n    PSInputLinkage, GPUOcclusionQueryVisibility,\n    Count",
    "targeted diagnostic enum append",
)
summary_case = "case Flag::SummaryOnExit:"
if h.count(summary_case) != 1:
    raise RuntimeError(f"SummaryOnExit IsImplemented case count={h.count(summary_case)}")
pos = h.index(summary_case)
ret = h.find("return true;", pos)
if ret < 0:
    raise RuntimeError("IsImplemented return true not found after SummaryOnExit")
h = h[:ret] + "    case Flag::PSInputLinkage:\n    case Flag::GPUOcclusionQueryVisibility:\n        " + h[ret:]
write(hdr_path, h)

# Add two checkboxes to the already-generated diagnostics UI. Existing generic
# binding/persistence code automatically covers them.
main_path = "src/gui/wxgui/MainWindow.cpp"
main = read(main_path)
main = replace_once(
    main,
    '{"Summary on exit",DiagFlag::SummaryOnExit}',
    '{"Summary on exit",DiagFlag::SummaryOnExit},{"PS input linkage",DiagFlag::PSInputLinkage},{"GPU occlusion/query visibility",DiagFlag::GPUOcclusionQueryVisibility}',
    "targeted diagnostic UI items",
)
write(main_path, main)

# Capture PS input-control words and VS exported semantic IDs on the exact shader
# objects so async pipeline compilation does not observe unrelated live registers.
dec_path = "src/Cafe/HW/Latte/LegacyShaderDecompiler/LatteDecompiler.h"
dec = read(dec_path)
dec = replace_once(
    dec,
    "\tuint32 outputParameterMask{ 0 };",
    "\tuint32 outputParameterMask{ 0 };\n"
    "\t// ARM64 diagnostic only: captured stage-linkage metadata.\n"
    "\tuint8 diagPSInputCount{0};\n"
    "\tuint32 diagPSInputControl[32]{};\n"
    "\tuint8 diagVSOutputCount{0};\n"
    "\tuint8 diagVSOutputSemantic[32]{};",
    "shader linkage diagnostic fields",
)
write(dec_path, dec)

shader_path = "src/Cafe/HW/Latte/Core/LatteShader.cpp"
s = read(shader_path)
func_marker = "LatteDecompilerShader* LatteShader_CreateShaderFromDecompilerOutput"
func_pos = s.find(func_marker)
if func_pos < 0:
    raise RuntimeError("CreateShader function marker not found")
assign = "\tshader->baseHash = baseHash;"
assign_pos = s.find(assign, func_pos)
if assign_pos < 0:
    raise RuntimeError("CreateShader baseHash assignment not found")
next_func = s.find("\nvoid LatteShader_GetDecompilerOptions", func_pos)
if next_func < 0 or assign_pos > next_func:
    raise RuntimeError("CreateShader baseHash assignment resolved outside target function")
insert_pos = assign_pos + len(assign)
capture = r'''
	if (contextRegister)
	{
		if (decompilerOutput.shaderType == LatteConst::ShaderType::Pixel)
		{
			uint32 diagCount = contextRegister[mmSPI_PS_IN_CONTROL_0] & 0x3F;
			if (diagCount > 32)
				diagCount = 32;
			shader->diagPSInputCount = (uint8)diagCount;
			for (uint32 i = 0; i < diagCount; ++i)
				shader->diagPSInputControl[i] = contextRegister[mmSPI_PS_INPUT_CNTL_0 + i];
		}
		else if (decompilerOutput.shaderType == LatteConst::ShaderType::Vertex)
		{
			for (uint32 paramIndex = 0; paramIndex < 32 && shader->diagVSOutputCount < 32; ++paramIndex)
			{
				if ((shader->outputParameterMask & (1u << paramIndex)) == 0)
					continue;
				shader->diagVSOutputSemantic[shader->diagVSOutputCount++] =
					(uint8)LatteShaderPSInputTable::getVertexShaderOutParamSemanticId(contextRegister, paramIndex);
			}
		}
	}
'''
s = s[:insert_pos] + capture + s[insert_pos:]
write(shader_path, s)

# On pipeline failure dump exact PS input controls and VS producer presence.
pc_path = "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp"
p = read(pc_path)
gs_anchor = "\t\t\tconst uint64 gsHash = m_diagPipelineInfo->geometryShader ? m_diagPipelineInfo->geometryShader->baseHash : 0;"
if p.count(gs_anchor) != 1:
    raise RuntimeError(f"pipeline failure hash anchor count={p.count(gs_anchor)}")
pslog = r'''
			if (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PSInputLinkage) && m_diagPipelineInfo->pixelShader)
			{
				const auto* diagPS = m_diagPipelineInfo->pixelShader;
				const auto* diagVS = m_diagPipelineInfo->vertexShader;
				for (uint32 i = 0; i < diagPS->diagPSInputCount; ++i)
				{
					const uint32 raw = diagPS->diagPSInputControl[i];
					const uint32 semanticId = raw & 0xFF;
					const uint32 defaultValue = (raw >> 8) & 3;
					const uint32 flat = (raw >> 10) & 1;
					const uint32 centroid = (raw >> 11) & 1;
					const uint32 noPerspective = (raw >> 12) & 1;
					bool vsProducer = false;
					if (diagVS)
					{
						for (uint32 j = 0; j < diagVS->diagVSOutputCount; ++j)
						{
							if (diagVS->diagVSOutputSemantic[j] == semanticId)
							{
								vsProducer = true;
								break;
							}
						}
					}
					cemuLog_log(LogType::Force,
						"[ADRENO_DIAG] PS_INPUT_LINK vs={:016x} ps={:016x} idx={} semantic={} raw=0x{:08x} default={} flat={} centroid={} nopersp={} vsProducer={}",
						vsHash, psHash, i, semanticId, raw, defaultValue, flat, centroid, noPerspective, vsProducer ? 1 : 0);
				}
			}
'''
p = p.replace(gs_anchor, gs_anchor + pslog, 1)
write(pc_path, p)

# GX2-level generic query visibility diagnostics.
gx2_path = "src/Cafe/OS/libs/gx2/GX2_Query.cpp"
g = read(gx2_path)
if '#include "diagnostics/RuntimeDiagnostics.h"\n' not in g:
    g = replace_once(g, '#include "GX2_Query.h"\n', '#include "GX2_Query.h"\n#include "diagnostics/RuntimeDiagnostics.h"\n', "GX2 query diagnostic include")
g = replace_once(
    g,
    "\t\t\t\t*(uint64*)(queryInfo->reg + 2) = 0x100000;",
    "\t\t\t\t*(uint64*)(queryInfo->reg + 2) = 0x100000;\n"
    "\t\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GPUOcclusionQueryVisibility))\n"
    "\t\t\t\t\tcemuLog_log(LogType::Force, \"[QUERY_VIS] layer=GX2 event=GPU_INIT_SEED title={:016x} query={:08x} seed={:x}\", titleId, (uint32)memory_getVirtualOffsetFromPointer(queryInfo), 0x100000u);",
    "GX2 GPU seed diagnostic",
)
g = replace_once(
    g,
    "\tvoid GX2QueryBegin(uint32 queryType, GX2Query* query)\n\t{\n",
    "\tvoid GX2QueryBegin(uint32 queryType, GX2Query* query)\n\t{\n"
    "\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GPUOcclusionQueryVisibility))\n"
    "\t\t\tcemuLog_log(LogType::Force, \"[QUERY_VIS] layer=GX2 event=BEGIN title={:016x} type={} query={:08x}\", CafeSystem::GetForegroundTitleId(), queryType, (uint32)memory_getVirtualOffsetFromPointer(query));\n",
    "GX2 query begin diagnostic",
)
g = replace_once(
    g,
    "\tvoid GX2QueryEnd(uint32 queryType, GX2Query* query)\n\t{\n",
    "\tvoid GX2QueryEnd(uint32 queryType, GX2Query* query)\n\t{\n"
    "\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GPUOcclusionQueryVisibility))\n"
    "\t\t\tcemuLog_log(LogType::Force, \"[QUERY_VIS] layer=GX2 event=END title={:016x} type={} query={:08x}\", CafeSystem::GetForegroundTitleId(), queryType, (uint32)memory_getVirtualOffsetFromPointer(query));\n",
    "GX2 query end diagnostic",
)
g = replace_once(
    g,
    "\t\tif (query->reg[LATTE_GC_NUM_RB * 4 + 1] == _swapEndianU32('OCPU') && query->reg[LATTE_GC_NUM_RB * 4 + 0] == 0)\n\t\t{\n\t\t\t// CPU query result not ready\n\t\t\treturn GX2_FALSE;\n\t\t}",
    "\t\tif (query->reg[LATTE_GC_NUM_RB * 4 + 1] == _swapEndianU32('OCPU') && query->reg[LATTE_GC_NUM_RB * 4 + 0] == 0)\n\t\t{\n"
    "\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GPUOcclusionQueryVisibility))\n"
    "\t\t\t\tcemuLog_log(LogType::Force, \"[QUERY_VIS] layer=GX2 event=GET_RESULT ready=0 reason=cpu_marker query={:08x}\", (uint32)memory_getVirtualOffsetFromPointer(query));\n"
    "\t\t\t// CPU query result not ready\n\t\t\treturn GX2_FALSE;\n\t\t}",
    "GX2 CPU not-ready diagnostic",
)
g = replace_once(
    g,
    "\t\tif ((startValue & 0x8000000000000000ULL) || (endValue & 0x8000000000000000ULL))\n\t\t{\n\t\t\treturn GX2_FALSE;\n\t\t}\n\t\t*resultOut = endValue - startValue;\n\t\treturn GX2_TRUE;",
    "\t\tif ((startValue & 0x8000000000000000ULL) || (endValue & 0x8000000000000000ULL))\n\t\t{\n"
    "\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GPUOcclusionQueryVisibility))\n"
    "\t\t\t\tcemuLog_log(LogType::Force, \"[QUERY_VIS] layer=GX2 event=GET_RESULT ready=0 reason=pending_bit query={:08x} start={:016x} end={:016x}\", (uint32)memory_getVirtualOffsetFromPointer(query), startValue, endValue);\n"
    "\t\t\treturn GX2_FALSE;\n\t\t}\n"
    "\t\t*resultOut = endValue - startValue;\n"
    "\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GPUOcclusionQueryVisibility))\n"
    "\t\t\tcemuLog_log(LogType::Force, \"[QUERY_VIS] layer=GX2 event=GET_RESULT ready=1 query={:08x} start={:016x} end={:016x} samples={}\", (uint32)memory_getVirtualOffsetFromPointer(query), startValue, endValue, endValue - startValue);\n"
    "\t\treturn GX2_TRUE;",
    "GX2 result diagnostic",
)
g = replace_once(
    g,
    "\t\tflags |= ((dontWaitBool != 0) << 19);\n\n\t\tgx2WriteGather_submitU32AsBE(pm4HeaderType3(IT_SET_PREDICATION, 2));",
    "\t\tflags |= ((dontWaitBool != 0) << 19);\n\n"
    "\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GPUOcclusionQueryVisibility))\n"
    "\t\t\tcemuLog_log(LogType::Force, \"[QUERY_VIS] layer=GX2 event=PRED_BEGIN title={:016x} type={} query={:08x} dontWait={} pixelsMustPass={} flags=0x{:08x}\", CafeSystem::GetForegroundTitleId(), queryType, (uint32)memory_getVirtualOffsetFromPointer(query), dontWaitBool, pixelsMustPassBool, flags);\n\n"
    "\t\tgx2WriteGather_submitU32AsBE(pm4HeaderType3(IT_SET_PREDICATION, 2));",
    "GX2 predication begin diagnostic",
)
g = replace_once(
    g,
    "\tvoid GX2QueryEndConditionalRender()\n\t{\n\t\tGX2ReserveCmdSpace(3);",
    "\tvoid GX2QueryEndConditionalRender()\n\t{\n"
    "\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GPUOcclusionQueryVisibility))\n"
    "\t\t\tcemuLog_log(LogType::Force, \"[QUERY_VIS] layer=GX2 event=PRED_END title={:016x}\", CafeSystem::GetForegroundTitleId());\n"
    "\t\tGX2ReserveCmdSpace(3);",
    "GX2 predication end diagnostic",
)
write(gx2_path, g)

# Vulkan-level query lifecycle/results, including protected direct readback.
vkq_path = "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanQuery.cpp"
v = read(vkq_path)
if '#include "diagnostics/RuntimeDiagnostics.h"\n' not in v:
    v = replace_once(v, '#include "Cafe/CafeSystem.h"\n', '#include "Cafe/CafeSystem.h"\n#include "diagnostics/RuntimeDiagnostics.h"\n', "Vulkan query diagnostic include")
v = replace_once(
    v,
    "\tuint32 newQueryIndex = acquireQueryIndex();\n",
    "\tuint32 newQueryIndex = acquireQueryIndex();\n"
    "\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GPUOcclusionQueryVisibility))\n"
    "\t\tcemuLog_log(LogType::Force, \"[QUERY_VIS] layer=VK event=FRAGMENT_BEGIN title={:016x} index={} cmd={}\", CafeSystem::GetForegroundTitleId(), newQueryIndex, m_rendererVk->GetCurrentCommandBufferId());\n",
    "Vulkan query fragment begin diagnostic",
)
v = replace_once(
    v,
    "\tuint32 queryIndex = list_queryFragments.back().queryIndex;\n\tvkCmdEndQuery",
    "\tuint32 queryIndex = list_queryFragments.back().queryIndex;\n"
    "\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GPUOcclusionQueryVisibility))\n"
    "\t\tcemuLog_log(LogType::Force, \"[QUERY_VIS] layer=VK event=FRAGMENT_END title={:016x} index={} cmd={}\", CafeSystem::GetForegroundTitleId(), queryIndex, m_rendererVk->GetCurrentCommandBufferId());\n"
    "\tvkCmdEndQuery",
    "Vulkan query fragment end diagnostic",
)
v = replace_once(
    v,
    "\t\t\tif (result == VK_NOT_READY)\n\t\t\t\tbreak;\n\t\t\tif (result == VK_SUCCESS)\n\t\t\t\tfragmentResult = directResult;",
    "\t\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GPUOcclusionQueryVisibility))\n"
    "\t\t\t\tcemuLog_log(LogType::Force, \"[QUERY_VIS] layer=VK event=DIRECT_READBACK title={:016x} index={} vkResult={} samples={}\", CafeSystem::GetForegroundTitleId(), it.queryIndex, (sint32)result, directResult);\n"
    "\t\t\tif (result == VK_NOT_READY)\n\t\t\t\tbreak;\n\t\t\tif (result == VK_SUCCESS)\n\t\t\t\tfragmentResult = directResult;",
    "Vulkan direct readback diagnostic",
)
v = replace_once(
    v,
    "\t\tm_acccumulatedSum += fragmentResult;\n\t\treleaseQueryIndex(it.queryIndex);",
    "\t\tm_acccumulatedSum += fragmentResult;\n"
    "\t\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GPUOcclusionQueryVisibility))\n"
    "\t\t\tcemuLog_log(LogType::Force, \"[QUERY_VIS] layer=VK event=FRAGMENT_RESULT title={:016x} index={} samples={} accumulated={}\", CafeSystem::GetForegroundTitleId(), it.queryIndex, fragmentResult, m_acccumulatedSum);\n"
    "\t\treleaseQueryIndex(it.queryIndex);",
    "Vulkan fragment result diagnostic",
)
v = replace_once(
    v,
    "\tnumSamplesPassed = m_acccumulatedSum;\n\t//numSamplesPassed = m_rendererVk->m_occlusionQueries.ptrQueryResults[m_queryIndex];\n\treturn true;",
    "\tnumSamplesPassed = m_acccumulatedSum;\n"
    "\tif (RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::GPUOcclusionQueryVisibility))\n"
    "\t\tcemuLog_log(LogType::Force, \"[QUERY_VIS] layer=VK event=GET_RESULT ready=1 title={:016x} samples={}\", CafeSystem::GetForegroundTitleId(), numSamplesPassed);\n"
    "\t//numSamplesPassed = m_rendererVk->m_occlusionQueries.ptrQueryResults[m_queryIndex];\n\treturn true;",
    "Vulkan final result diagnostic",
)
write(vkq_path, v)

checks = {
    hdr_path: ("PSInputLinkage", "GPUOcclusionQueryVisibility"),
    main_path: ("PS input linkage", "GPU occlusion/query visibility"),
    pc_path: ("[ADRENO_DIAG] PS_INPUT_LINK", "vsProducer={}"),
    gx2_path: ("[QUERY_VIS] layer=GX2", "event=PRED_BEGIN"),
    vkq_path: ("[QUERY_VIS] layer=VK", "event=DIRECT_READBACK"),
}
for path, tokens in checks.items():
    data = read(path)
    for token in tokens:
        if token not in data:
            raise RuntimeError(f"{path}: missing verification token {token}")

print("[targeted-diagnostics] PASS: PS input linkage + GPU occlusion/query visibility installed")
