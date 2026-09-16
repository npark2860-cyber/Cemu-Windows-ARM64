#pragma once

// Stage A adapter around the physically validated BARS/FWAV correlation path.
// Route policy remains game-agnostic and lives in active graphic-pack data.
#include "Cafe/OS/common/BotWSoundSourceTracer.h"
#include "Cafe/OS/common/BotWSoundFingerprintCatalog.h"
#include "Cafe/OS/common/BotWSoundSourceTracerV3Support.h"

#include <optional>
#include <string>

namespace EnhancedSoundSourceTracker
{
	using SourceMatch = BotWSoundSourceTracer::SourceMatch;

	inline void RegisterFileOpen(uint32 fileHandle, const char* path)
	{
		BotWSoundSourceTracer::RegisterFileOpen(fileHandle, path);
	}

	inline void RegisterFileClose(uint32 fileHandle)
	{
		BotWSoundSourceTracer::RegisterFileClose(fileHandle);
	}

	inline void RegisterRead(uint32 fileHandle, uint32 destination, uint32 size)
	{
		BotWSoundSourceTracer::RegisterRead(fileHandle, destination, size);
	}

	inline void RegisterReadCompleted(uint32 fileHandle, uint32 destination, uint32 size)
	{
		if (destination == 0 || size == 0)
			return;

		std::string path;
		{
			std::scoped_lock lock(BotWSoundSourceTracer::s_mutex);
			auto it = BotWSoundSourceTracer::s_openSoundFiles.find(fileHandle);
			if (it == BotWSoundSourceTracer::s_openSoundFiles.end())
				return;
			path = it->second;
		}

		if (BotWSoundSourceTracer::ToLower(path).ends_with(".bars"))
			BotWSoundSourceTracerV3Support::RegisterBarsReadCompleted(path, destination, size);
	}

	inline std::optional<SourceMatch> ResolveSource(uint32 sampleBase)
	{
		if (sampleBase == 0)
			return std::nullopt;

		std::optional<SourceMatch> source;
		{
			std::scoped_lock lock(BotWSoundSourceTracer::s_mutex);
			source = BotWSoundSourceTracer::FindSourceLocked(sampleBase);
		}

		if (source && source->trackName.empty())
		{
			const auto fingerprint = BotWSoundSourceTracerV3Support::FindMatchForPath(sampleBase, source->path);
			if (fingerprint)
			{
				source->start = fingerprint->sourceStart;
				source->size = fingerprint->sourceSize;
				source->offset = fingerprint->dataOffset;
				source->path = fingerprint->path;
				source->trackName = fingerprint->trackName;
			}
		}

		if (!source)
		{
			const auto fingerprint = BotWSoundFingerprintCatalog::FindMatch(sampleBase);
			if (fingerprint)
			{
				SourceMatch match;
				match.start = fingerprint->sourceStart;
				match.size = fingerprint->sourceSize;
				match.offset = fingerprint->dataOffset;
				match.path = fingerprint->path;
				match.trackName = fingerprint->trackName;
				source = std::move(match);
			}
		}
		return source;
	}
}
