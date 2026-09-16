#pragma once

#include "Cafe/HW/MMU/MMU.h"
#include "Cafe/OS/common/BotWSoundFingerprintCatalog.h"

#include <algorithm>
#include <cstdint>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace BotWSoundSourceTracerV3Support
{
	struct PendingBarsArchive
	{
		std::string path;
		uint32 start{};
		uint32 size{};
		bool registered{};
		std::vector<std::pair<uint32, uint32>> covered;
	};

	inline std::mutex s_mutex;
	inline std::vector<PendingBarsArchive> s_pendingArchives;

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

	inline bool HasBarsHeader(uint32 address, uint32 available, uint32& archiveSize)
	{
		archiveSize = 0;
		if (address == 0 || available < 16 || !memory_isAddressRangeAccessible(address, 16))
			return false;
		const uint8* p = memory_getPointerFromVirtualOffset(address);
		if (p[0] != 'B' || p[1] != 'A' || p[2] != 'R' || p[3] != 'S')
			return false;
		const bool bigEndian = p[8] == 0xFE;
		if (!bigEndian && p[8] != 0xFF)
			return false;
		archiveSize = ReadU32(p + 4, bigEndian);
		// BOTW BARS archives are far below this ceiling. Keep corrupt headers from
		// creating giant virtual ranges in the diagnostic tracker.
		return archiveSize >= 16 && archiveSize <= 128u * 1024u * 1024u;
	}

	inline void AddCoverage(PendingBarsArchive& archive, uint32 address, uint32 size)
	{
		if (size == 0)
			return;
		const uint64 archiveBegin = archive.start;
		const uint64 archiveEnd = archiveBegin + archive.size;
		const uint64 readBegin = address;
		const uint64 readEnd = readBegin + size;
		const uint64 begin = std::max(archiveBegin, readBegin);
		const uint64 end = std::min(archiveEnd, readEnd);
		if (begin >= end)
			return;

		archive.covered.emplace_back(static_cast<uint32>(begin - archiveBegin), static_cast<uint32>(end - archiveBegin));
		std::sort(archive.covered.begin(), archive.covered.end());
		std::vector<std::pair<uint32, uint32>> merged;
		for (const auto& span : archive.covered)
		{
			if (merged.empty() || span.first > merged.back().second)
				merged.emplace_back(span);
			else
				merged.back().second = std::max(merged.back().second, span.second);
		}
		archive.covered = std::move(merged);
	}

	inline bool IsComplete(const PendingBarsArchive& archive)
	{
		return archive.covered.size() == 1 && archive.covered.front().first == 0 && archive.covered.front().second >= archive.size;
	}

	inline void RegisterBarsReadCompleted(std::string_view path, uint32 destination, uint32 size)
	{
		if (destination == 0 || size == 0)
			return;

		std::vector<std::pair<uint32, uint32>> ready;
		{
			std::scoped_lock lock(s_mutex);

			uint32 archiveSize = 0;
			if (HasBarsHeader(destination, size, archiveSize))
			{
				auto it = std::find_if(s_pendingArchives.begin(), s_pendingArchives.end(), [&](const PendingBarsArchive& archive) {
					return archive.start == destination && archive.path == path;
				});
				if (it == s_pendingArchives.end())
				{
					PendingBarsArchive archive;
					archive.path = std::string(path);
					archive.start = destination;
					archive.size = archiveSize;
					s_pendingArchives.emplace_back(std::move(archive));
				}
				else
				{
					it->size = archiveSize;
				}
			}

			for (auto& archive : s_pendingArchives)
			{
				if (archive.path != path || archive.registered)
					continue;
				AddCoverage(archive, destination, size);
				if (IsComplete(archive) && memory_isAddressRangeAccessible(archive.start, archive.size))
				{
					archive.registered = true;
					ready.emplace_back(archive.start, archive.size);
				}
			}

			constexpr size_t kMaxPendingArchives = 256;
			if (s_pendingArchives.size() > kMaxPendingArchives)
			{
				s_pendingArchives.erase(s_pendingArchives.begin(), s_pendingArchives.begin() +
					(s_pendingArchives.size() - kMaxPendingArchives));
			}
		}

		for (const auto& archive : ready)
			BotWSoundFingerprintCatalog::RegisterBarsRead(path, archive.first, archive.second);
	}

	inline std::optional<BotWSoundFingerprintCatalog::Match> FindMatchForPath(uint32 sampleBase, std::string_view expectedPath)
	{
		if (sampleBase == 0 || expectedPath.empty() || !memory_isAddressRangeAccessible(sampleBase, 64))
			return std::nullopt;

		const uint8* sample = memory_getPointerFromVirtualOffset(sampleBase);
		const uint64 hashA = BotWSoundFingerprintCatalog::Hash32(sample);
		const uint64 hashB = BotWSoundFingerprintCatalog::Hash32(sample + 32);

		std::scoped_lock lock(BotWSoundFingerprintCatalog::s_mutex);
		const BotWSoundFingerprintCatalog::FingerprintEntry* selected = nullptr;
		std::string selectedTrack;
		for (auto it = BotWSoundFingerprintCatalog::s_entries.rbegin(); it != BotWSoundFingerprintCatalog::s_entries.rend(); ++it)
		{
			if (it->path != expectedPath || it->hashA != hashA || it->hashB != hashB)
				continue;
			if (!selected)
			{
				selected = &*it;
				selectedTrack = it->trackName;
			}
			else if (it->trackName != selectedTrack)
			{
				// The same sample bytes can legitimately be shared by multiple cues.
				// Do not guess when the path hint still leaves more than one track.
				return std::nullopt;
			}
		}
		if (!selected)
			return std::nullopt;

		BotWSoundFingerprintCatalog::Match match;
		match.sourceStart = selected->sourceStart;
		match.sourceSize = selected->sourceSize;
		match.dataOffset = selected->dataOffset;
		match.path = selected->path;
		match.trackName = selected->trackName;
		return match;
	}
}
