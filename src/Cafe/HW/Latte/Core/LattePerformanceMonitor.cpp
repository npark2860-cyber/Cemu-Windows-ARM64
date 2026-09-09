#include "Cafe/HW/Latte/Core/LattePerformanceMonitor.h"
#include "Cafe/HW/Latte/Core/LatteOverlay.h"
#include "WindowSystem.h"
#include "config/ActiveSettings.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <string>
#include <string_view>
#include <system_error>

performanceMonitor_t performanceMonitor{};

namespace
{
constexpr uint64_t PERF_LOG_WINDOW_NS = 10'000'000'000ULL;
constexpr size_t PERF_LOG_MAX_FRAME_SAMPLES = 4096;

const char* PerfEnv(const char* name, const char* fallback)
{
	const char* value = std::getenv(name);
	return (value && value[0] != '\0') ? value : fallback;
}

bool PerfLogEnabled()
{
	static const bool enabled = []() {
		const char* raw = std::getenv("CEMU_EXPERIMENTS");
		if (!raw)
			return false;

		std::string_view experiments(raw);
		size_t start = 0;
		while (start < experiments.size())
		{
			while (start < experiments.size() && (experiments[start] == ',' || experiments[start] == ' ' || experiments[start] == '\t'))
				++start;
			if (start >= experiments.size())
				break;

			size_t end = experiments.find(',', start);
			if (end == std::string_view::npos)
				end = experiments.size();
			while (end > start && (experiments[end - 1] == ' ' || experiments[end - 1] == '\t'))
				--end;
			if (experiments.substr(start, end - start) == "perf-log")
				return true;
			start = end + 1;
		}
		return false;
	}();
	return enabled;
}

uint64_t PerfNowNs()
{
	return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
		std::chrono::steady_clock::now().time_since_epoch()).count());
}

struct PerfBenchmarkState
{
	bool started{};
	uint64_t runStartNs{};
	uint64_t windowStartNs{};
	uint64_t lastFrameNs{};
	uint64_t windowFrames{};
	uint64_t windowTotalUs{};
	uint64_t barrierSum{};
	uint64_t renderPassSum{};
	std::array<uint32_t, PERF_LOG_MAX_FRAME_SAMPLES> frameUs{};
	size_t frameSampleCount{};
	std::ofstream file;

	~PerfBenchmarkState()
	{
		if (file.is_open())
		{
			file << "===================== CEMU PERF TEST END =====================\n";
			file << "Preset      : " << PerfEnv("CEMU_PERF_PRESET", "UNSPECIFIED") << "\n";
			file << "Run ID      : " << PerfEnv("CEMU_PERF_RUN_ID", "manual") << "\n";
			file << "==============================================================\n";
			file.flush();
		}
	}
};

void PerfBenchmarkFrameEnd()
{
	if (!PerfLogEnabled())
		return;

	static PerfBenchmarkState state;
	const uint64_t nowNs = PerfNowNs();

	if (!state.started)
	{
		state.started = true;
		state.runStartNs = nowNs;
		state.windowStartNs = nowNs;
		state.lastFrameNs = nowNs;

		const char* preset = PerfEnv("CEMU_PERF_PRESET", "UNSPECIFIED");
		const char* runId = PerfEnv("CEMU_PERF_RUN_ID", "manual");
		const char* branch = PerfEnv("CEMU_PERF_BRANCH", "runtime-experiments-arm64");
		const char* experiments = PerfEnv("CEMU_EXPERIMENTS", "perf-log");

		cemuLog_log(LogType::Force, "==================== CEMU PERF TEST BEGIN ====================");
		cemuLog_log(LogType::Force, "[PERF_META] preset={} run={} branch={}", preset, runId, branch);
		cemuLog_log(LogType::Force, "[PERF_META] experiments={}", experiments);
		cemuLog_log(LogType::Force, "[PERF_META] sample_window=10s output=perf-logs/PERF_{}_{}.txt", runId, preset);
		cemuLog_log(LogType::Force, "==============================================================");

		std::error_code ec;
		auto perfDir = ActiveSettings::GetUserDataPath("perf-logs");
		std::filesystem::create_directories(perfDir, ec);
		const std::string fileName = std::string("PERF_") + runId + "_" + preset + ".txt";
		auto perfPath = perfDir / fileName;
		state.file.open(perfPath, std::ios::out | std::ios::trunc);
		if (state.file.is_open())
		{
			state.file << "==================== CEMU PERF TEST BEGIN ====================\n";
			state.file << "Preset      : " << preset << "\n";
			state.file << "Run ID      : " << runId << "\n";
			state.file << "Branch      : " << branch << "\n";
			state.file << "Experiments : " << experiments << "\n";
			state.file << "Window      : 10 seconds\n";
			state.file << "==============================================================\n";
			state.file.flush();
			cemuLog_log(LogType::Force, "[PERF_FILE] {}", perfPath.string());
		}
		else
		{
			cemuLog_log(LogType::Force, "[PERF_FILE] failed to create {}", perfPath.string());
		}
		return;
	}

	const uint64_t deltaNs = nowNs - state.lastFrameNs;
	state.lastFrameNs = nowNs;
	if (deltaNs == 0)
		return;

	const uint64_t frameUs64 = std::max<uint64_t>(1, deltaNs / 1000ULL);
	const uint32_t frameUs = static_cast<uint32_t>(std::min<uint64_t>(frameUs64, UINT32_MAX));
	if (state.frameSampleCount < state.frameUs.size())
		state.frameUs[state.frameSampleCount++] = frameUs;

	state.windowFrames++;
	state.windowTotalUs += frameUs64;
	state.barrierSum += performanceMonitor.vk.numDrawBarriersPerFrame.get();
	state.renderPassSum += performanceMonitor.vk.numBeginRenderpassPerFrame.get();

	if ((nowNs - state.windowStartNs) < PERF_LOG_WINDOW_NS || state.windowFrames == 0 || state.frameSampleCount == 0)
		return;

	auto sortedFrames = state.frameUs;
	std::sort(sortedFrames.begin(), sortedFrames.begin() + state.frameSampleCount);
	const size_t p99Rank = std::max<size_t>(1, (state.frameSampleCount * 99 + 99) / 100);
	const uint32_t p99Us = sortedFrames[p99Rank - 1];

	const double avgFrameUs = static_cast<double>(state.windowTotalUs) / static_cast<double>(state.windowFrames);
	const double avgFps = 1'000'000.0 / avgFrameUs;
	const double avgMs = avgFrameUs / 1000.0;
	const double p99Ms = static_cast<double>(p99Us) / 1000.0;
	const double low1Fps = p99Us != 0 ? 1'000'000.0 / static_cast<double>(p99Us) : 0.0;
	const double barriersPerFrame = static_cast<double>(state.barrierSum) / static_cast<double>(state.windowFrames);
	const double renderPassesPerFrame = static_cast<double>(state.renderPassSum) / static_cast<double>(state.windowFrames);
	const uint64_t elapsedSeconds = (nowNs - state.runStartNs) / 1'000'000'000ULL;

	const char* preset = PerfEnv("CEMU_PERF_PRESET", "UNSPECIFIED");
	const char* runId = PerfEnv("CEMU_PERF_RUN_ID", "manual");
	cemuLog_log(LogType::Force,
		"[PERF_SAMPLE] preset={} run={} t={}s frames={} avg_fps={:.3f} avg_ms={:.3f} p99_ms={:.3f} low1_fps={:.3f} barriers_pf={:.3f} renderpasses_pf={:.3f}",
		preset, runId, elapsedSeconds, state.windowFrames, avgFps, avgMs, p99Ms, low1Fps, barriersPerFrame, renderPassesPerFrame);

	if (state.file.is_open())
	{
		state.file << std::fixed << std::setprecision(3)
			<< "[PERF_SAMPLE] preset=" << preset
			<< " run=" << runId
			<< " t=" << elapsedSeconds << "s"
			<< " frames=" << state.windowFrames
			<< " avg_fps=" << avgFps
			<< " avg_ms=" << avgMs
			<< " p99_ms=" << p99Ms
			<< " low1_fps=" << low1Fps
			<< " barriers_pf=" << barriersPerFrame
			<< " renderpasses_pf=" << renderPassesPerFrame
			<< '\n';
		state.file.flush();
	}

	state.windowStartNs = nowNs;
	state.windowFrames = 0;
	state.windowTotalUs = 0;
	state.barrierSum = 0;
	state.renderPassSum = 0;
	state.frameSampleCount = 0;
}
}

void LattePerformanceMonitor_frameEnd()
{
	// per-frame stats
	performanceMonitor.gpuTime_shaderCreate.frameFinished();
	performanceMonitor.gpuTime_frameTime.frameFinished();
	performanceMonitor.gpuTime_idleTime.frameFinished();
	performanceMonitor.gpuTime_fenceTime.frameFinished();

	performanceMonitor.gpuTime_dcStageTextures.frameFinished();
	performanceMonitor.gpuTime_dcStageVertexMgr.frameFinished();
	performanceMonitor.gpuTime_dcStageShaderAndUniformMgr.frameFinished();
	performanceMonitor.gpuTime_dcStageIndexMgr.frameFinished();
	performanceMonitor.gpuTime_dcStageMRT.frameFinished();
	performanceMonitor.gpuTime_dcStageDrawcallAPI.frameFinished();
	performanceMonitor.gpuTime_waitForAsync.frameFinished();

	PerfBenchmarkFrameEnd();

	uint32 elapsedTime = GetTickCount() - performanceMonitor.cycle[performanceMonitor.cycleIndex].lastUpdate;
	if (elapsedTime >= 1000)
	{
		bool isFirstUpdate = performanceMonitor.cycle[performanceMonitor.cycleIndex].lastUpdate == 0;
		// sum up raw stats
		uint32 totalElapsedTime = GetTickCount() - performanceMonitor.cycle[(performanceMonitor.cycleIndex + 1) % PERFORMANCE_MONITOR_TRACK_CYCLES].lastUpdate;
		uint32 totalElapsedTimeFPS = GetTickCount() - performanceMonitor.cycle[(performanceMonitor.cycleIndex + PERFORMANCE_MONITOR_TRACK_CYCLES - 1) % PERFORMANCE_MONITOR_TRACK_CYCLES].lastUpdate;
		uint32 elapsedFrames = 0;
		uint32 elapsedFrames2S = 0; // elapsed frames for last two entries (seconds)
		uint64 skippedCycles = 0;
		uint64 vertexDataUploaded = 0;
		uint64 vertexDataCached = 0;
		uint64 uniformBankUploadedData = 0;
		uint64 uniformBankUploadedCount = 0;
		uint64 indexDataUploaded = 0;
		uint64 indexDataCached = 0;
		uint32 frameCounter = 0;
		uint32 drawCallCounter = 0;
		uint32 fastDrawCallCounter = 0;
		uint32 shaderBindCounter = 0;
		uint32 recompilerLeaveCount = 0;
		uint32 threadLeaveCount = 0;
		for (sint32 i = 0; i < PERFORMANCE_MONITOR_TRACK_CYCLES; i++)
		{
			elapsedFrames += performanceMonitor.cycle[i].frameCounter;
			skippedCycles += performanceMonitor.cycle[i].skippedCycles;
			vertexDataUploaded += performanceMonitor.cycle[i].vertexDataUploaded;
			vertexDataCached += performanceMonitor.cycle[i].vertexDataCached;
			uniformBankUploadedData += performanceMonitor.cycle[i].uniformBankUploadedData;
			uniformBankUploadedCount += performanceMonitor.cycle[i].uniformBankUploadedCount;
			indexDataUploaded += performanceMonitor.cycle[i].indexDataUploaded;
			indexDataCached += performanceMonitor.cycle[i].indexDataCached;
			frameCounter += performanceMonitor.cycle[i].frameCounter;
			drawCallCounter += performanceMonitor.cycle[i].drawCallCounter;
			fastDrawCallCounter += performanceMonitor.cycle[i].fastDrawCallCounter;
			shaderBindCounter += performanceMonitor.cycle[i].shaderBindCount;
			recompilerLeaveCount += performanceMonitor.cycle[i].recompilerLeaveCount;
			threadLeaveCount += performanceMonitor.cycle[i].threadLeaveCount;
		}
		elapsedFrames = std::max<uint32>(elapsedFrames, 1);
		elapsedFrames2S = performanceMonitor.cycle[(performanceMonitor.cycleIndex + PERFORMANCE_MONITOR_TRACK_CYCLES - 0) % PERFORMANCE_MONITOR_TRACK_CYCLES].frameCounter;
		elapsedFrames2S += performanceMonitor.cycle[(performanceMonitor.cycleIndex + PERFORMANCE_MONITOR_TRACK_CYCLES - 1) % PERFORMANCE_MONITOR_TRACK_CYCLES].frameCounter;
		elapsedFrames2S = std::max<uint32>(elapsedFrames2S, 1);
		// calculate stats
		uint64 passedCycles = PPCInterpreter_getMainCoreCycleCounter() - performanceMonitor.cycle[(performanceMonitor.cycleIndex + 1) % PERFORMANCE_MONITOR_TRACK_CYCLES].lastCycleCount;
		passedCycles -= skippedCycles;
		uint64 vertexDataUploadPerFrame = (vertexDataUploaded / (uint64)elapsedFrames);
		vertexDataUploadPerFrame /= 1024ULL;
		uint64 vertexDataCachedPerFrame = (vertexDataCached / (uint64)elapsedFrames);
		vertexDataCachedPerFrame /= 1024ULL;
		uint64 uniformBankDataUploadedPerFrame = (uniformBankUploadedData / (uint64)elapsedFrames);
		uniformBankDataUploadedPerFrame /= 1024ULL;
		uint32 uniformBankCountUploadedPerFrame = (uint32)(uniformBankUploadedCount / (uint64)elapsedFrames);
		uint64 indexDataUploadPerFrame = (indexDataUploaded / (uint64)elapsedFrames);

		double fps = (double)elapsedFrames2S * 1000.0 / (double)totalElapsedTimeFPS;
		uint32 shaderBindsPerFrame = shaderBindCounter / elapsedFrames;
		passedCycles = passedCycles * 1000ULL / totalElapsedTime;
		uint32 rlps = (uint32)((uint64)recompilerLeaveCount * 1000ULL / (uint64)totalElapsedTime);
		uint32 tlps = (uint32)((uint64)threadLeaveCount * 1000ULL / (uint64)totalElapsedTime);
		// set stats
		performanceMonitor.stats.indexDataUploadPerFrame = indexDataUploadPerFrame;
		// next counter cycle
		sint32 nextCycleIndex = (performanceMonitor.cycleIndex + 1) % PERFORMANCE_MONITOR_TRACK_CYCLES;
		performanceMonitor.cycle[nextCycleIndex].drawCallCounter = 0;
		performanceMonitor.cycle[nextCycleIndex].fastDrawCallCounter = 0;
		performanceMonitor.cycle[nextCycleIndex].frameCounter = 0;
		performanceMonitor.cycle[nextCycleIndex].shaderBindCount = 0;
		performanceMonitor.cycle[nextCycleIndex].lastCycleCount = PPCInterpreter_getMainCoreCycleCounter();
		performanceMonitor.cycle[nextCycleIndex].skippedCycles = 0;
		performanceMonitor.cycle[nextCycleIndex].vertexDataUploaded = 0;
		performanceMonitor.cycle[nextCycleIndex].vertexDataCached = 0;
		performanceMonitor.cycle[nextCycleIndex].uniformBankUploadedData = 0;
		performanceMonitor.cycle[nextCycleIndex].uniformBankUploadedCount = 0;
		performanceMonitor.cycle[nextCycleIndex].indexDataUploaded = 0;
		performanceMonitor.cycle[nextCycleIndex].indexDataCached = 0;
		performanceMonitor.cycle[nextCycleIndex].recompilerLeaveCount = 0;
		performanceMonitor.cycle[nextCycleIndex].threadLeaveCount = 0;
		performanceMonitor.cycleIndex = nextCycleIndex;

		// next update in 1 second
		performanceMonitor.cycle[performanceMonitor.cycleIndex].lastUpdate = GetTickCount();

		if (isFirstUpdate)
		{
			LatteOverlay_updateStats(0.0, 0, 0);
			WindowSystem::UpdateWindowTitles(false, false, 0.0);
		}
		else
		{
			LatteOverlay_updateStats(fps, drawCallCounter / elapsedFrames, fastDrawCallCounter / elapsedFrames);
			WindowSystem::UpdateWindowTitles(false, false, fps);
		}
	}
}

void LattePerformanceMonitor_frameBegin()
{
	performanceMonitor.vk.numDrawBarriersPerFrame.reset();
	performanceMonitor.vk.numBeginRenderpassPerFrame.reset();
}
