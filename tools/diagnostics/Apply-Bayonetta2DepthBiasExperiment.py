from pathlib import Path
import re

path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
text = path.read_text(encoding="utf-8")

pattern = re.compile(
    r"\tfloat frontScale = LatteGPUState\.contextNew\.PA_SU_POLY_OFFSET_FRONT_SCALE\.get_SCALE\(\);\n"
    r"\tfloat frontOffset = LatteGPUState\.contextNew\.PA_SU_POLY_OFFSET_FRONT_OFFSET\.get_OFFSET\(\);\n"
    r"\tfloat offsetClamp = LatteGPUState\.contextNew\.PA_SU_POLY_OFFSET_CLAMP\.get_CLAMP\(\);\n\n"
    r"\tfrontScale /= 16\.0f;\n\n"
    r"\tvkCmdSetDepthBias\(m_state\.currentCommandBuffer, frontOffset, offsetClamp, frontScale\);\n"
)

replacement = r'''\tfloat frontScale = LatteGPUState.contextNew.PA_SU_POLY_OFFSET_FRONT_SCALE.get_SCALE();
\tfloat frontOffset = LatteGPUState.contextNew.PA_SU_POLY_OFFSET_FRONT_OFFSET.get_OFFSET();
\tfloat offsetClamp = LatteGPUState.contextNew.PA_SU_POLY_OFFSET_CLAMP.get_CLAMP();

\tfrontScale /= 16.0f;

\tfloat appliedClamp = offsetClamp;
\tconst uint64 titleId = CafeSystem::GetForegroundTitleId();
\tconst bool isBayonetta2 =
\t\ttitleId == 0x0005000010172600ULL || // USA
\t\ttitleId == 0x0005000010172700ULL || // EUR
\t\ttitleId == 0x000500001011B900ULL;   // JPN

\tif (isBayonetta2)
\t{
\t\t// A/B experiment: match Cemu's OpenGL behavior, which currently ignores
\t\t// PA_SU_POLY_OFFSET_CLAMP and calls glPolygonOffset(factor, units).
\t\tappliedClamp = 0.0f;

\t\tstatic uint64 s_bayo2DepthBiasCalls = 0;
\t\tstatic uint64 s_bayo2NonZeroClampCalls = 0;
\t\tconst bool nonZeroClamp = offsetClamp != 0.0f;
\t\tif (nonZeroClamp)
\t\t\ts_bayo2NonZeroClampCalls++;

\t\tconst bool shouldLog =
\t\t\ts_bayo2DepthBiasCalls < 128 ||
\t\t\t(nonZeroClamp && (s_bayo2NonZeroClampCalls <= 512 || (s_bayo2NonZeroClampCalls % 10000) == 0));
\t\tif (shouldLog)
\t\t{
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[BAYO2_DEPTH_BIAS] n={} offset={} slope={} rawClamp={} appliedClamp={} nonZeroClampCount={}",
\t\t\t\ts_bayo2DepthBiasCalls, frontOffset, frontScale, offsetClamp, appliedClamp, s_bayo2NonZeroClampCalls);
\t\t}
\t\ts_bayo2DepthBiasCalls++;
\t}

\tvkCmdSetDepthBias(m_state.currentCommandBuffer, frontOffset, appliedClamp, frontScale);
'''

new_text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit(f"Expected exactly one depth-bias block match, found {count}")

path.write_text(new_text, encoding="utf-8")
print("[bayo2-depth-bias] patched VulkanRendererCore.cpp")
print("[bayo2-depth-bias] Bayonetta 2 only: force Vulkan depthBiasClamp to 0.0")
print("[bayo2-depth-bias] OpenGL parity A/B; offset and slope remain unchanged")
print("[bayo2-depth-bias] log marker: [BAYO2_DEPTH_BIAS]")
