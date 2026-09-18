#pragma once

#include "Cafe/OS/common/EnhancedHapticEngine.h"

#include <filesystem>
#include <string>

#ifdef _WIN32

#include "config/CemuConfig.h"
#include "GCore/Interfaces/IPlatformHardware.h"
#include "GCore/Templates/TBasicDeviceRegistry.h"
#include "GCore/Types/Structs/Context/DeviceContext.h"
#include "Platform/windows/windows_hardware_policy.h"

#include <array>
#include <chrono>
#include <cstdint>
#include <functional>
#include <memory>
#include <mutex>
#include <thread>

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

	// Test-Haptic smoke asset: user's original UIFadeIn.bnvib (176 bytes).
	// Embedded only in the test branch so the smoke test does not depend on runtime file paths.
	inline constexpr std::array<uint8_t, 176> kSmokeUIFadeInBnvib = {
		0x0C,0x00,0x00,0x00,0x03,0x00,0xC8,0x00,0x21,0x00,0x00,0x00,0x23,0x00,0x00,0x00,
		0x9C,0x00,0x00,0x00,0x00,0x80,0x03,0x96,0x00,0x7E,0x05,0x96,0x00,0x8B,0x05,0x96,
		0x00,0x8A,0x06,0x96,0x00,0x8A,0x07,0x96,0x00,0x8A,0x08,0x96,0x00,0x8A,0x09,0x96,
		0x00,0x8A,0x0A,0x96,0x00,0x8A,0x0B,0x96,0x00,0x8A,0x0D,0x96,0x00,0x8A,0x10,0x96,
		0x00,0x8A,0x13,0x96,0x00,0x8A,0x16,0x96,0x00,0x8A,0x19,0x96,0x00,0x8A,0x1D,0x96,
		0x00,0x8A,0x22,0x96,0x00,0x8A,0x27,0x96,0x00,0x8A,0x2D,0x96,0x00,0x8A,0x36,0x96,
		0x00,0x8A,0x40,0x96,0x01,0x8A,0x4A,0x96,0x01,0x8A,0x57,0x96,0x01,0x8A,0x64,0x96,
		0x01,0x8A,0x73,0x96,0x01,0x8A,0x80,0x96,0x01,0x8A,0x8E,0x96,0x01,0x8A,0x9D,0x96,
		0x01,0x8A,0xAD,0x96,0x01,0x8A,0xBB,0x96,0x01,0x8A,0xC4,0x96,0x02,0x8A,0xCE,0x96,
		0x02,0x8A,0xD7,0x96,0x02,0x8A,0xE2,0x96,0x02,0x8A,0xEF,0x96,0x02,0x8A,0xF8,0x96,
		0x02,0x8A,0xFF,0x96,0x02,0x8A,0xFF,0x96,0x02,0x8A,0xFF,0x96,0x02,0x8A,0xFF,0x96
	};

	inline bool PlayEmbeddedSmokeClip()
	{
		std::vector<uint8_t> bytes(kSmokeUIFadeInBnvib.begin(), kSmokeUIFadeInBnvib.end());
		EnhancedHapticEngine::Clip clip;
		if (!EnhancedHapticEngine::ParseBnvib(bytes, clip))
			return false;
		// Smoke is intentionally one-shot even if the source asset contains a loop.
		clip.loop.reset();
		auto sharedClip = std::make_shared<EnhancedHapticEngine::Clip>(std::move(clip));
		s_hapticPlayer.Play(std::move(sharedClip), 1.0f);
		return true;
	}

	inline bool IsEligibleUsbDualSense(IGamepadBase* gamepad)
	{
		if (!gamepad || !gamepad->IsConnected())
			return false;
		auto* ctx = gamepad->GetMutableDeviceContext();
		if (!ctx || ctx->ConnectionType != EDSDeviceConnection::Usb)
			return false;
		return ctx->DeviceType == EDSDeviceType::DualSense || ctx->DeviceType == EDSDeviceType::DualSenseEdge;
	}

	inline bool ConfigureOutputState(IGamepadBase* gamepad, bool speakerEnabled, bool hapticsEnabled)
	{
		if (!IsEligibleUsbDualSense(gamepad))
			return false;
		auto* settings = gamepad->GetIGamepadSettings();
		if (!settings)
			return false;

		// Preserve the physically PASSed native USB speaker settings from Release+SE.
		// Gamepad-Core maps any non-255 rumble mode to DualSense HapticsRumble (0xFC).
		settings->DualSenseSettings(
			0,                         // mic state
			0,                         // headset disabled
			speakerEnabled ? 1 : 0,    // internal speaker
			0,                         // mic volume
			255,                       // audio volume
			hapticsEnabled ? 0 : 255,  // 0 -> HapticsRumble, 255 -> native/default rumble
			0,                         // rumble reduction
			0);                        // trigger reduction
		gamepad->UpdateOutput();
		return true;
	}

	inline void EnsureRunning();

	inline bool PlayBnvib(const std::filesystem::path& path, float gain = 1.0f, std::string* error = nullptr)
	{
		EnhancedHapticEngine::Clip clip;
		if (!EnhancedHapticEngine::LoadBnvib(path, clip, error))
			return false;

		EnsureRunning();
		auto sharedClip = std::make_shared<EnhancedHapticEngine::Clip>(std::move(clip));
		s_hapticPlayer.Play(std::move(sharedClip), gain);
		return true;
	}

	inline void StopHaptics()
	{
		s_hapticPlayer.Stop();
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
			bool configuredSpeaker = false;
			bool configuredHaptics = false;
			bool smokePlayedForConnection = false;
			std::optional<Clock::time_point> smokeDue;

			while (!stopToken.stop_requested())
			{
				const auto now = Clock::now();
				if (now >= nextDevicePoll)
				{
					registry.PlugAndPlay(0.1f);
					auto* polledGamepad = registry.GetLibrary(0);
					if (IsEligibleUsbDualSense(polledGamepad))
						polledGamepad->UpdateInput(0.1f);
					else
						registry.RequestImmediateDetection();
					nextDevicePoll = now + std::chrono::milliseconds(100);
				}

				auto* gamepad = registry.GetLibrary(0);
				if (!IsEligibleUsbDualSense(gamepad))
				{
					outputConfigured = false;
					smokePlayedForConnection = false;
					smokeDue.reset();
					std::this_thread::sleep_for(std::chrono::milliseconds(2));
					continue;
				}

				if (!smokePlayedForConnection && !smokeDue)
					smokeDue = now + std::chrono::milliseconds(1500);
				if (!smokePlayedForConnection && smokeDue && now >= *smokeDue)
				{
					PlayEmbeddedSmokeClip();
					smokePlayedForConnection = true;
					smokeDue.reset();
				}

				const auto hapticFrame = s_hapticPlayer.Tick(now);
				const bool hapticsEnabled = s_hapticPlayer.IsActive() || hapticFrame.has_value();
				const bool speakerEnabled = GetConfig().enhanced_sound_experience;

				if (!outputConfigured || configuredSpeaker != speakerEnabled || configuredHaptics != hapticsEnabled)
				{
					outputConfigured = ConfigureOutputState(gamepad, speakerEnabled, hapticsEnabled);
					if (outputConfigured)
					{
						configuredSpeaker = speakerEnabled;
						configuredHaptics = hapticsEnabled;
					}
				}

				if (hapticFrame)
				{
					if (auto* rumble = gamepad->GetIGamepadRumbles())
					{
						// Phase 1 backend: preserve the BNVIB low/high amplitudes and send them
						// through Gamepad-Core's DualSense HapticsRumble transport. Frequency
						// metadata remains available in Frame for the later USB audio-haptics backend.
						rumble->SetVibration(hapticFrame->lowLevel, hapticFrame->highLevel);
						gamepad->UpdateOutput();
					}
				}

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
	inline bool PlayBnvib(const std::filesystem::path&, float = 1.0f, std::string* error = nullptr)
	{
		if (error)
			*error = "DualSense BNVIB playback is only available on Windows";
		return false;
	}
	inline void StopHaptics() {}
}
#endif
