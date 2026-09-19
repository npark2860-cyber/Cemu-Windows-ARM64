#pragma once

#ifdef _WIN32

#include "config/CemuConfig.h"
#include "audio/IAudioAPI.h"
#include "GCore/Interfaces/IPlatformHardware.h"
#include "GCore/Templates/TBasicDeviceRegistry.h"
#include "GCore/Types/Structs/Context/DeviceContext.h"
#include "Platform/windows/windows_hardware_policy.h"

#include <chrono>
#include <cstdint>
#include <memory>
#include <mutex>
#include <shared_mutex>
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

	inline bool IsEligibleUsbDualSense(IGamepadBase* gamepad)
	{
		if (!gamepad || !gamepad->IsConnected())
			return false;
		auto* ctx = gamepad->GetMutableDeviceContext();
		if (!ctx || ctx->ConnectionType != EDSDeviceConnection::Usb)
			return false;
		return ctx->DeviceType == EDSDeviceType::DualSense || ctx->DeviceType == EDSDeviceType::DualSenseEdge;
	}

	inline bool ApplyAudioRoute(IGamepadBase* gamepad, bool headsetConnected)
	{
		if (!IsEligibleUsbDualSense(gamepad))
			return false;
		auto* settings = gamepad->GetIGamepadSettings();
		if (!settings)
			return false;

		// Preserve the physically PASSed native USB audio setup, but follow the
		// DualSense jack-detect state: headphones when inserted, speaker otherwise.
		settings->DualSenseSettings(
			0,                         // mic state
			headsetConnected ? 1 : 0, // headset enabled only while inserted
			headsetConnected ? 0 : 1, // internal speaker enabled only while unplugged
			0,                         // mic volume
			255,                       // audio volume
			255,                       // native DualSense output mode
			0,                         // rumble reduction
			0);                        // trigger reduction
		gamepad->UpdateOutput();

		// DualSense audio-route changes must never leave Cemu's TV stream stopped.
		// Play() is idempotent on all supported Cemu audio backends.
		{
			std::shared_lock lock(g_audioMutex);
			if (g_tvAudio)
				g_tvAudio->Play();
		}
		return true;
	}

	inline void Worker(std::stop_token stopToken)
	{
		try
		{
			IPlatformHardware::SetInstance(std::make_unique<windows_platform::windows_hardware>());
			Registry registry;
			registry.RequestImmediateDetection();
			bool initializedForConnection = false;
			bool lastHeadsetConnected = false;

			while (!stopToken.stop_requested())
			{
				registry.PlugAndPlay(0.1f);
				auto* gamepad = registry.GetLibrary(0);
				const bool eligible = IsEligibleUsbDualSense(gamepad);

				if (!GetConfig().enhanced_sound_experience)
				{
					initializedForConnection = false;
				}
				else if (eligible)
				{
					gamepad->UpdateInput(0.1f);
					auto* ctx = gamepad->GetMutableDeviceContext();
					const auto* input = ctx ? ctx->GetInputState() : nullptr;
					const bool headsetConnected = input && input->bHasPhoneConnected;
					if (!initializedForConnection || headsetConnected != lastHeadsetConnected)
					{
						initializedForConnection = ApplyAudioRoute(gamepad, headsetConnected);
						if (initializedForConnection)
							lastHeadsetConnected = headsetConnected;
					}
				}
				else
				{
					initializedForConnection = false;
					registry.RequestImmediateDetection();
				}
				std::this_thread::sleep_for(std::chrono::milliseconds(100));
			}
		}
		catch (...)
		{
			// Enhanced Sound is optional and must never make Cemu fatal.
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
}
#endif
