#pragma once

#include "Cafe/HW/MMU/MMU.h"

#include <algorithm>
#include <chrono>
#include <cctype>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <limits>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

namespace BotWSoundSourceTracer
{
	struct ReadRange
	{
		uint32 fileHandle{};
		uint32 start{};
		uint32 size{};
		uint64 sequence{};
		std::string path;
	};

	struct SourceMatch
	{
		uint32 start{};
		uint32 size{};
		uint32 offset{};
		std::string path;
		std::string trackName;
	};

	inline std::mutex s_mutex;
	inline std::unordered_map<uint32, std::string> s_openSoundFiles;
	inline std::vector<ReadRange> s_readRanges;
	inline uint64 s_sequence = 0;
	inline std::ofstream s_csv;
	inline uint32 s_linesSinceFlush = 0;

	inline std::string ToLower(std::string_view input)
	{
		std::string out(input);
		std::transform(out.begin(), out.end(), out.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
		return out;
	}

	inline bool IsInterestingSoundPath(std::string_view path)
	{
		const std::string lower = ToLower(path);
		if (lower.find("sound/") == std::string::npos && lower.find("sound\\") == std::string::npos)
			return false;
		return lower.ends_with(".bars") || lower.ends_with(".bfwav") || lower.ends_with(".bfstp");
	}

	inline uint16 ReadU16(const uint8* p, bool bigEndian)
	{
		if (bigEndian)
			return static_cast<uint16>((static_cast<uint16>(p[0]) << 8) | p[1]);
		return static_cast<uint16>(p[0] | (static_cast<uint16>(p[1]) << 8));
	}

	inline uint32 ReadU32(const uint8* p, bool bigEndian)
	{
		if (bigEndian)
		{
			return (static_cast<uint32>(p[0]) << 24) |
				(static_cast<uint32>(p[1]) << 16) |
				(static_cast<uint32>(p[2]) << 8) |
				static_cast<uint32>(p[3]);
		}
		return static_cast<uint32>(p[0]) |
			(static_cast<uint32>(p[1]) << 8) |
			(static_cast<uint32>(p[2]) << 16) |
			(static_cast<uint32>(p[3]) << 24);
	}

	inline bool HasMagic(const uint8* p, const char* magic)
	{
		return p[0] == static_cast<uint8>(magic[0]) && p[1] == static_cast<uint8>(magic[1]) &&
			p[2] == static_cast<uint8>(magic[2]) && p[3] == static_cast<uint8>(magic[3]);
	}

	inline std::string ParseBarsTrackName(const ReadRange& range, uint32 sampleBase)
	{
		if (range.size < 32 || sampleBase < range.start)
			return {};
		const uint64 rangeEnd = static_cast<uint64>(range.start) + range.size;
		if (sampleBase >= rangeEnd)
			return {};
		if (!memory_isAddressRangeAccessible(range.start, std::min<uint32>(range.size, 64)))
			return {};

		const uint8* base = memory_getPointerFromVirtualOffset(range.start);
		if (!HasMagic(base, "BARS"))
			return {};

		const bool bigEndian = base[8] == 0xFE;
		if (!bigEndian && base[8] != 0xFF)
			return {};

		const uint32 count = ReadU32(base + 12, bigEndian);
		if (count == 0 || count > 16384)
			return {};

		const uint64 offsetTableEnd = 16ull + static_cast<uint64>(count) * 12ull;
		if (offsetTableEnd > range.size || !memory_isAddressRangeAccessible(range.start, static_cast<uint32>(offsetTableEnd)))
			return {};

		uint32 archiveSize = ReadU32(base + 4, bigEndian);
		if (archiveSize < offsetTableEnd || archiveSize > range.size)
			archiveSize = range.size;

		const uint32 sampleOffset = sampleBase - range.start;
		if (sampleOffset >= archiveSize)
			return {};

		const uint32 pairsOffset = 16 + count * 4;
		uint32 selected = std::numeric_limits<uint32>::max();
		uint32 selectedTrackOffset = 0;
		for (uint32 i = 0; i < count; ++i)
		{
			const uint32 trackOffset = ReadU32(base + pairsOffset + i * 8 + 4, bigEndian);
			if (trackOffset <= sampleOffset && trackOffset >= selectedTrackOffset && trackOffset < archiveSize)
			{
				selected = i;
				selectedTrackOffset = trackOffset;
			}
		}
		if (selected == std::numeric_limits<uint32>::max())
			return {};

		const uint32 amtaOffset = ReadU32(base + pairsOffset + selected * 8, bigEndian);
		if (amtaOffset > archiveSize || archiveSize - amtaOffset < 36)
			return {};

		auto within = [archiveSize](uint64 pos, uint64 length) {
			return pos <= archiveSize && length <= archiveSize - pos;
		};

		uint64 pos = amtaOffset;
		if (!within(pos, 6) || !HasMagic(base + pos, "AMTA"))
			return {};
		const bool amtaBigEndian = base[pos + 4] == 0xFE;
		if (!amtaBigEndian && base[pos + 4] != 0xFF)
			return {};
		pos += 28; // AMTA + BOM + fixed header fields.

		auto skipChunk = [&](const char* magic) -> bool {
			if (!within(pos, 8) || !HasMagic(base + pos, magic))
				return false;
			const uint32 length = ReadU32(base + pos + 4, amtaBigEndian);
			pos += 8;
			if (!within(pos, length))
				return false;
			pos += length;
			return true;
		};

		if (!skipChunk("DATA") || !skipChunk("MARK") || !skipChunk("EXT_"))
			return {};
		if (!within(pos, 8) || !HasMagic(base + pos, "STRG"))
			return {};
		const uint32 stringLength = ReadU32(base + pos + 4, amtaBigEndian);
		pos += 8;
		if (stringLength == 0 || stringLength > 4096 || !within(pos, stringLength))
			return {};

		std::string name(reinterpret_cast<const char*>(base + pos), stringLength);
		while (!name.empty() && name.back() == '\0')
			name.pop_back();
		return name;
	}

	inline std::optional<SourceMatch> FindSourceLocked(uint32 sampleBase)
	{
		for (auto it = s_readRanges.rbegin(); it != s_readRanges.rend(); ++it)
		{
			const uint64 end = static_cast<uint64>(it->start) + it->size;
			if (sampleBase < it->start || sampleBase >= end)
				continue;

			SourceMatch match;
			match.start = it->start;
			match.size = it->size;
			match.offset = sampleBase - it->start;
			match.path = it->path;
			if (ToLower(it->path).ends_with(".bars"))
				match.trackName = ParseBarsTrackName(*it, sampleBase);
			return match;
		}
		return std::nullopt;
	}

	inline std::string CsvQuote(std::string_view input)
	{
		std::string out = "\"";
		for (char c : input)
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

	inline void EnsureCsvLocked()
	{
		if (s_csv.is_open())
			return;

		bool hasExistingData = false;
		{
			std::ifstream existing("botw_sound_source_trace.csv", std::ios::binary | std::ios::ate);
			if (existing)
				hasExistingData = existing.tellg() > 0;
		}
		s_csv.open("botw_sound_source_trace.csv", std::ios::out | std::ios::app);
		if (!hasExistingData && s_csv)
		{
			s_csv << "time_us,event,voice,sample_base,format,current,end,loop,tv_mask,drc_mask,source_start,source_size,source_offset,bars_path,track_name\n";
			s_csv.flush();
		}
	}

	inline void RegisterFileOpen(uint32 fileHandle, const char* path)
	{
		if (!path || fileHandle == 0xFFFFFFFFu || !IsInterestingSoundPath(path))
			return;
		std::scoped_lock lock(s_mutex);
		s_openSoundFiles[fileHandle] = path;
	}

	inline void RegisterFileClose(uint32 fileHandle)
	{
		std::scoped_lock lock(s_mutex);
		s_openSoundFiles.erase(fileHandle);
	}

	inline void RegisterRead(uint32 fileHandle, uint32 destination, uint32 size)
	{
		if (destination == 0 || size == 0)
			return;
		std::scoped_lock lock(s_mutex);
		auto it = s_openSoundFiles.find(fileHandle);
		if (it == s_openSoundFiles.end())
			return;

		ReadRange range;
		range.fileHandle = fileHandle;
		range.start = destination;
		range.size = size;
		range.sequence = ++s_sequence;
		range.path = it->second;
		s_readRanges.emplace_back(std::move(range));

		constexpr size_t kMaxRanges = 16384;
		if (s_readRanges.size() > kMaxRanges)
			s_readRanges.erase(s_readRanges.begin(), s_readRanges.begin() + (s_readRanges.size() - kMaxRanges));
	}

	inline void TraceVoice(std::string_view eventName, uint32 voiceIndex, uint32 sampleBase,
		uint16 format, uint32 currentOffset, uint32 endOffset, uint32 loopOffset,
		uint16 tvMask, uint16 drcMask)
	{
		if (sampleBase == 0)
			return;

		std::scoped_lock lock(s_mutex);
		EnsureCsvLocked();
		if (!s_csv)
			return;

		const auto source = FindSourceLocked(sampleBase);
		const auto nowUs = std::chrono::duration_cast<std::chrono::microseconds>(
			std::chrono::steady_clock::now().time_since_epoch()).count();

		auto hex32 = [](uint32 value) {
			std::ostringstream ss;
			ss << "0x" << std::hex << std::setw(8) << std::setfill('0') << value;
			return ss.str();
		};
		auto hex16 = [](uint16 value) {
			std::ostringstream ss;
			ss << "0x" << std::hex << std::setw(4) << std::setfill('0') << value;
			return ss.str();
		};

		s_csv << nowUs << ',' << eventName << ',' << voiceIndex << ',' << hex32(sampleBase) << ','
			<< format << ',' << currentOffset << ',' << endOffset << ',' << loopOffset << ','
			<< hex16(tvMask) << ',' << hex16(drcMask) << ',';

		if (source)
		{
			s_csv << hex32(source->start) << ',' << source->size << ',' << source->offset << ','
				<< CsvQuote(source->path) << ',' << CsvQuote(source->trackName);
		}
		else
		{
			s_csv << ",,,,";
		}
		s_csv << '\n';

		if (++s_linesSinceFlush >= 16)
		{
			s_csv.flush();
			s_linesSinceFlush = 0;
		}
	}
}
