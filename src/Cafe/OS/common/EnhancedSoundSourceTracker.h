#pragma once

// Stage A adapter around the physically validated BARS/FWAV correlation path.
// Route policy remains game-agnostic and lives in active graphic-pack data.
#include "Cafe/OS/common/BotWSoundSourceTracer.h"
#include "Cafe/OS/common/BotWSoundFingerprintCatalog.h"
#include "Cafe/OS/common/BotWSoundSourceTracerV3Support.h"
#include "Cafe/OS/common/EnhancedSoundPackedBars.h"

#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace EnhancedSoundSourceTracker
{
	using SourceMatch = BotWSoundSourceTracer::SourceMatch;


	inline std::mutex s_packedFileMutex;
	inline std::unordered_map<uint32, std::string> s_openPackedFiles;

	inline bool IsPackedArchivePath(std::string_view path)
	{
		const std::string lower = BotWSoundSourceTracer::ToLower(path);
		return lower.ends_with(".pack") || lower.ends_with(".sarc");
	}

	inline void RegisterFileOpen(uint32 fileHandle, const char* path)
	{
		BotWSoundSourceTracer::RegisterFileOpen(fileHandle, path);
		if (!path || fileHandle == 0xFFFFFFFFu || !IsPackedArchivePath(path))
			return;
		std::scoped_lock lock(s_packedFileMutex);
		s_openPackedFiles[fileHandle] = path;
	}

	inline void RegisterFileClose(uint32 fileHandle)
	{
		BotWSoundSourceTracer::RegisterFileClose(fileHandle);
		std::scoped_lock lock(s_packedFileMutex);
		s_openPackedFiles.erase(fileHandle);
	}

	inline void RegisterRead(uint32 fileHandle, uint32 destination, uint32 size)
	{
		BotWSoundSourceTracer::RegisterRead(fileHandle, destination, size);
	}

	inline void RegisterReadCompleted(uint32 fileHandle, uint32 destination, uint32 size)
	{
		if (destination == 0 || size == 0)
			return;

		std::string soundPath;
		{
			std::scoped_lock lock(BotWSoundSourceTracer::s_mutex);
			auto it = BotWSoundSourceTracer::s_openSoundFiles.find(fileHandle);
			if (it != BotWSoundSourceTracer::s_openSoundFiles.end())
				soundPath = it->second;
		}
		if (!soundPath.empty() && BotWSoundSourceTracer::ToLower(soundPath).ends_with(".bars"))
			BotWSoundSourceTracerV3Support::RegisterBarsReadCompleted(soundPath, destination, size);

		std::string packedPath;
		{
			std::scoped_lock lock(s_packedFileMutex);
			auto it = s_openPackedFiles.find(fileHandle);
			if (it != s_openPackedFiles.end())
				packedPath = it->second;
		}
		if (!packedPath.empty())
			EnhancedSoundPackedBars::RegisterSarcReadCompleted(packedPath, destination, size);
	}

	inline SourceMatch ToSourceMatch(const BotWSoundFingerprintCatalog::Match& fingerprint)
	{
		SourceMatch match;
		match.start = fingerprint.sourceStart;
		match.size = fingerprint.sourceSize;
		match.offset = fingerprint.dataOffset;
		match.path = fingerprint.path;
		match.trackName = fingerprint.trackName;
		return match;
	}

	inline std::vector<SourceMatch> ResolveSourceCandidates(uint32 sampleBase)
	{
		std::vector<SourceMatch> candidates;
		if (sampleBase == 0)
			return candidates;

		std::optional<SourceMatch> source;
		{
			std::scoped_lock lock(BotWSoundSourceTracer::s_mutex);
			source = BotWSoundSourceTracer::FindSourceLocked(sampleBase);
		}

		if (source && !source->trackName.empty())
		{
			candidates.emplace_back(std::move(*source));
			return candidates;
		}

		const auto fingerprints = BotWSoundFingerprintCatalog::FindMatches(
			sampleBase, source ? std::string_view(source->path) : std::string_view{});
		if (!fingerprints.empty())
		{
			candidates.reserve(fingerprints.size());
			for (const auto& fingerprint : fingerprints)
				candidates.emplace_back(ToSourceMatch(fingerprint));
			return candidates;
		}

		// A direct BARS range can still provide useful source-only identity. This is
		// sufficient for an explicit source + track=* policy and avoids guessing a cue.
		if (source)
			candidates.emplace_back(std::move(*source));
		return candidates;
	}

	inline std::optional<SourceMatch> ResolveSource(uint32 sampleBase)
	{
		const auto candidates = ResolveSourceCandidates(sampleBase);
		if (candidates.size() != 1)
			return std::nullopt;
		return candidates.front();
	}
}
