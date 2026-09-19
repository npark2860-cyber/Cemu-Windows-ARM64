#pragma once

#include "Cafe/HW/MMU/MMU.h"

#include <algorithm>
#include <cstdint>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

namespace BotWSoundFingerprintCatalog
{
	struct FingerprintEntry
	{
		uint64 hashA{};
		uint64 hashB{};
		uint32 sourceStart{};
		uint32 sourceSize{};
		uint32 dataOffset{};
		uint32 rawSize{};
		uint32 channel{};
		std::string path;
		std::string trackName;
	};

	struct Match
	{
		uint32 sourceStart{};
		uint32 sourceSize{};
		uint32 dataOffset{};
		std::string path;
		std::string trackName;
	};

	struct FingerprintKey
	{
		uint64 hashA{};
		uint64 hashB{};

		bool operator==(const FingerprintKey&) const = default;
	};

	struct FingerprintKeyHasher
	{
		size_t operator()(const FingerprintKey& key) const
		{
			const size_t h1 = std::hash<uint64>{}(key.hashA);
			const size_t h2 = std::hash<uint64>{}(key.hashB);
			return h1 ^ (h2 + 0x9e3779b97f4a7c15ull + (h1 << 6) + (h1 >> 2));
		}
	};

	inline std::mutex s_mutex;
	inline std::vector<FingerprintEntry> s_entries;
	// Lookup-only acceleration index. s_entries remains the source of truth.
	inline std::unordered_map<FingerprintKey, std::vector<Match>, FingerprintKeyHasher> s_lookupIndex;

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

	inline uint64 Hash32(const uint8* p)
	{
		uint64 hash = 1469598103934665603ull;
		for (uint32 i = 0; i < 32; ++i)
		{
			hash ^= p[i];
			hash *= 1099511628211ull;
		}
		return hash;
	}

	inline std::string ParseTrackName(const uint8* base, uint32 archiveSize, bool barsBigEndian,
		uint32 count, uint32 index)
	{
		if (index >= count)
			return {};
		const uint32 pairsOffset = 16 + count * 4;
		const uint32 amtaOffset = ReadU32(base + pairsOffset + index * 8, barsBigEndian);
		if (amtaOffset > archiveSize || archiveSize - amtaOffset < 24)
			return {};

		const uint8* amta = base + amtaOffset;
		if (!HasMagic(amta, "AMTA"))
			return {};
		const bool amtaBigEndian = amta[4] == 0xFE;
		if (!amtaBigEndian && amta[4] != 0xFF)
			return {};

		const uint16 version = ReadU16(amta + 6, amtaBigEndian);
		const uint32 amtaSize = ReadU32(amta + 8, amtaBigEndian);
		if (amtaSize < 24 || amtaSize > archiveSize - amtaOffset)
			return {};

		uint32 strgOffsetField = 0;
		if (version == 0x0100)
			strgOffsetField = 0x14;
		else if (version == 0x0300 || version == 0x0400)
			strgOffsetField = 0x18;
		else
			return {};
		if (strgOffsetField + 4 > amtaSize)
			return {};

		const uint32 dataRel = ReadU32(amta + 0x0C, amtaBigEndian);
		const uint32 strgRel = ReadU32(amta + strgOffsetField, amtaBigEndian);
		auto withinAmta = [amtaSize](uint64 pos, uint64 length) {
			return pos <= amtaSize && length <= amtaSize - pos;
		};

		if (!withinAmta(dataRel, 12) || !HasMagic(amta + dataRel, "DATA"))
			return {};
		const uint32 dataBodySize = ReadU32(amta + dataRel + 4, amtaBigEndian);
		if (dataBodySize < 4 || !withinAmta(static_cast<uint64>(dataRel) + 8, dataBodySize))
			return {};
		const uint32 assetNameOffset = ReadU32(amta + dataRel + 8, amtaBigEndian);

		if (!withinAmta(strgRel, 8) || !HasMagic(amta + strgRel, "STRG"))
			return {};
		const uint32 stringBodySize = ReadU32(amta + strgRel + 4, amtaBigEndian);
		if (stringBodySize == 0 || !withinAmta(static_cast<uint64>(strgRel) + 8, stringBodySize) ||
			assetNameOffset >= stringBodySize)
			return {};

		const char* name = reinterpret_cast<const char*>(amta + strgRel + 8 + assetNameOffset);
		const uint32 maxLength = stringBodySize - assetNameOffset;
		uint32 length = 0;
		while (length < maxLength && name[length] != '\0')
			++length;
		if (length == 0 || length == maxLength)
			return {};
		return std::string(name, length);
	}

	inline uint32 CalculateRawChannelSize(uint8 sampleFormat, uint32 numSamples)
	{
		if (sampleFormat == 0)
			return numSamples;
		if (sampleFormat == 1)
		{
			const uint64 size = static_cast<uint64>(numSamples) * 2ull;
			return size <= 0xFFFFFFFFull ? static_cast<uint32>(size) : 0;
		}
		if (sampleFormat == 2)
		{
			// Nintendo DSP ADPCM: one predictor/scale byte per 14 samples plus packed nibbles.
			const uint64 size = static_cast<uint64>((numSamples + 13) / 14) +
				static_cast<uint64>((numSamples + 1) / 2);
			return size <= 0xFFFFFFFFull ? static_cast<uint32>(size) : 0;
		}
		return 0;
	}

	inline Match ToLookupMatch(const FingerprintEntry& entry)
	{
		Match match;
		match.sourceStart = entry.sourceStart;
		match.sourceSize = entry.sourceSize;
		match.dataOffset = entry.dataOffset;
		match.path = entry.path;
		match.trackName = entry.trackName;
		return match;
	}

	inline void RemoveLookupEntryLocked(const FingerprintEntry& entry)
	{
		const FingerprintKey key{ entry.hashA, entry.hashB };
		auto bucketIt = s_lookupIndex.find(key);
		if (bucketIt == s_lookupIndex.end())
			return;

		auto& bucket = bucketIt->second;
		auto it = std::find_if(bucket.begin(), bucket.end(), [&](const Match& match) {
			return match.sourceStart == entry.sourceStart && match.sourceSize == entry.sourceSize &&
				match.dataOffset == entry.dataOffset && match.path == entry.path &&
				match.trackName == entry.trackName;
		});
		if (it != bucket.end())
			bucket.erase(it);
		if (bucket.empty())
			s_lookupIndex.erase(bucketIt);
	}

	inline void AddEntryLocked(FingerprintEntry entry)
	{
		for (const auto& existing : s_entries)
		{
			if (existing.hashA == entry.hashA && existing.hashB == entry.hashB &&
				existing.channel == entry.channel && existing.path == entry.path &&
				existing.trackName == entry.trackName)
				return;
		}

		const FingerprintKey key{ entry.hashA, entry.hashB };
		s_lookupIndex[key].emplace_back(ToLookupMatch(entry));
		s_entries.emplace_back(std::move(entry));

		constexpr size_t kMaxEntries = 32768;
		if (s_entries.size() > kMaxEntries)
		{
			const size_t removeCount = s_entries.size() - kMaxEntries;
			for (size_t i = 0; i < removeCount; ++i)
				RemoveLookupEntryLocked(s_entries[i]);
			s_entries.erase(s_entries.begin(), s_entries.begin() + removeCount);
		}
	}

	inline void RegisterBarsRead(std::string_view path, uint32 start, uint32 size)
	{
		if (start == 0 || size < 32 || !memory_isAddressRangeAccessible(start, std::min<uint32>(size, 64)))
			return;
		const uint8* base = memory_getPointerFromVirtualOffset(start);
		if (!HasMagic(base, "BARS"))
			return;

		const bool barsBigEndian = base[8] == 0xFE;
		if (!barsBigEndian && base[8] != 0xFF)
			return;

		const uint32 count = ReadU32(base + 12, barsBigEndian);
		if (count == 0 || count > 16384)
			return;
		const uint64 offsetTableEnd = 16ull + static_cast<uint64>(count) * 12ull;
		if (offsetTableEnd > size)
			return;

		uint32 archiveSize = ReadU32(base + 4, barsBigEndian);
		if (archiveSize < offsetTableEnd || archiveSize > size)
			return;
		if (!memory_isAddressRangeAccessible(start, archiveSize))
			return;

		const uint32 pairsOffset = 16 + count * 4;
		std::scoped_lock lock(s_mutex);

		for (uint32 i = 0; i < count; ++i)
		{
			const uint32 trackOffset = ReadU32(base + pairsOffset + i * 8 + 4, barsBigEndian);
			if (trackOffset > archiveSize || archiveSize - trackOffset < 32)
				continue;
			const uint8* track = base + trackOffset;
			if (!HasMagic(track, "FWAV"))
				continue;

			const bool fwavBigEndian = track[4] == 0xFE;
			if (!fwavBigEndian && track[4] != 0xFF)
				continue;
			const uint32 fileSize = ReadU32(track + 12, fwavBigEndian);
			if (fileSize < 32 || fileSize > archiveSize - trackOffset)
				continue;
			const uint16 blockCount = ReadU16(track + 16, fwavBigEndian);
			if (blockCount == 0 || blockCount > 16 || 20ull + static_cast<uint64>(blockCount) * 12ull > fileSize)
				continue;

			uint32 infoOffset = 0;
			uint32 infoSize = 0;
			uint32 dataOffset = 0;
			uint32 dataSize = 0;
			for (uint32 block = 0; block < blockCount; ++block)
			{
				const uint8* ref = track + 20 + block * 12;
				const uint16 type = ReadU16(ref, fwavBigEndian);
				const uint32 blockOffset = ReadU32(ref + 4, fwavBigEndian);
				const uint32 blockSize = ReadU32(ref + 8, fwavBigEndian);
				if (blockOffset > fileSize || blockSize > fileSize - blockOffset)
					continue;
				if (type == 0x7000)
				{
					infoOffset = blockOffset;
					infoSize = blockSize;
				}
				else if (type == 0x7001)
				{
					dataOffset = blockOffset;
					dataSize = blockSize;
				}
			}
			if (infoOffset == 0 || dataOffset == 0 || infoSize < 36 || dataSize < 8)
				continue;

			const uint8* info = track + infoOffset;
			const uint8* data = track + dataOffset;
			if (!HasMagic(info, "INFO") || !HasMagic(data, "DATA"))
				continue;
			const uint8 sampleFormat = info[8];
			const uint32 numSamples = ReadU32(info + 20, fwavBigEndian);
			const uint32 channelCount = ReadU32(info + 28, fwavBigEndian);
			if (channelCount == 0 || channelCount > 16 || 32ull + static_cast<uint64>(channelCount) * 8ull > infoSize)
				continue;
			const uint32 rawSize = CalculateRawChannelSize(sampleFormat, numSamples);
			if (rawSize < 64)
				continue;

			const std::string trackName = ParseTrackName(base, archiveSize, barsBigEndian, count, i);

			const uint8* channelBase = info + 28;
			for (uint32 channel = 0; channel < channelCount; ++channel)
			{
				const uint8* channelRef = info + 32 + channel * 8;
				const uint32 channelInfoRel = ReadU32(channelRef + 4, fwavBigEndian);
				if (channelInfoRel > infoSize || channelInfoRel + 20 > infoSize)
					continue;
				const uint8* channelInfo = channelBase + channelInfoRel;
				if (channelInfo < info || channelInfo + 20 > info + infoSize)
					continue;
				const uint32 sampleDataRel = ReadU32(channelInfo + 4, fwavBigEndian);
				if (sampleDataRel > dataSize - 8 || rawSize > dataSize - 8 - sampleDataRel)
					continue;
				const uint8* raw = data + 8 + sampleDataRel;

				FingerprintEntry entry;
				entry.hashA = Hash32(raw);
				entry.hashB = Hash32(raw + 32);
				entry.sourceStart = start;
				entry.sourceSize = archiveSize;
				entry.dataOffset = trackOffset + dataOffset + 8 + sampleDataRel;
				entry.rawSize = rawSize;
				entry.channel = channel;
				entry.path = std::string(path);
				entry.trackName = trackName;
				AddEntryLocked(std::move(entry));
			}
		}
	}

	inline std::vector<Match> FindMatches(uint32 sampleBase, std::string_view expectedPath = {})
	{
		std::vector<Match> matches;
		if (sampleBase == 0 || !memory_isAddressRangeAccessible(sampleBase, 64))
			return matches;
		const uint8* sample = memory_getPointerFromVirtualOffset(sampleBase);
		const uint64 hashA = Hash32(sample);
		const uint64 hashB = Hash32(sample + 32);

		std::scoped_lock lock(s_mutex);
		const auto bucketIt = s_lookupIndex.find(FingerprintKey{ hashA, hashB });
		if (bucketIt == s_lookupIndex.end())
			return matches;

		const auto& bucket = bucketIt->second;
		for (auto it = bucket.rbegin(); it != bucket.rend(); ++it)
		{
			if (!expectedPath.empty() && it->path != expectedPath)
				continue;

			const bool duplicate = std::any_of(matches.begin(), matches.end(), [&](const Match& match) {
				return match.path == it->path && match.trackName == it->trackName;
			});
			if (duplicate)
				continue;
			matches.emplace_back(*it);
		}
		return matches;
	}

	inline std::optional<Match> FindMatch(uint32 sampleBase)
	{
		const auto matches = FindMatches(sampleBase);
		if (matches.size() != 1)
			return std::nullopt;
		return matches.front();
	}
}
