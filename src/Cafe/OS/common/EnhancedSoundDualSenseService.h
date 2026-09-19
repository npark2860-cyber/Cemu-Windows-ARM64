#pragma once

#include "Cafe/OS/common/EnhancedHapticEngine.h"

#include <cstdint>
#include <filesystem>
#include <string>

#ifdef _WIN32

#include "Cafe/OS/common/BotwBowAdaptiveTrigger.h"
#include "config/CemuConfig.h"
#include "GCore/Interfaces/IPlatformHardware.h"
#include "GCore/Templates/TBasicDeviceRegistry.h"
#include "GCore/Types/Structs/Context/DeviceContext.h"
#include "Platform/windows/windows_hardware_policy.h"

#include <chrono>
#include <cstdint>
#include <memory>
#include <mutex>
#include <optional>
#include <thread>
#include <unordered_map>

namespace EnhancedSoundDualSenseService
{
	struct RegistryPolicy
	{
		using EngineIdType = uint32_t;
		struct Hasher
		{
			size_t operator()(const EngineIdType& id) const { return std::hash<EngineIdType>{}(id); }
		};
		static EngineIdType AllocEngineDevice()
		{
			static EngineIdType nextId = 0;
			return nextId++;
		}
		static void DisconnectDevice(EngineIdType) {}
		static void DispatchNewGamepad(EngineIdType) {}
	};

	class Registry : public GamepadCore::TBasicDeviceRegistry<RegistryPolicy>
	{
	public:
		using TBasicDeviceRegistry<RegistryPolicy>::TBasicDeviceRegistry;
		using TBasicDeviceRegistry<RegistryPolicy>::GetLibrary;
	};

	inline std::mutex s_startMutex;
	inline std::unique_ptr<std::jthread> s_worker;
	inline EnhancedHapticEngine::Player s_hapticPlayer;

	inline std::mutex s_clipCacheMutex;
	inline std::unordered_map<std::filesystem::path, std::shared_ptr<const EnhancedHapticEngine::Clip>> s_oneShotClipCache;
	inline std::unordered_map<std::filesystem::path, std::shared_ptr<const EnhancedHapticEngine::Clip>> s_loopClipCache;

	inline std::mutex s_playbackMutex;
	inline uint64_t s_nextPlaybackId{ 1 };
	inline uint64_t s_activePlaybackId{};

	struct AdaptiveTriggerRequest
	{
		bool active{};
		uint8_t startZoneMask{};
		uint8_t forcePair{};
		uint8_t tensionPercent{};
		std::string actorId;
	};

	inline std::mutex s_triggerMutex;
	inline AdaptiveTriggerRequest s_triggerRequest;
	inline uint64_t s_triggerRevision{};

	inline bool IsEligibleUsbDualSense(IGamepadBase* gamepad)
	{
		if (!gamepad || !gamepad->IsConnected())
			return false;
		auto* ctx = gamepad->GetMutableDeviceContext();
		if (!ctx || ctx->ConnectionType != EDSDeviceConnection::Usb)
			return false;
		return ctx->DeviceType == EDSDeviceType::DualSense || ctx->DeviceType == EDSDeviceType::DualSenseEdge;
	}

	inline bool ConfigureOutputState(IGamepadBase* gamepad, bool headsetConnected, bool hapticsEnabled)
	{
		if (!IsEligibleUsbDualSense(gamepad))
			return false;
		auto* settings = gamepad->GetIGamepadSettings();
		if (!settings)
			return false;

		// Preserve the current Release+SE jack-detect routing while switching only
		// the DualSense rumble transport when a BNVIB clip is active.
		settings->DualSenseSettings(
			0,                         // mic state
			headsetConnected ? 1 : 0, // headset follows physical jack state
			headsetConnected ? 0 : 1, // internal speaker only while unplugged
			0,                         // mic volume
			255,                       // audio volume
			hapticsEnabled ? 0 : 255,  // non-255 => DualSense HapticsRumble transport
			0,                         // rumble reduction
			0);                        // trigger reduction
		gamepad->UpdateOutput();
		return true;
	}

	inline std::shared_ptr<const EnhancedHapticEngine::Clip> GetCachedClip(
		const std::filesystem::path& path, bool useLoop, std::string* error)
	{
		const auto normalizedPath = path.lexically_normal();
		{
			std::scoped_lock lock(s_clipCacheMutex);
			auto& cache = useLoop ? s_loopClipCache : s_oneShotClipCache;
			const auto it = cache.find(normalizedPath);
			if (it != cache.end())
				return it->second;
		}

		EnhancedHapticEngine::Clip clip;
		if (!EnhancedHapticEngine::LoadBnvib(normalizedPath, clip, error))
			return {};
		if (!useLoop)
			clip.loop.reset();

		auto loaded = std::make_shared<EnhancedHapticEngine::Clip>(std::move(clip));
		{
			std::scoped_lock lock(s_clipCacheMutex);
			auto& cache = useLoop ? s_loopClipCache : s_oneShotClipCache;
			const auto [it, inserted] = cache.emplace(normalizedPath, loaded);
			if (!inserted)
				return it->second;
		}
		return loaded;
	}

	inline void EnsureRunning();

	inline bool PlayBnvib(const std::filesystem::path& path, float gain = 1.0f, bool useLoop = false,
		uint64_t* playbackId = nullptr, std::string* error = nullptr)
	{
		auto clip = GetCachedClip(path, useLoop, error);
		if (!clip)
			return false;

		EnsureRunning();

		uint64_t id;
		{
			std::scoped_lock lock(s_playbackMutex);
			if (s_nextPlaybackId == 0)
				s_nextPlaybackId = 1;
			id = s_nextPlaybackId++;
			s_activePlaybackId = id;
			s_hapticPlayer.Play(std::move(clip), gain);
		}
		if (playbackId)
			*playbackId = id;
		return true;
	}

	inline void StopHaptics(uint64_t playbackId = 0)
	{
		std::scoped_lock lock(s_playbackMutex);
		if (playbackId != 0 && s_activePlaybackId != playbackId)
			return;
		s_activePlaybackId = 0;
		s_hapticPlayer.Stop();
	}


	inline bool ApplyBotwBowTrigger(uint8_t minTensionPercent = 40, uint8_t maxTensionPercent = 85,
		uint8_t startZone = 2, std::string* error = nullptr)
	{
		const auto profile = BotwBowAdaptiveTrigger::ResolveEquippedBow(
			minTensionPercent, maxTensionPercent, startZone);
		if (!profile)
		{
			if (error)
				*error = "BOTW v208 equipped bow could not be resolved";
			return false;
		}

		EnsureRunning();
		std::scoped_lock lock(s_triggerMutex);
		const bool changed =
			!s_triggerRequest.active ||
			s_triggerRequest.startZoneMask != profile->startZoneMask ||
			s_triggerRequest.forcePair != profile->forcePair ||
			s_triggerRequest.tensionPercent != profile->tensionPercent ||
			s_triggerRequest.actorId != profile->actorId;
		if (changed)
		{
			s_triggerRequest.active = true;
			s_triggerRequest.startZoneMask = profile->startZoneMask;
			s_triggerRequest.forcePair = profile->forcePair;
			s_triggerRequest.tensionPercent = profile->tensionPercent;
			s_triggerRequest.actorId = profile->actorId;
			++s_triggerRevision;
		}
		return true;
	}

	inline void StopAdaptiveTrigger()
	{
		std::scoped_lock lock(s_triggerMutex);
		if (!s_triggerRequest.active)
			return;
		s_triggerRequest = {};
		++s_triggerRevision;
	}

	inline void Worker(std::stop_token stopToken)
	{
		try
		{
			IPlatformHardware::SetInstance(std::make_unique<windows_platform::windows_hardware>());
			Registry registry;
			registry.RequestImmediateDetection();

			using Clock = std::chrono::steady_clock;
			auto nextDevicePoll = Clock::now();
			bool outputConfigured = false;
			bool configuredHeadsetConnected = false;
			bool configuredHapticsEnabled = false;
			bool lastHeadsetConnected = false;
			bool hadHaptics = false;
			bool hadAdaptiveTrigger = false;
			uint64_t appliedTriggerRevision = 0;

			while (!stopToken.stop_requested())
			{
				const auto now = Clock::now();
				if (now >= nextDevicePoll)
				{
					registry.PlugAndPlay(0.1f);
					auto* polledGamepad = registry.GetLibrary(0);
					if (IsEligibleUsbDualSense(polledGamepad))
					{
						polledGamepad->UpdateInput(0.1f);
						auto* ctx = polledGamepad->GetMutableDeviceContext();
						const auto* input = ctx ? ctx->GetInputState() : nullptr;
						lastHeadsetConnected = input && input->bHasPhoneConnected;
					}
					else
					{
						registry.RequestImmediateDetection();
					}
					nextDevicePoll = now + std::chrono::milliseconds(100);
				}

				auto* gamepad = registry.GetLibrary(0);
				if (!IsEligibleUsbDualSense(gamepad))
				{
					outputConfigured = false;
					hadHaptics = false;
					hadAdaptiveTrigger = false;
					appliedTriggerRevision = 0;
					std::this_thread::sleep_for(std::chrono::milliseconds(2));
					continue;
				}

				if (!GetConfig().enhanced_sound_experience)
				{
					if (s_hapticPlayer.IsActive())
						StopHaptics();
					StopAdaptiveTrigger();
				}

				AdaptiveTriggerRequest triggerRequest;
				uint64_t triggerRevision;
				{
					std::scoped_lock lock(s_triggerMutex);
					triggerRequest = s_triggerRequest;
					triggerRevision = s_triggerRevision;
				}

				const auto hapticFrame = s_hapticPlayer.Tick(now);
				const bool hapticsEnabled = s_hapticPlayer.IsActive() || hapticFrame.has_value();
				const bool serviceEnabled =
					GetConfig().enhanced_sound_experience || hapticsEnabled || hadHaptics ||
					triggerRequest.active || hadAdaptiveTrigger;

				if (serviceEnabled &&
					(!outputConfigured ||
					 configuredHeadsetConnected != lastHeadsetConnected ||
					 configuredHapticsEnabled != hapticsEnabled))
				{
					outputConfigured = ConfigureOutputState(gamepad, lastHeadsetConnected, hapticsEnabled);
					if (outputConfigured)
					{
						configuredHeadsetConnected = lastHeadsetConnected;
						configuredHapticsEnabled = hapticsEnabled;
					}
				}
				else if (!serviceEnabled)
				{
					outputConfigured = false;
				}

				if (hapticFrame)
				{
					if (auto* rumble = gamepad->GetIGamepadRumbles())
					{
						// Phase-1 backend: preserve BNVIB low/high amplitudes through
						// Gamepad-Core's DualSense HapticsRumble transport. Frequency
						// metadata stays available in the parsed frame for a later
						// audio-haptics backend.
						rumble->SetVibration(hapticFrame->lowLevel, hapticFrame->highLevel);
						gamepad->UpdateOutput();
					}
				}

				if (triggerRevision != appliedTriggerRevision)
				{
					if (auto* trigger = gamepad->GetIGamepadTrigger())
					{
						if (triggerRequest.active)
							trigger->SetBow22(triggerRequest.startZoneMask, triggerRequest.forcePair, EDSGamepadHand::Right);
						else
							trigger->StopTrigger(EDSGamepadHand::Right);
						gamepad->UpdateOutput();
						appliedTriggerRevision = triggerRevision;
					}
				}

				hadHaptics = hapticsEnabled;
				hadAdaptiveTrigger = triggerRequest.active;
				std::this_thread::sleep_for(std::chrono::milliseconds(2));
			}
		}
		catch (...)
		{
			// Enhanced Sound/Haptics are optional and must never make Cemu fatal.
		}
	}

	inline void EnsureRunning()
	{
		std::scoped_lock lock(s_startMutex);
		if (!s_worker)
			s_worker = std::make_unique<std::jthread>(Worker);
	}
}

#else
namespace EnhancedSoundDualSenseService
{
	inline void EnsureRunning() {}
	inline bool PlayBnvib(const std::filesystem::path&, float = 1.0f, bool = false,
		uint64_t* = nullptr, std::string* error = nullptr)
	{
		if (error)
			*error = "DualSense BNVIB playback is only available on Windows";
		return false;
	}
	inline void StopHaptics(uint64_t = 0) {}
	inline bool ApplyBotwBowTrigger(uint8_t = 40, uint8_t = 85, uint8_t = 2, std::string* error = nullptr)
	{
		if (error)
			*error = "DualSense adaptive triggers are only available on Windows";
		return false;
	}
	inline void StopAdaptiveTrigger() {}
}
#endif
