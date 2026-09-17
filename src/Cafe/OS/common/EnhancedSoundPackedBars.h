#pragma once

#include "Cafe/HW/MMU/MMU.h"
#include "Cafe/OS/common/BotWSoundFingerprintCatalog.h"

#include <algorithm>
#include <cstdint>
#include <mutex>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace EnhancedSoundPackedBars
{
	struct PendingSarc
	{
		std::string path;
		uint32 start{};
		uint32 size{};
		bool registered{};
		std::vector<std::pair<uint32, uint32>> covered;
	};

	inline std::mutex s_mutex;
	inline std::vector<PendingSarc> s_pendingSarcs;

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

	inline bool HasSarcHeader(uint32 address, uint32 available, uint32& archiveSize)
	{
		archiveSize = 0;
		if (address == 0 || available < 0x14 || !memory_isAddressRangeAccessible(address, 0x14))
			return false;
		const uint8* base = memory_getPointerFromVirtualOffset(address);
		if (!HasMagic(base, "SARC"))
			return false;

		bool bigEndian{};
		if (base[6] == 0xFE && base[7] == 0xFF)
			bigEndian = true;
		else if (base[6] == 0xFF && base[7] == 0xFE)
			bigEndian = false;
		else
			return false;

		const uint16 headerSize = ReadU16(base + 4, bigEndian);
		archiveSize = ReadU32(base + 8, bigEndian);
		const uint32 dataOffset = ReadU32(base + 0x0C, bigEndian);
		if (headerSize < 0x14 || archiveSize < headerSize || dataOffset < headerSize || dataOffset > archiveSize)
			return false;
		// Keep corrupt headers from creating enormous tracked virtual ranges.
		return archiveSize <= 512u * 1024u * 1024u;
	}

	inline void AddCoverage(PendingSarc& archive, uint32 address, uint32 size)
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

	inline bool IsComplete(const PendingSarc& archive)
	{
		return archive.covered.size() == 1 && archive.covered.front().first == 0 && archive.covered.front().second >= archive.size;
	}

	inline std::string ReadName(const uint8* base, uint32 archiveSize, uint32 nameOffset, uint32 nameLimit)
	{
		if (nameOffset >= nameLimit || nameLimit > archiveSize)
			return {};
		const char* begin = reinterpret_cast<const char*>(base + nameOffset);
		const uint32 maxLength = nameLimit - nameOffset;
		uint32 length = 0;
		while (length < maxLength && begin[length] != '\0')
			++length;
		if (length == 0 || length == maxLength)
			return {};
		return std::string(begin, length);
	}

	inline bool EndsWithBars(std::string_view name)
	{
		if (name.size() < 5)
			return false;
		const auto tail = name.substr(name.size() - 5);
		return (tail[0] == '.' && (tail[1] == 'b' || tail[1] == 'B') &&
			(tail[2] == 'a' || tail[2] == 'A') && (tail[3] == 'r' || tail[3] == 'R') &&
			(tail[4] == 's' || tail[4] == 'S'));
	}

	inline void RegisterEmbeddedBars(std::string_view parentPath, uint32 start, uint32 size)
	{
		if (start == 0 || size < 0x20 || !memory_isAddressRangeAccessible(start, size))
			return;
		const uint8* base = memory_getPointerFromVirtualOffset(start);
		if (!HasMagic(base, "SARC"))
			return;

		bool bigEndian{};
		if (base[6] == 0xFE && base[7] == 0xFF)
			bigEndian = true;
		else if (base[6] == 0xFF && base[7] == 0xFE)
			bigEndian = false;
		else
			return;

		const uint16 sarcHeaderSize = ReadU16(base + 4, bigEndian);
		const uint32 archiveSize = ReadU32(base + 8, bigEndian);
		const uint32 dataOffset = ReadU32(base + 0x0C, bigEndian);
		if (archiveSize > size || sarcHeaderSize > archiveSize || dataOffset > archiveSize ||
			sarcHeaderSize + 0x0C > archiveSize)
			return;

		const uint32 sfatOffset = sarcHeaderSize;
		const uint8* sfat = base + sfatOffset;
		if (!HasMagic(sfat, "SFAT"))
			return;
		const uint16 sfatHeaderSize = ReadU16(sfat + 4, bigEndian);
		const uint16 nodeCount = ReadU16(sfat + 6, bigEndian);
		if (sfatHeaderSize < 0x0C || nodeCount == 0 || nodeCount > 65535)
			return;

		const uint64 nodeBase64 = static_cast<uint64>(sfatOffset) + sfatHeaderSize;
		const uint64 nodesEnd64 = nodeBase64 + static_cast<uint64>(nodeCount) * 16ull;
		if (nodesEnd64 + 8ull > archiveSize || nodesEnd64 > dataOffset)
			return;
		const uint32 nodeBase = static_cast<uint32>(nodeBase64);
		const uint32 sfntOffset = static_cast<uint32>(nodesEnd64);
		const uint8* sfnt = base + sfntOffset;
		if (!HasMagic(sfnt, "SFNT"))
			return;
		const uint16 sfntHeaderSize = ReadU16(sfnt + 4, bigEndian);
		if (sfntHeaderSize < 8 || static_cast<uint64>(sfntOffset) + sfntHeaderSize > dataOffset)
			return;
		const uint32 namesBase = sfntOffset + sfntHeaderSize;

		for (uint32 i = 0; i < nodeCount; ++i)
		{
			const uint8* node = base + nodeBase + i * 16;
			const uint32 nameField = ReadU32(node + 4, bigEndian);
			if ((nameField >> 24) == 0)
				continue;
			const uint64 nameOffset64 = static_cast<uint64>(namesBase) + static_cast<uint64>(nameField & 0x00FFFFFFu) * 4ull;
			if (nameOffset64 >= dataOffset)
				continue;
			const std::string name = ReadName(base, archiveSize, static_cast<uint32>(nameOffset64), dataOffset);
			if (!EndsWithBars(name))
				continue;

			const uint32 relativeStart = ReadU32(node + 8, bigEndian);
			const uint32 relativeEnd = ReadU32(node + 12, bigEndian);
			if (relativeStart >= relativeEnd || relativeEnd > archiveSize - dataOffset)
				continue;
			const uint32 embeddedSize = relativeEnd - relativeStart;
			const uint64 embeddedStart64 = static_cast<uint64>(start) + dataOffset + relativeStart;
			if (embeddedStart64 > 0xFFFFFFFFull)
				continue;
			const uint32 embeddedStart = static_cast<uint32>(embeddedStart64);
			if (embeddedSize < 32 || !memory_isAddressRangeAccessible(embeddedStart, embeddedSize))
				continue;
			const uint8* embedded = memory_getPointerFromVirtualOffset(embeddedStart);
			if (!HasMagic(embedded, "BARS"))
				continue;

			const std::string virtualPath = std::string(parentPath) + "::" + name;
			BotWSoundFingerprintCatalog::RegisterBarsRead(virtualPath, embeddedStart, embeddedSize);
		}
	}

	inline void RegisterSarcReadCompleted(std::string_view path, uint32 destination, uint32 size)
	{
		if (destination == 0 || size == 0)
			return;

		std::vector<std::pair<uint32, uint32>> ready;
		{
			std::scoped_lock lock(s_mutex);
			uint32 archiveSize = 0;
			if (HasSarcHeader(destination, size, archiveSize))
			{
				auto it = std::find_if(s_pendingSarcs.begin(), s_pendingSarcs.end(), [&](const PendingSarc& archive) {
					return archive.start == destination && archive.path == path;
				});
				if (it == s_pendingSarcs.end())
				{
					PendingSarc archive;
					archive.path = std::string(path);
					archive.start = destination;
					archive.size = archiveSize;
					s_pendingSarcs.emplace_back(std::move(archive));
				}
				else
				{
					it->size = archiveSize;
				}
			}

			for (auto& archive : s_pendingSarcs)
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

			constexpr size_t kMaxPendingSarcs = 64;
			if (s_pendingSarcs.size() > kMaxPendingSarcs)
				s_pendingSarcs.erase(s_pendingSarcs.begin(), s_pendingSarcs.begin() + (s_pendingSarcs.size() - kMaxPendingSarcs));
		}

		for (const auto& archive : ready)
			RegisterEmbeddedBars(path, archive.first, archive.second);
	}
}
