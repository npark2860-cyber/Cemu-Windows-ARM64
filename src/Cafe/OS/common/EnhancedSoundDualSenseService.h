#pragma once

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

	inline bool InitializeSpeakerRoute(IGamepadBase* gamepad)
	{
		if (!IsEligibleUsbDualSense(gamepad))
			return false;
		auto* settings = gamepad->GetIGamepadSettings();
		if (!settings)
			return false;

		// Exact command from the physically PASSed native USB speaker-route test.
		// Test-only rumble/trigger clears are intentionally not carried into Cemu.
		settings->DualSenseSettings(
			0,   // mic state
			0,   // headset disabled
			1,   // internal speaker enabled
			0,   // mic volume
			180, // audio volume
			255, // native DualSense output mode
			0,   // rumble reduction
			0);  // trigger reduction
		gamepad->UpdateOutput();
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
					if (!initializedForConnection)
						initializedForConnection = InitializeSpeakerRoute(gamepad);
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
