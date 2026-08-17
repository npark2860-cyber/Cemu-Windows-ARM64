$ErrorActionPreference = 'Stop'

function Replace-Required([string]$Text, [string]$Old, [string]$New, [string]$Label)
{
    if (-not $Text.Contains($Old))
    {
        throw "Runtime experiment patch failed: $Label"
    }
    return $Text.Replace($Old, $New)
}

Write-Host '[runtime-experiments] Installing reusable diagnostics header'
$headerPath = 'src/diagnostics/RuntimeExperiments.h'
New-Item -ItemType Directory -Force -Path (Split-Path $headerPath) | Out-Null
@'
#pragma once

#include <atomic>
#include <cctype>
#include <cstdlib>
#include <string>
#include <string_view>

namespace RuntimeExperiments
{
inline std::atomic_bool g_depthClipFeatureEnabled{false};

inline const std::string& Raw()
{
    static const std::string value = []() {
        const char* env = std::getenv("CEMU_EXPERIMENTS");
        return env ? std::string(env) : std::string{};
    }();
    return value;
}

inline bool Enabled(std::string_view name)
{
    const std::string& raw = Raw();
    size_t start = 0;
    while (start < raw.size())
    {
        while (start < raw.size() && (raw[start] == ',' || std::isspace(static_cast<unsigned char>(raw[start]))))
            ++start;
        if (start >= raw.size())
            break;

        size_t end = raw.find(',', start);
        if (end == std::string::npos)
            end = raw.size();

        size_t tokenEnd = end;
        while (tokenEnd > start && std::isspace(static_cast<unsigned char>(raw[tokenEnd - 1])))
            --tokenEnd;

        if (std::string_view(raw).substr(start, tokenEnd - start) == name)
            return true;
        start = end + 1;
    }
    return false;
}

inline void SetDepthClipFeatureEnabled(bool enabled)
{
    g_depthClipFeatureEnabled.store(enabled, std::memory_order_relaxed);
}

inline bool DepthClipFeatureEnabled()
{
    return g_depthClipFeatureEnabled.load(std::memory_order_relaxed);
}
}
'@ | Set-Content -Path $headerPath -NoNewline

Write-Host '[runtime-experiments] Patching PPCTimer experiments'
$timerPath = 'src/Cafe/HW/Espresso/PPCTimer.cpp'
$t = Get-Content $timerPath -Raw
$t = Replace-Required $t '#include "Common/cpu_features.h"' "#include \"Common/cpu_features.h\"`n#include \"diagnostics/RuntimeExperiments.h\"" 'PPCTimer include anchor'

$timerPattern = '(?ms)// thread safe\r?\nuint64 PPCTimer_getFromRDTSC\(\)\r?\n\{.*?\r?\n\}\s*$'
if (-not [regex]::IsMatch($t, $timerPattern))
{
    throw 'Runtime experiment patch failed: PPCTimer_getFromRDTSC block'
}
$timerReplacement = @'
// Runtime experiment counters are intentionally dormant unless timer-stats is enabled.
static std::atomic<uint64> sTimerStatCalls{0};
static std::atomic<uint64> sTimerStatHighZero{0};
static std::atomic<uint64> sTimerStatHighNonZero{0};
static std::atomic<uint64> sTimerStatContended{0};
static std::atomic<uint64> sTimerStatFast64{0};
static std::atomic<uint64> sTimerStatSlow128{0};

static void PPCTimer_logExperimentStats(uint64 calls)
{
    cemuLog_log(LogType::Force,
        "[PERF] PPCTimer calls={} high0={} highNZ={} contended={} fast64={} slow128={}",
        calls,
        sTimerStatHighZero.load(std::memory_order_relaxed),
        sTimerStatHighNonZero.load(std::memory_order_relaxed),
        sTimerStatContended.load(std::memory_order_relaxed),
        sTimerStatFast64.load(std::memory_order_relaxed),
        sTimerStatSlow128.load(std::memory_order_relaxed));
}

// thread safe
uint64 PPCTimer_getFromRDTSC()
{
    static const bool expStats = RuntimeExperiments::Enabled("timer-stats");
    static const bool expFast64 = RuntimeExperiments::Enabled("timer-udiv64");
    static const bool expNoExtraFence = RuntimeExperiments::Enabled("timer-no-extra-fence");
    static const bool expArm64Serialize = RuntimeExperiments::Enabled("timer-arm64-serialize");

    if (expStats)
    {
        if (!sTimerSpinlock.try_lock())
        {
            sTimerStatContended.fetch_add(1, std::memory_order_relaxed);
            sTimerSpinlock.lock();
        }
    }
    else
    {
        sTimerSpinlock.lock();
    }

#if defined(__aarch64__)
    if (expArm64Serialize)
        asm volatile("isb" ::: "memory");
    else if (!expNoExtraFence)
        _mm_mfence();
#else
    if (!expNoExtraFence)
        _mm_mfence();
#endif

    uint64 rdtscCurrentMeasure = __rdtsc();
    uint64 rdtscDif = rdtscCurrentMeasure - _rdtscLastMeasure;
    // optimized max(rdtscDif, 0) without conditionals
    rdtscDif = rdtscDif & ~(uint64)((sint64)rdtscDif >> 63);

    uint128_t diff{};
    diff.low = _umul128(rdtscDif, Espresso::CORE_CLOCK, &diff.high);

    if(rdtscCurrentMeasure > _rdtscLastMeasure)
        _rdtscLastMeasure = rdtscCurrentMeasure; // only travel forward in time

    uint8 c = 0;
#if BOOST_OS_WINDOWS
    c = _addcarry_u64(c, _rdtscAcc.low, diff.low, &_rdtscAcc.low);
    _addcarry_u64(c, _rdtscAcc.high, diff.high, &_rdtscAcc.high);
#else
    // requires casting because of long / long long nonesense
    c = _addcarry_u64(c, _rdtscAcc.low, diff.low, (unsigned long long*)&_rdtscAcc.low);
    _addcarry_u64(c, _rdtscAcc.high, diff.high, (unsigned long long*)&_rdtscAcc.high);
#endif

    const bool highIsZero = _rdtscAcc.high == 0;
    if (expStats)
    {
        if (highIsZero)
            sTimerStatHighZero.fetch_add(1, std::memory_order_relaxed);
        else
            sTimerStatHighNonZero.fetch_add(1, std::memory_order_relaxed);
    }

    uint64 remainder;
    uint64 elapsedTick;
    if (expFast64 && highIsZero)
    {
        elapsedTick = _rdtscAcc.low / _rdtscFrequency;
        remainder = _rdtscAcc.low % _rdtscFrequency;
        if (expStats)
            sTimerStatFast64.fetch_add(1, std::memory_order_relaxed);
    }
    else
    {
        elapsedTick = _udiv128(_rdtscAcc.high, _rdtscAcc.low, _rdtscFrequency, &remainder);
        if (expStats)
            sTimerStatSlow128.fetch_add(1, std::memory_order_relaxed);
    }

    _rdtscAcc.low = remainder;
    _rdtscAcc.high = 0;

    // timer scaling
    elapsedTick <<= 3ull; // *8
    uint8 timerShiftFactor = ActiveSettings::GetTimerShiftFactor();
    elapsedTick >>= timerShiftFactor;

    _tickSummary += elapsedTick;

    uint64 statsReturnValue = 0;
    uint64 statsCalls = 0;
    bool logStats = false;
    if (expStats)
    {
        statsReturnValue = _tickSummary;
        statsCalls = sTimerStatCalls.fetch_add(1, std::memory_order_relaxed) + 1;
        logStats = (statsCalls % 5000000ULL) == 0;
    }

    sTimerSpinlock.unlock();

    if (logStats)
        PPCTimer_logExperimentStats(statsCalls);

    // Preserve the original unlocked read unless stats mode is explicitly enabled.
    return expStats ? statsReturnValue : _tickSummary;
}
'@
$t = [regex]::Replace($t, $timerPattern, $timerReplacement, 1)
Set-Content -Path $timerPath -Value $t -NoNewline

Write-Host '[runtime-experiments] Patching Vulkan device feature experiment'
$rendererPath = 'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp'
$v = Get-Content $rendererPath -Raw
$v = Replace-Required $v '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"' "#include \"Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h\"`n#include \"diagnostics/RuntimeExperiments.h\"" 'VulkanRenderer include anchor'
$v = Replace-Required $v "`tGetDeviceFeatures();" "`tGetDeviceFeatures();`n`tif (!RuntimeExperiments::Raw().empty())`n`t`t cemuLog_log(LogType::Force, \"[EXPERIMENT] Active: {}\", RuntimeExperiments::Raw());" 'experiment startup log anchor'

$deviceAnchor = "`tvoid* deviceExtensionFeatures = nullptr;"
$deviceBlock = @'
	VkPhysicalDeviceDepthClipEnableFeaturesEXT depthClipEnableFeature{};
	bool depthClipFeatureUsable = false;
	if (RuntimeExperiments::Enabled("depthclip-feature") && m_featureControl.deviceExtensions.depth_clip_enable)
	{
		depthClipEnableFeature.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DEPTH_CLIP_ENABLE_FEATURES_EXT;
		VkPhysicalDeviceFeatures2 depthClipFeatures2{};
		depthClipFeatures2.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2;
		depthClipFeatures2.pNext = &depthClipEnableFeature;
		vkGetPhysicalDeviceFeatures2(m_physicalDevice, &depthClipFeatures2);
		depthClipFeatureUsable = depthClipEnableFeature.depthClipEnable == VK_TRUE;
		RuntimeExperiments::SetDepthClipFeatureEnabled(depthClipFeatureUsable);
		cemuLog_log(LogType::Force, "[EXPERIMENT] depthClipEnable feature: {}", depthClipFeatureUsable ? "supported/enabled" : "unsupported");
	}
	else
	{
		RuntimeExperiments::SetDepthClipFeatureEnabled(false);
	}

	void* deviceExtensionFeatures = nullptr;
	if (depthClipFeatureUsable)
	{
		depthClipEnableFeature.pNext = deviceExtensionFeatures;
		deviceExtensionFeatures = &depthClipEnableFeature;
		depthClipEnableFeature.depthClipEnable = VK_TRUE;
	}
'@
$v = Replace-Required $v $deviceAnchor $deviceBlock 'device extension feature chain anchor'
Set-Content -Path $rendererPath -Value $v -NoNewline

Write-Host '[runtime-experiments] Patching Vulkan pipeline switches'
$pipelinePath = 'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp'
$p = Get-Content $pipelinePath -Raw
$p = Replace-Required $p '#include "Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h"' "#include \"Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.h\"`n#include \"diagnostics/RuntimeExperiments.h\"" 'PipelineCompiler include anchor'

$oldRasterPNext = "`trasterizer.pNext = VulkanRenderer::GetInstance()->m_featureControl.deviceExtensions.depth_clip_enable ? &rasterizerExt : nullptr;"
$newRasterPNext = @'
	bool useDepthClipPNext = VulkanRenderer::GetInstance()->m_featureControl.deviceExtensions.depth_clip_enable;
	if (RuntimeExperiments::Enabled("depthclip-feature"))
		useDepthClipPNext = RuntimeExperiments::DepthClipFeatureEnabled();
	if (RuntimeExperiments::Enabled("depthclip-off") || RuntimeExperiments::Enabled("raster-pnext-off"))
		useDepthClipPNext = false;
	rasterizer.pNext = useDepthClipPNext ? &rasterizerExt : nullptr;
'@
$p = Replace-Required $p $oldRasterPNext $newRasterPNext 'rasterizer pNext anchor'
$p = Replace-Required $p "`trasterizer.depthClampEnable = VK_TRUE; // depth clamping is always enabled" "`trasterizer.depthClampEnable = RuntimeExperiments::Enabled(\"depthclamp-off\") ? VK_FALSE : VK_TRUE; // experiment switch, default unchanged" 'depth clamp anchor'

$feedbackOld = 'if (vkRenderer->m_featureControl.deviceExtensions.pipeline_feedback)'
$feedbackCount = ([regex]::Matches($p, [regex]::Escape($feedbackOld))).Count
if ($feedbackCount -ne 2)
{
    throw "Runtime experiment patch failed: expected 2 pipeline_feedback anchors, found $feedbackCount"
}
$p = $p.Replace($feedbackOld, 'if (vkRenderer->m_featureControl.deviceExtensions.pipeline_feedback && !RuntimeExperiments::Enabled("pipeline-feedback-off"))')
$p = Replace-Required $p "`tpipelineInfo.pNext = prevStruct;" "`tpipelineInfo.pNext = RuntimeExperiments::Enabled(\"pipeline-pnext-off\") ? nullptr : prevStruct;" 'graphics pipeline pNext anchor'
Set-Content -Path $pipelinePath -Value $p -NoNewline

Write-Host '[runtime-experiments] Patch summary'
git diff -- $headerPath $timerPath $rendererPath $pipelinePath
