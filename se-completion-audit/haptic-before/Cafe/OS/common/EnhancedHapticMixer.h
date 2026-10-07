#pragma once

#include "EnhancedHapticEngine.h"
#include <unordered_map>

namespace EnhancedHapticEngine
{
	// Independent timelines, keyed by playback generation rather than reusable AX indices.
	// The backend currently transports amplitudes only: combine by channel maximum,
	// avoiding clipping/strength multiplication for duplicated stereo voices.
	class Mixer
	{
	public:
		using Clock = Player::Clock;
		static constexpr size_t Capacity = 256;
		static constexpr auto VoiceLease = std::chrono::milliseconds(100);

		uint64_t Play(std::shared_ptr<const Clip> clip, float gain, bool voiceBound = false,
			Clock::time_point now = Clock::now())
		{
			if (!clip || clip->samples.empty() || !clip->sampleRateHz)
				return 0;
			std::scoped_lock lock(m_mutex);
			if (m_entries.size() >= Capacity || m_nextId == 0)
				return 0;
			const auto id = m_nextId++;
			auto& entry = m_entries[id];
			entry.player.Play(std::move(clip));
			entry.gain = ClampGain(gain);
			entry.voiceBound = voiceBound;
			entry.updated = now;
			// Wait for the first synchronized AX snapshot before producing output.
			entry.hasSnapshot = !voiceBound;
			return id;
		}

		void Update(uint64_t id, float gain, Clock::time_point now = Clock::now())
		{
			std::scoped_lock lock(m_mutex);
			if (auto it = m_entries.find(id); it != m_entries.end())
			{
				it->second.gain = ClampGain(gain);
				it->second.updated = now;
				it->second.hasSnapshot = true;
			}
		}

		void Stop(uint64_t id = 0)
		{
			std::scoped_lock lock(m_mutex);
			if (id == 0)
				m_entries.clear();
			else
				m_entries.erase(id);
		}

		bool IsActive() const
		{
			std::scoped_lock lock(m_mutex);
			return !m_entries.empty();
		}

		std::optional<Frame> Tick(Clock::time_point now = Clock::now(), bool forceOutput = false)
		{
			std::scoped_lock lock(m_mutex);
			Frame output{};
			for (auto it = m_entries.begin(); it != m_entries.end();)
			{
				auto& entry = it->second;
				if (auto frame = entry.player.Tick(now))
					entry.frame = *frame;
				if (!entry.player.IsActive())
				{
					it = m_entries.erase(it);
					continue;
				}
				if (entry.hasSnapshot && (!entry.voiceBound || now - entry.updated < VoiceLease))
				{
					output.lowLevel = std::max(output.lowLevel, Scale(entry.frame.lowLevel, entry.gain));
					output.highLevel = std::max(output.highLevel, Scale(entry.frame.highLevel, entry.gain));
				}
				++it;
			}
			const int key = output.lowLevel | (output.highLevel << 8);
			if (!forceOutput && key == m_lastOutput)
				return std::nullopt;
			m_lastOutput = key;
			return output;
		}

		static float ClampGain(float gain)
		{
			return std::isfinite(gain) ? std::clamp(gain, 0.0f, 1.0f) : 0.0f;
		}

	private:
		static uint8_t Scale(uint8_t level, float gain)
		{
			return static_cast<uint8_t>(std::lround(level * gain));
		}
		struct Entry
		{
			Player player;
			Frame frame{};
			Clock::time_point updated{};
			float gain{};
			bool voiceBound{};
			bool hasSnapshot{};
		};
		mutable std::mutex m_mutex;
		std::unordered_map<uint64_t, Entry> m_entries;
		uint64_t m_nextId{1};
		int m_lastOutput{-1};
	};
}
