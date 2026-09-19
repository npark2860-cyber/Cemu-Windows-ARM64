#pragma once

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <limits>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <vector>

namespace EnhancedHapticEngine
{
	struct Sample
	{
		uint8_t amplitudeLow{};
		uint8_t frequencyLow{};
		uint8_t amplitudeHigh{};
		uint8_t frequencyHigh{};
	};

	struct Loop
	{
		uint32_t startSample{};
		uint32_t endSample{};
		uint32_t intervalSamples{};
	};

	struct Clip
	{
		uint16_t sampleRateHz{};
		std::vector<Sample> samples;
		std::optional<Loop> loop;
	};

	struct Frame
	{
		uint8_t lowLevel{};
		uint8_t highLevel{};
		float lowFrequencyHz{};
		float highFrequencyHz{};
	};

	inline uint16_t ReadLE16(const std::vector<uint8_t>& data, size_t offset)
	{
		return static_cast<uint16_t>(data[offset]) |
			(static_cast<uint16_t>(data[offset + 1]) << 8);
	}

	inline uint32_t ReadLE32(const std::vector<uint8_t>& data, size_t offset)
	{
		return static_cast<uint32_t>(data[offset]) |
			(static_cast<uint32_t>(data[offset + 1]) << 8) |
			(static_cast<uint32_t>(data[offset + 2]) << 16) |
			(static_cast<uint32_t>(data[offset + 3]) << 24);
	}

	inline float DecodeFrequency(uint8_t encoded)
	{
		return 10.0f * std::pow(2.0f, static_cast<float>(encoded) / 32.0f);
	}

	inline bool ParseBnvib(const std::vector<uint8_t>& data, Clip& outClip, std::string* error = nullptr)
	{
		auto fail = [&](const char* message) {
			if (error)
				*error = message;
			return false;
		};

		if (data.size() < 12)
			return fail("BNVIB file is too small");

		const uint32_t metadataSize = ReadLE32(data, 0);
		if (metadataSize != 4 && metadataSize != 12 && metadataSize != 16)
			return fail("Unsupported BNVIB metadata size");

		if (ReadLE16(data, 4) != 3)
			return fail("Unsupported BNVIB format version");

		const uint16_t sampleRateHz = ReadLE16(data, 6);
		if (sampleRateHz == 0)
			return fail("BNVIB sample rate is zero");

		size_t dataSizeOffset = 8;
		size_t sampleOffset = 12;
		std::optional<Loop> loop;
		if (metadataSize >= 12)
		{
			if (data.size() < 20)
				return fail("BNVIB loop header is truncated");
			Loop parsedLoop;
			parsedLoop.startSample = ReadLE32(data, 8);
			parsedLoop.endSample = ReadLE32(data, 12);
			parsedLoop.intervalSamples = 0;
			if (metadataSize == 16)
			{
				if (data.size() < 24)
					return fail("BNVIB loop-wait header is truncated");
				parsedLoop.intervalSamples = ReadLE32(data, 16);
				dataSizeOffset = 20;
				sampleOffset = 24;
			}
			else
			{
				dataSizeOffset = 16;
				sampleOffset = 20;
			}
			loop = parsedLoop;
		}

		if (dataSizeOffset + sizeof(uint32_t) > data.size())
			return fail("BNVIB data-size field is truncated");

		const uint32_t dataSize = ReadLE32(data, dataSizeOffset);
		if ((dataSize % 4u) != 0)
			return fail("BNVIB sample data is not aligned to four bytes");
		if (sampleOffset > data.size() || dataSize > data.size() - sampleOffset)
			return fail("BNVIB sample data exceeds file size");

		Clip parsed;
		parsed.sampleRateHz = sampleRateHz;
		parsed.samples.reserve(dataSize / 4u);
		for (size_t offset = sampleOffset; offset < sampleOffset + dataSize; offset += 4)
		{
			parsed.samples.push_back({data[offset], data[offset + 1], data[offset + 2], data[offset + 3]});
		}

		if (parsed.samples.empty())
			return fail("BNVIB contains no samples");
		if (loop)
		{
			if (loop->startSample >= loop->endSample || loop->endSample > parsed.samples.size())
				return fail("BNVIB loop range exceeds sample data");
			parsed.loop = loop;
		}

		outClip = std::move(parsed);
		return true;
	}

	inline bool LoadBnvib(const std::filesystem::path& path, Clip& outClip, std::string* error = nullptr)
	{
		std::ifstream file(path, std::ios::binary);
		if (!file)
		{
			if (error)
				*error = "Unable to open BNVIB file";
			return false;
		}

		file.seekg(0, std::ios::end);
		const auto length = file.tellg();
		if (length <= 0)
		{
			if (error)
				*error = "BNVIB file is empty";
			return false;
		}
		file.seekg(0, std::ios::beg);

		std::vector<uint8_t> data(static_cast<size_t>(length));
		if (!file.read(reinterpret_cast<char*>(data.data()), static_cast<std::streamsize>(data.size())))
		{
			if (error)
				*error = "Unable to read BNVIB file";
			return false;
		}
		return ParseBnvib(data, outClip, error);
	}

	class Player
	{
	public:
		using Clock = std::chrono::steady_clock;

		void Play(std::shared_ptr<const Clip> clip, float gain = 1.0f)
		{
			std::scoped_lock lock(m_mutex);
			m_clip = std::move(clip);
			m_gain = std::clamp(gain, 0.0f, 1.0f);
			m_started = {};
			m_startedValid = false;
			m_lastOutputKey = kNoOutput;
			m_active = static_cast<bool>(m_clip) && !m_clip->samples.empty() && m_clip->sampleRateHz != 0;
			m_pendingStopFrame = false;
		}

		void Stop()
		{
			std::scoped_lock lock(m_mutex);
			m_active = false;
			m_clip.reset();
			m_startedValid = false;
			m_lastOutputKey = kNoOutput;
			m_pendingStopFrame = true;
		}

		[[nodiscard]] bool IsActive() const
		{
			std::scoped_lock lock(m_mutex);
			return m_active;
		}

		std::optional<Frame> Tick(Clock::time_point now = Clock::now())
		{
			std::scoped_lock lock(m_mutex);
			if (!m_active || !m_clip)
			{
				if (m_pendingStopFrame)
				{
					m_pendingStopFrame = false;
					return Frame{};
				}
				return std::nullopt;
			}

			if (!m_startedValid)
			{
				m_started = now;
				m_startedValid = true;
			}

			const auto elapsedUs = std::chrono::duration_cast<std::chrono::microseconds>(now - m_started).count();
			const uint64_t rawIndex = (static_cast<uint64_t>(std::max<int64_t>(0, elapsedUs)) * m_clip->sampleRateHz) / 1000000ull;

			uint64_t outputKey = rawIndex;
			std::optional<size_t> sampleIndex;
			if (m_clip->loop)
			{
				const auto& loop = *m_clip->loop;
				if (rawIndex < loop.endSample)
				{
					sampleIndex = static_cast<size_t>(rawIndex);
				}
				else
				{
					const uint64_t loopLength = static_cast<uint64_t>(loop.endSample - loop.startSample);
					const uint64_t loopSpan = loopLength + loop.intervalSamples;
					if (loopSpan == 0)
					{
						m_active = false;
						m_pendingStopFrame = false;
						return Frame{};
					}

					const uint64_t position = (rawIndex - loop.endSample) % loopSpan;
					if (position < loop.intervalSamples)
						outputKey = kLoopSilence;
					else
						sampleIndex = static_cast<size_t>(loop.startSample + (position - loop.intervalSamples));
				}
			}
			else if (rawIndex < m_clip->samples.size())
			{
				sampleIndex = static_cast<size_t>(rawIndex);
			}
			else
			{
				m_active = false;
				m_pendingStopFrame = false;
				return Frame{};
			}

			if (outputKey == m_lastOutputKey)
				return std::nullopt;
			m_lastOutputKey = outputKey;

			if (!sampleIndex)
				return Frame{};

			const auto& sample = m_clip->samples[*sampleIndex];
			auto scale = [this](uint8_t value) {
				return static_cast<uint8_t>(std::clamp(static_cast<int>(std::lround(value * m_gain)), 0, 255));
			};
			return Frame{
				scale(sample.amplitudeLow),
				scale(sample.amplitudeHigh),
				DecodeFrequency(sample.frequencyLow),
				DecodeFrequency(sample.frequencyHigh),
			};
		}

	private:
		static constexpr uint64_t kNoOutput = std::numeric_limits<uint64_t>::max();
		static constexpr uint64_t kLoopSilence = std::numeric_limits<uint64_t>::max() - 1;

		mutable std::mutex m_mutex;
		std::shared_ptr<const Clip> m_clip;
		Clock::time_point m_started{};
		bool m_startedValid{};
		float m_gain{1.0f};
		uint64_t m_lastOutputKey{kNoOutput};
		bool m_active{};
		bool m_pendingStopFrame{};
	};
}
