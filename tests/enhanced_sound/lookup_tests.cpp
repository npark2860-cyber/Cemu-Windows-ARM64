#include "Cafe/OS/common/EnhancedSoundSourceTracker.h"
#include "Cafe/OS/common/EnhancedSoundRouter.h"
#include <chrono>
#include <iostream>
#include <random>
#include <stdexcept>
#include <thread>

namespace Router = EnhancedSoundRouter;
namespace Tracer = BotWSoundSourceTracer;
namespace Catalog = BotWSoundFingerprintCatalog;

void Check(bool condition, const char* message)
{
	if (!condition)
		throw std::runtime_error(message);
}

// The pre-change matcher from 668acee, deliberately retaining normalization
// allocations. This oracle also preserves its literal-star comparison order.
bool ReferenceGlob(std::string_view patternValue, std::string_view textValue)
{
	const std::string pattern = Router::Normalize(patternValue);
	const std::string text = Router::Normalize(textValue);
	size_t p = 0, t = 0, star = std::string::npos, retry = 0;
	while (t < text.size())
	{
		if (p < pattern.size() && pattern[p] == text[t])
		{
			++p;
			++t;
		}
		else if (p < pattern.size() && pattern[p] == '*')
		{
			star = p++;
			retry = t;
		}
		else if (star != std::string::npos)
		{
			p = star + 1;
			t = ++retry;
		}
		else
			return false;
	}
	while (p < pattern.size() && pattern[p] == '*')
		++p;
	return p == pattern.size();
}

std::optional<Router::RouteMatch> ReferenceResolve(std::string_view path, std::string_view track)
{
	for (auto table = Router::s_tables.rbegin(); table != Router::s_tables.rend(); ++table)
	{
		for (const auto& rule : table->rules)
		{
			const bool fullPath = rule.sourcePattern.find_first_of("/\\") != std::string::npos;
			if (!rule.sourcePattern.empty() && !ReferenceGlob(rule.sourcePattern, fullPath ? path : Router::BaseName(path)))
				continue;
			if (!rule.trackPattern.empty() && (track.empty() || !ReferenceGlob(rule.trackPattern, track)))
				continue;
			return Router::RouteMatch{ rule.audioEnabled, rule.mode, rule.gain,
				rule.tvVolumePercent, rule.hapticPath, rule.hapticGain, rule.hapticLoop };
		}
	}
	return std::nullopt;
}

bool SameRoute(const std::optional<Router::RouteMatch>& a, const std::optional<Router::RouteMatch>& b)
{
	return a.has_value() == b.has_value() && (!a || Router::Equivalent(*a, *b));
}

void TestRoutes()
{
	std::vector<std::string> words{ "" };
	const std::string alphabet = "aA*/\\?b";
	for (size_t length = 1; length <= 3; ++length)
	{
		const auto previous = words;
		for (const auto& word : previous)
			if (word.size() == length - 1)
				for (char c : alphabet)
					words.push_back(word + c);
	}
	for (const auto& pattern : words)
		for (const auto& text : words)
			Check(Router::GlobMatch(pattern, text) == ReferenceGlob(pattern, text), "glob equivalence");
	for (unsigned i = 0; i < 256; ++i)
	{
		std::string byte(1, static_cast<char>(i));
		Check(Router::GlobMatch(byte, byte) == ReferenceGlob(byte, byte), "unsigned byte normalization");
	}

	std::vector<Router::RouteRule> rules;
	for (unsigned i = 0; i < 49; ++i)
	{
		Router::RouteRule rule;
		rule.sourcePattern = (i % 3 == 0) ? "*PACK::Sound/*.bars" : "*.bars";
		rule.trackPattern = "Track" + std::to_string(i) + "*";
		rule.gain = static_cast<uint16>(i + 1);
		rule.mode = (i % 2) ? Router::Mode::SpatialDRC : Router::Mode::AddDRC;
		rule.audioEnabled = i % 4 != 0;
		rule.hapticPath = "haptics/" + std::to_string(i) + ".bnvib";
		rule.hapticGain = 0.25f;
		rule.hapticLoop = i % 2 != 0;
		rules.push_back(rule);
	}
	Router::RegisterRouteTable("base", rules);
	for (unsigned i = 0; i < 5000; ++i)
	{
		const std::string path = (i % 2) ? "a.pack::Sound/Voice.bars" : "b.pack::Sound/Voice.bars";
		const std::string track = (i % 10 == 0) ? "" : "Track" + std::to_string(i % 80) + "_" + std::to_string(i);
		const auto expected = ReferenceResolve(path, track);
		Check(SameRoute(expected, Router::Resolve(path, track)), "route miss/collision equivalence");
		Check(SameRoute(expected, Router::Resolve(path, track)), "route cache hit equivalence");
	}
	Router::RouteRule exact;
	exact.sourcePattern = "a.pack::Sound/Voice.bars";
	exact.trackPattern = "*";
	exact.gain = 999;
	Check(!Router::Resolve("a.pack::Sound/Voice.bars", "Unknown"), "negative cache warmup");
	Router::RegisterRouteTable("override", { exact });
	Check(Router::Resolve("a.pack::Sound/Voice.bars", "Unknown")->gain == 999, "negative invalidation");
	Check(!Router::Resolve("b.pack::Sound/Voice.bars", "Unknown"), "full path isolation");
	Check(!Router::Resolve("a.pack::Sound/Voice.bars", ""), "star does not match empty track");
	exact.gain = 777;
	Router::RegisterRouteTable("override", { exact });
	Check(Router::Resolve("a.pack::Sound/Voice.bars", "Unknown")->gain == 777, "replace invalidation");
	Router::UnregisterRouteTable("override");
	Check(!Router::Resolve("a.pack::Sound/Voice.bars", "Unknown"), "remove invalidation");

	// Serialize lookup/mutation with the production mutex; no stale references
	// may escape cache replacement, even while tables are being replaced.
	std::thread reader([] {
		for (unsigned i = 0; i < 2000; ++i)
			(void)Router::Resolve("a.pack::Sound/Voice.bars", "Track48_extra");
	});
	for (unsigned i = 0; i < 200; ++i)
	{
		Router::RegisterRouteTable("temporary", { exact });
		Router::UnregisterRouteTable("temporary");
	}
	reader.join();
	Router::UnregisterRouteTable("base");
	std::cout << "PASS: glob, 49-rule routes, collisions, invalidation, concurrent table updates\n";
}

std::optional<Tracer::SourceMatch> ReferenceSource(uint32 sampleBase)
{
	for (auto it = Tracer::s_readRanges.rbegin(); it != Tracer::s_readRanges.rend(); ++it)
	{
		if (sampleBase < it->start || sampleBase >= static_cast<uint64>(it->start) + it->size)
			continue;
		Tracer::SourceMatch result{ it->start, it->size, sampleBase - it->start, it->path, {} };
		if (Tracer::ToLower(it->path).ends_with(".bars"))
			result.trackName = Tracer::ParseBarsTrackName(*it, sampleBase);
		return result;
	}
	return std::nullopt;
}

void CompareSource(uint32 address)
{
	std::scoped_lock lock(Tracer::s_mutex);
	const auto expected = ReferenceSource(address);
	for (unsigned repeat = 0; repeat < 2; ++repeat)
	{
		const auto actual = Tracer::FindSourceLocked(address);
		Check(actual.has_value() == expected.has_value(), "range hit/miss equivalence");
		if (expected)
			Check(actual->start == expected->start && actual->size == expected->size &&
				actual->offset == expected->offset && actual->path == expected->path &&
				actual->trackName == expected->trackName, "range result equivalence");
	}
}

void Put32(uint32 address, uint32 value)
{
	for (unsigned i = 0; i < 4; ++i)
		testMemory[address + i] = static_cast<uint8>(value >> (i * 8));
}

void Magic(uint32 address, const char* value)
{
	std::copy_n(value, 4, testMemory.begin() + address);
}

void TestRanges()
{
	Tracer::RegisterFileOpen(1, "/Sound/first.bfwav");
	Tracer::RegisterFileOpen(2, "/Sound/second.bfwav");
	CompareSource(500); // Negative entry must not survive a new range.
	Tracer::RegisterRead(1, 400, 200);
	CompareSource(500);
	Tracer::RegisterRead(2, 450, 100);
	CompareSource(500); // Latest overlapping range wins.
	CompareSource(550); // Exclusive end falls back to older range.
	Tracer::RegisterFileClose(2);
	CompareSource(500); // Preserve baseline close semantics.
	Tracer::RegisterRead(1, 0xfffffff0u, 64);
	CompareSource(0xffffffffu);
	CompareSource(0);
	std::mt19937 random(0x668acee);
	for (unsigned i = 0; i < 16400; ++i)
	{
		Tracer::RegisterRead(1, 1000 + random() % 40000, 1 + random() % 200);
		if (i % 47 == 0 || i > 16380)
			for (unsigned j = 0; j < 20; ++j)
				CompareSource(random() % 45000);
	}
	Check(Tracer::s_readRanges.size() == 16384, "range eviction bound");
	CompareSource(0xffffffffu); // Cached old index must not survive front eviction.

	// Synthetic live BARS metadata: mutate the track name without any new read
	// registration. The range cache must not cache parsed guest-memory content.
	const uint32 base = 100000;
	Magic(base, "BARS"); Put32(base + 4, 256); testMemory[base + 8] = 0xff;
	Put32(base + 12, 1); Put32(base + 20, 32); Put32(base + 24, 160);
	Magic(base + 32, "AMTA"); testMemory[base + 36] = 0xff;
	Magic(base + 60, "DATA"); Magic(base + 68, "MARK");
	Magic(base + 76, "EXT_"); Magic(base + 84, "STRG"); Put32(base + 88, 4);
	Magic(base + 92, "old\0");
	Tracer::RegisterFileOpen(3, "/Sound/live.bars");
	Tracer::RegisterRead(3, base, 256);
	Check(EnhancedSoundSourceTracker::ResolveSourceCandidates(base + 160).front().trackName == "old", "live BARS initial track");
	Magic(base + 92, "new\0");
	Check(EnhancedSoundSourceTracker::ResolveSourceCandidates(base + 160).front().trackName == "new", "same address changed BARS track");
	testAccessibleSize = base;
	CompareSource(base + 160);
	testAccessibleSize = static_cast<uint32>(testMemory.size());
	CompareSource(base + 160);
	std::cout << "PASS: ranges, overlap, miss invalidation, eviction, same-address BARS writes\n";
}

std::vector<Catalog::FingerprintEntry> referenceEntries;
void ReferenceAdd(const Catalog::FingerprintEntry& entry)
{
	for (const auto& existing : referenceEntries)
		if (existing.hashA == entry.hashA && existing.hashB == entry.hashB &&
			existing.channel == entry.channel && existing.path == entry.path && existing.trackName == entry.trackName)
			return;
	referenceEntries.push_back(entry);
	if (referenceEntries.size() > 32768)
		referenceEntries.erase(referenceEntries.begin());
}

std::vector<Catalog::Match> ReferenceMatches(uint32 address, std::string_view path)
{
	std::vector<Catalog::Match> matches;
	const uint64 a = Catalog::Hash32(testMemory.data() + address);
	const uint64 b = Catalog::Hash32(testMemory.data() + address + 32);
	for (auto it = referenceEntries.rbegin(); it != referenceEntries.rend(); ++it)
	{
		if (it->hashA != a || it->hashB != b || (!path.empty() && it->path != path))
			continue;
		if (std::any_of(matches.begin(), matches.end(), [&](const auto& match) {
			return match.path == it->path && match.trackName == it->trackName;
		}))
			continue;
		matches.push_back(Catalog::ToLookupMatch(*it));
	}
	return matches;
}

void CompareMatches(uint32 address, std::string_view path = {})
{
	const auto expected = ReferenceMatches(address, path);
	const auto actual = Catalog::FindMatches(address, path);
	Check(expected.size() == actual.size(), "fingerprint candidate count");
	for (size_t i = 0; i < expected.size(); ++i)
		Check(expected[i].path == actual[i].path && expected[i].trackName == actual[i].trackName &&
			expected[i].sourceStart == actual[i].sourceStart && expected[i].sourceSize == actual[i].sourceSize &&
			expected[i].dataOffset == actual[i].dataOffset, "fingerprint order and metadata");
}

void AddBoth(const Catalog::FingerprintEntry& entry)
{
	ReferenceAdd(entry);
	std::scoped_lock lock(Catalog::s_mutex);
	Catalog::AddEntryLocked(entry);
	Check(referenceEntries.size() == Catalog::s_entries.size(), "dedup identity equivalence");
}

void TestCatalog()
{
	const uint32 sample = 500000;
	for (unsigned i = 0; i < 64; ++i)
		testMemory[sample + i] = static_cast<uint8>(i * 7);
	Catalog::FingerprintEntry entry;
	entry.hashA = Catalog::Hash32(testMemory.data() + sample);
	entry.hashB = Catalog::Hash32(testMemory.data() + sample + 32);
	entry.path = "pack::Sound/a.bars";
	entry.trackName = "trackA";
	entry.sourceStart = 100;
	entry.sourceSize = 200;
	entry.dataOffset = 64;
	AddBoth(entry);
	entry.sourceStart = 999; // Location is deliberately NOT part of baseline dedup.
	AddBoth(entry);
	entry.channel = 1; entry.dataOffset = 128;
	AddBoth(entry); // A distinct channel must remain registered.
	entry.trackName = "trackB";
	AddBoth(entry);
	entry.path = "other::Sound/a.bars";
	AddBoth(entry);
	CompareMatches(sample);
	CompareMatches(sample, "pack::Sound/a.bars");
	CompareMatches(sample, "PACK::Sound/a.bars"); // Exact, case-sensitive expectedPath.
	Check(EnhancedSoundSourceTracker::ResolveSourceCandidates(sample).size() == 3, "all ambiguous candidates preserved");
	testMemory[sample] ^= 0xff;
	CompareMatches(sample);
	Check(EnhancedSoundSourceTracker::ResolveSourceCandidates(sample).empty(), "same-address fingerprint write revalidated");
	testMemory[sample] ^= 0xff;
	CompareMatches(sample);

	// Fill with known distinct hashes without an O(N^2) oracle setup. Then check
	// real FIFO evictions, stale pointer removal, and re-registration of evictees.
	while (referenceEntries.size() < 32768)
	{
		Catalog::FingerprintEntry unique = entry;
		unique.hashA = referenceEntries.size();
		unique.hashB = 123;
		referenceEntries.push_back(unique);
		Catalog::AddEntryLocked(unique);
	}
	for (unsigned i = 0; i < 20; ++i)
	{
		Catalog::FingerprintEntry unique = entry;
		unique.hashA = 1000000 + i; unique.hashB = 123;
		AddBoth(unique);
		CompareMatches(sample);
	}
	AddBoth(entry);
	AddBoth(entry);
	CompareMatches(sample);
	Check(Catalog::s_registrationIndex.size() == Catalog::s_entries.size(), "registration index eviction bound");
	std::cout << "PASS: dedup identity, candidate order, ambiguity, guest writes, catalog eviction/re-registration\n";
}

int main()
{
	try
	{
		TestRoutes();
		TestRanges();
		TestCatalog();
		return 0;
	}
	catch (const std::exception& error)
	{
		std::cerr << "FAIL: " << error.what() << '\n';
		return 1;
	}
}
