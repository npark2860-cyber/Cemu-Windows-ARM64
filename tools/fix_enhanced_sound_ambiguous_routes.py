from pathlib import Path

CATALOG = Path("src/Cafe/OS/common/BotWSoundFingerprintCatalog.h")
TRACKER = Path("src/Cafe/OS/common/EnhancedSoundSourceTracker.h")
ROUTER = Path("src/Cafe/OS/common/EnhancedSoundRouter.h")
AX = Path("src/Cafe/OS/libs/snd_core/ax_voice.cpp")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


# 1) Preserve all exact fingerprint candidates instead of discarding shared samples.
text = CATALOG.read_text(encoding="utf-8")
old = r'''	inline std::optional<Match> FindMatch(uint32 sampleBase)
	{
		if (sampleBase == 0 || !memory_isAddressRangeAccessible(sampleBase, 64))
			return std::nullopt;
		const uint8* sample = memory_getPointerFromVirtualOffset(sampleBase);
		const uint64 hashA = Hash32(sample);
		const uint64 hashB = Hash32(sample + 32);

		std::scoped_lock lock(s_mutex);
		const FingerprintEntry* selected = nullptr;
		std::string selectedKey;
		for (auto it = s_entries.rbegin(); it != s_entries.rend(); ++it)
		{
			if (it->hashA != hashA || it->hashB != hashB)
				continue;
			const std::string key = it->path + "\n" + it->trackName;
			if (!selected)
			{
				selected = &*it;
				selectedKey = key;
			}
			else if (key != selectedKey)
			{
				// Ambiguous fingerprints are deliberately left unresolved.
				return std::nullopt;
			}
		}
		if (!selected)
			return std::nullopt;

		Match match;
		match.sourceStart = selected->sourceStart;
		match.sourceSize = selected->sourceSize;
		match.dataOffset = selected->dataOffset;
		match.path = selected->path;
		match.trackName = selected->trackName;
		return match;
	}
'''
new = r'''	inline std::vector<Match> FindMatches(uint32 sampleBase, std::string_view expectedPath = {})
	{
		std::vector<Match> matches;
		if (sampleBase == 0 || !memory_isAddressRangeAccessible(sampleBase, 64))
			return matches;
		const uint8* sample = memory_getPointerFromVirtualOffset(sampleBase);
		const uint64 hashA = Hash32(sample);
		const uint64 hashB = Hash32(sample + 32);

		std::scoped_lock lock(s_mutex);
		for (auto it = s_entries.rbegin(); it != s_entries.rend(); ++it)
		{
			if (it->hashA != hashA || it->hashB != hashB)
				continue;
			if (!expectedPath.empty() && it->path != expectedPath)
				continue;

			const bool duplicate = std::any_of(matches.begin(), matches.end(), [&](const Match& match) {
				return match.path == it->path && match.trackName == it->trackName;
			});
			if (duplicate)
				continue;

			Match match;
			match.sourceStart = it->sourceStart;
			match.sourceSize = it->sourceSize;
			match.dataOffset = it->dataOffset;
			match.path = it->path;
			match.trackName = it->trackName;
			matches.emplace_back(std::move(match));
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
'''
text = replace_once(text, old, new, "fingerprint candidate set")
CATALOG.write_text(text, encoding="utf-8")


# 2) Expose candidate identities to the routing layer while keeping ResolveSource's
#    conservative single-identity contract for existing callers.
text = TRACKER.read_text(encoding="utf-8")
text = replace_once(
    text,
    '#include <unordered_map>\n',
    '#include <unordered_map>\n#include <vector>\n',
    "tracker vector include",
)
old = r'''	inline std::optional<SourceMatch> ResolveSource(uint32 sampleBase)
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
'''
new = r'''	inline SourceMatch ToSourceMatch(const BotWSoundFingerprintCatalog::Match& fingerprint)
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
'''
text = replace_once(text, old, new, "candidate-aware source tracker")
TRACKER.write_text(text, encoding="utf-8")


# 3) track=* means all tracks in a known source, including a source-only identity.
text = ROUTER.read_text(encoding="utf-8")
old = r'''	inline bool MatchTrack(std::string_view pattern, std::string_view trackName)
	{
		if (pattern.empty())
			return true;
		if (trackName.empty())
			return false;
		return GlobMatch(pattern, trackName);
	}
'''
new = r'''	inline bool MatchTrack(std::string_view pattern, std::string_view trackName)
	{
		if (pattern.empty())
			return true;
		if (trackName.empty())
			return Normalize(pattern) == "*";
		return GlobMatch(pattern, trackName);
	}
'''
text = replace_once(text, old, new, "source-only wildcard routing")
ROUTER.write_text(text, encoding="utf-8")


# 4) Apply a route only when every plausible fingerprint identity resolves to the
#    same policy. Shared samples are therefore routable without guessing cue names.
text = AX.read_text(encoding="utf-8")
old = r'''		if (GetConfig().enhanced_sound_experience && sampleBase != MPTR_NULL)
		{
			EnhancedSoundDualSenseService::EnsureRunning();
			const auto source = EnhancedSoundSourceTracker::ResolveSource(sampleBase);
			if (source)
			{
				const auto resolved = EnhancedSoundRouter::Resolve(source->path, source->trackName);
				if (resolved && (resolved->mode == EnhancedSoundRouter::Mode::AddDRC ||
					resolved->mode == EnhancedSoundRouter::Mode::SpatialDRC))
					route = resolved;
			}
		}
'''
new = r'''		if (GetConfig().enhanced_sound_experience && sampleBase != MPTR_NULL)
		{
			EnhancedSoundDualSenseService::EnsureRunning();
			const auto sources = EnhancedSoundSourceTracker::ResolveSourceCandidates(sampleBase);
			bool unanimousRoute = !sources.empty();
			for (const auto& source : sources)
			{
				const auto resolved = EnhancedSoundRouter::Resolve(source.path, source.trackName);
				if (!resolved || (resolved->mode != EnhancedSoundRouter::Mode::AddDRC &&
					resolved->mode != EnhancedSoundRouter::Mode::SpatialDRC))
				{
					unanimousRoute = false;
					break;
				}
				if (!route)
					route = resolved;
				else if (route->mode != resolved->mode || route->gain != resolved->gain)
				{
					unanimousRoute = false;
					break;
				}
			}
			if (!unanimousRoute)
				route.reset();
		}
'''
text = replace_once(text, old, new, "unanimous ambiguous route")
AX.write_text(text, encoding="utf-8")

print("Enhanced Sound ambiguous shared-sample routing fix applied")
