#pragma once

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
