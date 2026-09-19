#pragma once

#include "Cafe/OS/common/EnhancedHapticEngine.h"

#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <string>

#ifdef _WIN32

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
		bool leftHand{};
		uint8_t startZoneMask{};
		uint8_t forcePair{};
		uint8_t tensionPercent{};
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


	inline bool ApplyAdaptiveTriggerBow(uint8_t tensionPercent, uint8_t startZone = 2, bool leftHand = false)
	{
		if (!GetConfig().enhanced_sound_experience)
			return false;

		const uint8_t safeTension = std::min<uint8_t>(tensionPercent, 100u);
		if (safeTension == 0)
		{
			std::scoped_lock lock(s_triggerMutex);
			if (s_triggerRequest.active)
			{
				s_triggerRequest = {};
				++s_triggerRevision;
			}
			return true;
		}

		const uint8_t hardwareStrength = static_cast<uint8_t>(std::clamp(
			(static_cast<int>(safeTension) * 8 + 50) / 100, 1, 8));
		const uint8_t encodedForce = static_cast<uint8_t>(hardwareStrength - 1u);
		const uint8_t forcePair = static_cast<uint8_t>(encodedForce | (encodedForce << 3));
		const uint8_t safeStartZone = std::min<uint8_t>(startZone, 7u);
		const uint8_t startZoneMask = static_cast<uint8_t>(1u << safeStartZone);

		EnsureRunning();
		std::scoped_lock lock(s_triggerMutex);
		const bool changed =
			!s_triggerRequest.active ||
			s_triggerRequest.leftHand != leftHand ||
			s_triggerRequest.startZoneMask != startZoneMask ||
			s_triggerRequest.forcePair != forcePair ||
			s_triggerRequest.tensionPercent != safeTension;
		if (changed)
		{
			s_triggerRequest.active = true;
			s_triggerRequest.leftHand = leftHand;
			s_triggerRequest.startZoneMask = startZoneMask;
			s_triggerRequest.forcePair = forcePair;
			s_triggerRequest.tensionPercent = safeTension;
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
			auto nextInputPoll = Clock::now();
			bool outputConfigured = false;
			bool configuredHeadsetConnected = false;
			bool configuredHapticsEnabled = false;
			bool lastHeadsetConnected = false;
			float lastLeftTriggerAnalog = 0.0f;
			float lastRightTriggerAnalog = 0.0f;
			bool triggerPulledSinceApply = false;
			bool hadHaptics = false;
			bool hadAdaptiveTrigger = false;
			bool appliedTriggerLeftHand = false;
			uint64_t appliedTriggerRevision = 0;

			while (!stopToken.stop_requested())
			{
				const auto now = Clock::now();
				if (now >= nextDevicePoll)
				{
					registry.PlugAndPlay(0.1f);
					auto* polledGamepad = registry.GetLibrary(0);
					if (!IsEligibleUsbDualSense(polledGamepad))
						registry.RequestImmediateDetection();
					nextDevicePoll = now + std::chrono::milliseconds(100);
				}

				auto* gamepad = registry.GetLibrary(0);
				if (!IsEligibleUsbDualSense(gamepad))
				{
					outputConfigured = false;
					hadHaptics = false;
					hadAdaptiveTrigger = false;
					triggerPulledSinceApply = false;
					lastLeftTriggerAnalog = 0.0f;
					lastRightTriggerAnalog = 0.0f;
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

				if (now >= nextInputPoll)
				{
					gamepad->UpdateInput(0.008f);
					auto* ctx = gamepad->GetMutableDeviceContext();
					const auto* input = ctx ? ctx->GetInputState() : nullptr;
					if (input)
					{
						lastHeadsetConnected = input->bHasPhoneConnected;
						lastLeftTriggerAnalog = input->LeftTriggerAnalog;
						lastRightTriggerAnalog = input->RightTriggerAnalog;
					}
					nextInputPoll = now + std::chrono::milliseconds(8);
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
						const auto requestedHand = triggerRequest.leftHand ? EDSGamepadHand::Left : EDSGamepadHand::Right;
						const auto previousHand = appliedTriggerLeftHand ? EDSGamepadHand::Left : EDSGamepadHand::Right;
						if (hadAdaptiveTrigger && (!triggerRequest.active || triggerRequest.leftHand != appliedTriggerLeftHand))
							trigger->StopTrigger(previousHand);
						if (triggerRequest.active)
							trigger->SetBow22(triggerRequest.startZoneMask, triggerRequest.forcePair, requestedHand);
						gamepad->UpdateOutput();
						appliedTriggerLeftHand = triggerRequest.leftHand;
						appliedTriggerRevision = triggerRevision;
					}
				}

				// DualSense bow mode is a pull/release cycle. Re-arm the same
				// GraphicPack-requested effect after the physical trigger returns
				// to rest, even when the game-side tension value did not change.
				if (triggerRequest.active)
				{
					const float triggerAnalog =
						triggerRequest.leftHand ? lastLeftTriggerAnalog : lastRightTriggerAnalog;
					if (triggerAnalog >= 0.25f)
					{
						triggerPulledSinceApply = true;
					}
					else if (triggerPulledSinceApply && triggerAnalog <= 0.05f &&
						triggerRevision == appliedTriggerRevision)
					{
						if (auto* trigger = gamepad->GetIGamepadTrigger())
						{
							const auto hand = triggerRequest.leftHand ? EDSGamepadHand::Left : EDSGamepadHand::Right;
							trigger->SetBow22(triggerRequest.startZoneMask, triggerRequest.forcePair, hand);
							gamepad->UpdateOutput();
							triggerPulledSinceApply = false;
						}
					}
				}
				else
				{
					triggerPulledSinceApply = false;
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
	inline bool ApplyAdaptiveTriggerBow(uint8_t, uint8_t = 2, bool = false)
	{
		return false;
	}
	inline void StopAdaptiveTrigger() {}
}
#endif
