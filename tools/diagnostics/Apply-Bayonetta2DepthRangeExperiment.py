from pathlib import Path
import re

path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
text = path.read_text(encoding="utf-8")

pattern = re.compile(
    r"void VulkanRenderer::renderTarget_setViewport\(float x, float y, float width, float height, float nearZ, float farZ, bool halfZ\)\n"
    r"\{\n"
    r"\t// the Vulkan renderer handles halfZ in the vertex shader\n\n"
    r"\tfloat vpNewX = x;\n"
    r"\tfloat vpNewY = y \+ height;\n"
    r"\tfloat vpNewWidth = width;\n"
    r"\tfloat vpNewHeight = -height;\n\n"
    r"\tif \(m_state\.currentViewport\.x == vpNewX && m_state\.currentViewport\.y == vpNewY && m_state\.currentViewport\.width == vpNewWidth && m_state\.currentViewport\.height == vpNewHeight && m_state\.currentViewport\.minDepth == nearZ && m_state\.currentViewport\.maxDepth == farZ\)\n"
    r"\t\treturn; // viewport did not change\n\n"
    r"\tm_state\.currentViewport\.x = vpNewX;\n"
    r"\tm_state\.currentViewport\.y = vpNewY;\n"
    r"\tm_state\.currentViewport\.width = vpNewWidth;\n"
    r"\tm_state\.currentViewport\.height = vpNewHeight;\n\n"
    r"\tm_state\.currentViewport\.minDepth = nearZ;\n"
    r"\tm_state\.currentViewport\.maxDepth = farZ;\n\n"
    r"\tvkCmdSetViewport\(m_state\.currentCommandBuffer, 0, 1, &m_state\.currentViewport\);\n"
    r"\}\n"
)

replacement = r'''void VulkanRenderer::renderTarget_setViewport(float x, float y, float width, float height, float nearZ, float farZ, bool halfZ)
{
	// the Vulkan renderer handles halfZ in the vertex shader

	float vpNewX = x;
	float vpNewY = y + height;
	float vpNewWidth = width;
	float vpNewHeight = -height;

	float appliedNearZ = nearZ;
	float appliedFarZ = farZ;
	const uint64 titleId = CafeSystem::GetForegroundTitleId();
	const bool isBayonetta2 =
		titleId == 0x0005000010172600ULL || // USA
		titleId == 0x0005000010172700ULL || // EUR
		titleId == 0x000500001011B900ULL;   // JPN

	if (isBayonetta2)
	{
		auto clampDepth = [](float v) -> float
		{
			if (v < 0.0f)
				return 0.0f;
			if (v > 1.0f)
				return 1.0f;
			return v;
		};

		const bool outOfRange = nearZ < 0.0f || nearZ > 1.0f || farZ < 0.0f || farZ > 1.0f;
		if (outOfRange)
		{
			appliedNearZ = clampDepth(nearZ);
			appliedFarZ = clampDepth(farZ);
		}

		static uint32 s_bayo2DepthRangeLogCount = 0;
		if (s_bayo2DepthRangeLogCount < 128 || outOfRange)
		{
			cemuLog_log(LogType::Force,
				"[BAYO2_DEPTH_RANGE] n={} rawNear={} rawFar={} appliedNear={} appliedFar={} halfZ={} clamped={}",
				s_bayo2DepthRangeLogCount, nearZ, farZ, appliedNearZ, appliedFarZ, halfZ ? 1 : 0, outOfRange ? 1 : 0);
			s_bayo2DepthRangeLogCount++;
		}
	}

	if (m_state.currentViewport.x == vpNewX && m_state.currentViewport.y == vpNewY && m_state.currentViewport.width == vpNewWidth && m_state.currentViewport.height == vpNewHeight && m_state.currentViewport.minDepth == appliedNearZ && m_state.currentViewport.maxDepth == appliedFarZ)
		return; // viewport did not change

	m_state.currentViewport.x = vpNewX;
	m_state.currentViewport.y = vpNewY;
	m_state.currentViewport.width = vpNewWidth;
	m_state.currentViewport.height = vpNewHeight;

	m_state.currentViewport.minDepth = appliedNearZ;
	m_state.currentViewport.maxDepth = appliedFarZ;

	vkCmdSetViewport(m_state.currentCommandBuffer, 0, 1, &m_state.currentViewport);
}
'''

new_text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit(f"Expected exactly one renderTarget_setViewport match, found {count}")

path.write_text(new_text, encoding="utf-8")
print("[bayo2-depth-range] patched VulkanRenderer.cpp")
print("[bayo2-depth-range] Bayonetta 2 only: clamp out-of-range viewport depth values to [0,1]")
print("[bayo2-depth-range] log marker: [BAYO2_DEPTH_RANGE]")
