#pragma once

// Stage A adapter around the physically validated BARS/FWAV correlation path.
// Route policy remains game-agnostic and lives in active graphic-pack data.
#include "Cafe/OS/common/BotWSoundSourceTracer.h"
#include "Cafe/OS/common/BotWSoundFingerprintCatalog.h"
#include "Cafe/OS/common/BotWSoundSourceTracerV3Support.h"
#include "Cafe/OS/common/EnhancedSoundPackedBars.h"

#include <algorithm>
#include <fstream>
#include <optional>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace EnhancedSoundSourceTracker
{
	using SourceMatch = BotWSoundSourceTracer::SourceMatch;

	inline std::mutex s_packedFileMutex;
	inline std::unordered_map<uint32, std::string> s_openPackedFiles;

	// Diagnostic-only state for the one-handed sword unresolved fingerprint probe.
	// This branch never changes routing decisions; it only records why FindMatch()
	// returned no semantic source for a runtime AX sample.
	inline std::mutex s_fingerprintDiagMutex;
	inline std::unordered_set<std::string> s_fingerprintDiagSeen;
	inline std::ofstream s_fingerprintDiagCsv;

	inline bool IsPackedArchivePath(std::string_view path)
	{
		const std::string lower = BotWSoundSourceTracer::ToLower(path);
		return lower.ends_with(".pack") || lower.ends_with(".sarc");
	}

	inline void TraceUnresolvedFingerprint(uint32 sampleBase)
	{
		if (sampleBase == 0 || !memory_isAddressRangeAccessible(sampleBase, 64))
			return;

		const uint8* sample = memory_getPointerFromVirtualOffset(sampleBase);
		const uint64 hashA = BotWSoundFingerprintCatalog::Hash32(sample);
		const uint64 hashB = BotWSoundFingerprintCatalog::Hash32(sample + 32);

		std::vector<std::string> candidates;
		size_t catalogEntries = 0;
		{
			std::scoped_lock lock(BotWSoundFingerprintCatalog::s_mutex);
			catalogEntries = BotWSoundFingerprintCatalog::s_entries.size();
			for (const auto& entry : BotWSoundFingerprintCatalog::s_entries)
			{
				if (entry.hashA != hashA || entry.hashB != hashB)
					continue;
				const std::string key = entry.path + "::" + entry.trackName;
				if (std::find(candidates.begin(), candidates.end(), key) == candidates.end())
					candidates.emplace_back(key);
			}
		}

		const char* status = candidates.empty() ? "no_candidate" :
			(candidates.size() == 1 ? "single_candidate_rejected" : "ambiguous");

		std::ostringstream sampleText;
		sampleText << "0x" << std::hex << sampleBase;
		std::ostringstream hashAText;
		hashAText << "0x" << std::hex << hashA;
		std::ostringstream hashBText;
		hashBText << "0x" << std::hex << hashB;

		std::string candidateText;
		for (size_t i = 0; i < candidates.size(); ++i)
		{
			if (i != 0)
				candidateText += " | ";
			candidateText += candidates[i];
		}

		const std::string seenKey = sampleText.str() + ":" + status + ":" + std::to_string(candidates.size());
		std::scoped_lock diagLock(s_fingerprintDiagMutex);
		if (!s_fingerprintDiagSeen.emplace(seenKey).second)
			return;

		if (!s_fingerprintDiagCsv.is_open())
		{
			bool hasExistingData = false;
			{
				std::ifstream existing("enhanced_sound_fingerprint_diag.csv", std::ios::binary | std::ios::ate);
				if (existing)
					hasExistingData = existing.tellg() > 0;
			}
			s_fingerprintDiagCsv.open("enhanced_sound_fingerprint_diag.csv", std::ios::out | std::ios::app);
			if (!hasExistingData && s_fingerprintDiagCsv)
				s_fingerprintDiagCsv << "sample_base,hash_a,hash_b,status,candidate_count,catalog_entries,candidates\n";
		}
		if (!s_fingerprintDiagCsv)
			return;

		s_fingerprintDiagCsv << sampleText.str() << ',' << hashAText.str() << ',' << hashBText.str() << ','
			<< status << ',' << candidates.size() << ',' << catalogEntries << ','
			<< BotWSoundSourceTracer::CsvQuote(candidateText) << '\n';
		s_fingerprintDiagCsv.flush();
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

		if (!source || source->trackName.empty())
			TraceUnresolvedFingerprint(sampleBase);
		return source;
	}
}
