from pathlib import Path

AX_PATH = Path("src/Cafe/OS/libs/snd_core/ax_voice.cpp")
DIAG_PATH = Path("src/Cafe/OS/common/EnhancedSoundCueDiagnostic.h")

text = AX_PATH.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    text = text.replace(old, new, 1)


replace_once(
    '#include "Cafe/OS/common/EnhancedSoundDualSenseService.h"\n',
    '#include "Cafe/OS/common/EnhancedSoundDualSenseService.h"\n'
    '#include "Cafe/OS/common/EnhancedSoundCueDiagnostic.h"\n',
    "diagnostic include",
)

old = r'''			const auto sources = EnhancedSoundSourceTracker::ResolveSourceCandidates(sampleBase);
			bool unanimousRoute = !sources.empty();
			for (const auto& source : sources)
			{
				const auto resolved = EnhancedSoundRouter::Resolve(source.path, source.trackName);
'''
new = r'''			const auto sources = EnhancedSoundSourceTracker::ResolveSourceCandidates(sampleBase);
			if (sources.empty())
			{
				EnhancedSoundCueDiagnostic::Record(
					static_cast<uint32>(vpb->index),
					vpb->playbackState == (uint32be)1 ? 1u : 0u,
					sampleBase, 0u, 0u, false, {}, {}, false, 0u, 0u);
			}
			bool unanimousRoute = !sources.empty();
			for (size_t sourceIndex = 0; sourceIndex < sources.size(); ++sourceIndex)
			{
				const auto& source = sources[sourceIndex];
				const auto resolved = EnhancedSoundRouter::Resolve(source.path, source.trackName);
				EnhancedSoundCueDiagnostic::Record(
					static_cast<uint32>(vpb->index),
					vpb->playbackState == (uint32be)1 ? 1u : 0u,
					sampleBase, static_cast<uint32>(sourceIndex), static_cast<uint32>(sources.size()),
					true, source.path, source.trackName, resolved.has_value(),
					resolved ? static_cast<uint32>(resolved->mode) : 0u,
					resolved ? resolved->gain : 0u);
'''
replace_once(old, new, "candidate capture")

header = r'''#pragma once

#include <chrono>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <mutex>
#include <sstream>
#include <string>
#include <string_view>

namespace EnhancedSoundCueDiagnostic
{
	inline std::mutex s_mutex;
	inline std::ofstream s_csv;
	inline uint64_t s_sequence = 0;
	inline uint32_t s_linesSinceFlush = 0;

	inline std::string CsvQuote(std::string_view value)
	{
		std::string out = "\"";
		for (const char c : value)
		{
			if (c == '"')
				out += "\"\"";
			else if (c == '\r' || c == '\n')
				out += ' ';
			else
				out += c;
		}
		out += '"';
		return out;
	}

	inline std::string Hex32(uint32_t value)
	{
		std::ostringstream ss;
		ss << "0x" << std::hex << std::setw(8) << std::setfill('0') << value;
		return ss.str();
	}

	inline void EnsureOpenLocked()
	{
		if (s_csv.is_open())
			return;

		bool hasData = false;
		{
			std::ifstream existing("enhanced_sound_cue_capture.csv", std::ios::binary | std::ios::ate);
			if (existing)
				hasData = existing.tellg() > 0;
		}
		s_csv.open("enhanced_sound_cue_capture.csv", std::ios::out | std::ios::app);
		if (!hasData && s_csv)
		{
			s_csv << "sequence,time_us,voice,playback,sample_base,candidate_index,candidate_count,source_found,source_path,track_name,route_match,route_mode,gain\n";
			s_csv.flush();
		}
	}

	inline void Record(uint32_t voiceIndex, uint32_t playbackState, uint32_t sampleBase,
		uint32_t candidateIndex, uint32_t candidateCount, bool sourceFound,
		std::string_view sourcePath, std::string_view trackName, bool routeMatched,
		uint32_t routeMode, uint32_t gain)
	{
		std::scoped_lock lock(s_mutex);
		EnsureOpenLocked();
		if (!s_csv)
			return;

		const auto nowUs = std::chrono::duration_cast<std::chrono::microseconds>(
			std::chrono::steady_clock::now().time_since_epoch()).count();
		const char* modeName = "none";
		if (routeMatched)
		{
			if (routeMode == 1)
				modeName = "add_drc";
			else if (routeMode == 2)
				modeName = "spatial_drc";
			else
				modeName = "other";
		}

		s_csv << ++s_sequence << ',' << nowUs << ',' << voiceIndex << ',' << playbackState << ','
			<< Hex32(sampleBase) << ',' << candidateIndex << ',' << candidateCount << ','
			<< (sourceFound ? 1 : 0) << ',' << CsvQuote(sourcePath) << ',' << CsvQuote(trackName) << ','
			<< (routeMatched ? 1 : 0) << ',' << modeName << ',' << gain << '\n';

		if (++s_linesSinceFlush >= 16 || routeMatched)
		{
			s_csv.flush();
			s_linesSinceFlush = 0;
		}
	}
}
'''

DIAG_PATH.write_text(header, encoding="utf-8")
AX_PATH.write_text(text, encoding="utf-8")
print("Enhanced Sound V2 cue capture instrumentation applied")
