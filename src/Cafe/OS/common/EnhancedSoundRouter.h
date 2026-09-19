#pragma once

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <functional>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace EnhancedSoundRouter
{
	enum class Mode : uint8_t
	{
		AddDRC = 1,
		SpatialDRC = 2,
	};

	struct RouteRule
	{
		std::string sourcePattern;
		std::string trackPattern;
		bool audioEnabled{ true };
		Mode mode{ Mode::AddDRC };
		uint16_t gain{ 0x6000 };
		uint8_t tvVolume{ 50 };
		uint8_t tvVolumePercent{ 50 };
		std::string hapticPath;
		float hapticGain{ 1.0f };
		bool hapticLoop{};
	};

	struct RouteMatch
	{
		bool audioEnabled{ true };
		Mode mode{ Mode::AddDRC };
		uint16_t gain{ 0x6000 };
		uint8_t tvVolumePercent{ 50 };
		std::string hapticPath;
		float hapticGain{ 1.0f };
		bool hapticLoop{};
	};

	struct RouteTable
	{
		std::string owner;
		std::vector<RouteRule> rules;
	};

	inline std::mutex s_mutex;
	inline std::vector<RouteTable> s_tables;
	struct RouteCacheEntry
	{
		bool valid{};
		std::string sourcePath;
		std::string trackName;
		std::optional<RouteMatch> route;
	};
	inline std::array<RouteCacheEntry, 1024> s_routeCache{};

	inline void InvalidateRouteCacheLocked()
	{
		for (auto& entry : s_routeCache)
			entry.valid = false;
	}

	inline char NormalizeCharacter(unsigned char c)
	{
		return c == '\\' ? '/' : static_cast<char>(std::tolower(c));
	}

	inline std::string Normalize(std::string_view value)
	{
		std::string out(value);
		std::transform(out.begin(), out.end(), out.begin(), NormalizeCharacter);
		return out;
	}

	inline bool GlobMatch(std::string_view pattern, std::string_view text)
	{
		// Normalize only compared characters. Preserve the original greedy-star
		// algorithm, case/slash semantics, and literal '?' without temporary strings.
		size_t p = 0, t = 0, star = std::string::npos, retry = 0;
		while (t < text.size())
		{
			if (p < pattern.size() && NormalizeCharacter(pattern[p]) == NormalizeCharacter(text[t]))
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
			{
				return false;
			}
		}
		while (p < pattern.size() && pattern[p] == '*')
			++p;
		return p == pattern.size();
	}

	inline std::string_view BaseName(std::string_view path)
	{
		const auto pos = path.find_last_of("/\\");
		return pos == std::string_view::npos ? path : path.substr(pos + 1);
	}

	inline bool MatchSource(std::string_view pattern, std::string_view sourcePath)
	{
		if (pattern.empty())
			return true;
		const bool hasPath = pattern.find('/') != std::string_view::npos || pattern.find('\\') != std::string_view::npos;
		return GlobMatch(pattern, hasPath ? sourcePath : BaseName(sourcePath));
	}

	inline bool MatchTrack(std::string_view pattern, std::string_view trackName)
	{
		if (pattern.empty())
			return true;
		if (trackName.empty())
			return false;
		return GlobMatch(pattern, trackName);
	}

	inline bool Equivalent(const RouteMatch& a, const RouteMatch& b)
	{
		return a.audioEnabled == b.audioEnabled &&
			a.mode == b.mode &&
			a.gain == b.gain &&
			a.tvVolumePercent == b.tvVolumePercent &&
			a.hapticPath == b.hapticPath &&
			a.hapticGain == b.hapticGain &&
			a.hapticLoop == b.hapticLoop;
	}

	inline void RegisterRouteTable(std::string owner, std::vector<RouteRule> rules)
	{
		std::scoped_lock lock(s_mutex);
		InvalidateRouteCacheLocked();
		s_tables.erase(std::remove_if(s_tables.begin(), s_tables.end(), [&](const RouteTable& table) {
			return table.owner == owner;
		}), s_tables.end());
		if (!rules.empty())
			s_tables.push_back({ std::move(owner), std::move(rules) });
	}

	inline void UnregisterRouteTable(std::string_view owner)
	{
		std::scoped_lock lock(s_mutex);
		InvalidateRouteCacheLocked();
		s_tables.erase(std::remove_if(s_tables.begin(), s_tables.end(), [&](const RouteTable& table) {
			return table.owner == owner;
		}), s_tables.end());
	}

	inline std::optional<RouteMatch> Resolve(std::string_view sourcePath, std::string_view trackName)
	{
		std::scoped_lock lock(s_mutex);
		const size_t sourceHash = std::hash<std::string_view>{}(sourcePath);
		const size_t trackHash = std::hash<std::string_view>{}(trackName);
		auto& cached = s_routeCache[(sourceHash ^ (trackHash + (sourceHash << 6) + (sourceHash >> 2))) % s_routeCache.size()];
		// Exact full-path + track equality, not hash equality, determines a hit.
		// Keep negative results too. Table replacement/removal invalidates both.
		if (cached.valid && cached.sourcePath == sourcePath && cached.trackName == trackName)
			return cached.route;
		cached.valid = false;
		cached.sourcePath = sourcePath;
		cached.trackName = trackName;
		cached.route.reset();
		for (auto table = s_tables.rbegin(); table != s_tables.rend(); ++table)
		{
			for (const auto& rule : table->rules)
			{
				if (!MatchSource(rule.sourcePattern, sourcePath) || !MatchTrack(rule.trackPattern, trackName))
					continue;
				cached.route = RouteMatch{
					rule.audioEnabled,
					rule.mode,
					rule.gain,
					rule.tvVolumePercent,
					rule.hapticPath,
					rule.hapticGain,
					rule.hapticLoop
				};
				cached.valid = true;
				return cached.route;
			}
		}
		cached.valid = true;
		return cached.route;
	}
}
