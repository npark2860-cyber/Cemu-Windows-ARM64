#pragma once

#include <algorithm>
#include <cctype>
#include <cstdint>
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

	inline std::string Normalize(std::string_view value)
	{
		std::string out(value);
		std::transform(out.begin(), out.end(), out.begin(), [](unsigned char c) {
			if (c == '\\')
				return '/';
			return static_cast<char>(std::tolower(c));
		});
		return out;
	}

	inline bool GlobMatch(std::string_view patternValue, std::string_view textValue)
	{
		const std::string pattern = Normalize(patternValue);
		const std::string text = Normalize(textValue);
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
		s_tables.erase(std::remove_if(s_tables.begin(), s_tables.end(), [&](const RouteTable& table) {
			return table.owner == owner;
		}), s_tables.end());
		if (!rules.empty())
			s_tables.push_back({ std::move(owner), std::move(rules) });
	}

	inline void UnregisterRouteTable(std::string_view owner)
	{
		std::scoped_lock lock(s_mutex);
		s_tables.erase(std::remove_if(s_tables.begin(), s_tables.end(), [&](const RouteTable& table) {
			return table.owner == owner;
		}), s_tables.end());
	}

	inline std::optional<RouteMatch> Resolve(std::string_view sourcePath, std::string_view trackName)
	{
		std::scoped_lock lock(s_mutex);
		for (auto table = s_tables.rbegin(); table != s_tables.rend(); ++table)
		{
			for (const auto& rule : table->rules)
			{
				if (!MatchSource(rule.sourcePattern, sourcePath) || !MatchTrack(rule.trackPattern, trackName))
					continue;
				return RouteMatch{
					rule.audioEnabled,
					rule.mode,
					rule.gain,
					rule.tvVolumePercent,
					rule.hapticPath,
					rule.hapticGain,
					rule.hapticLoop
				};
			}
		}
		return std::nullopt;
	}
}
