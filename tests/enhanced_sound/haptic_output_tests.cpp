#include "Cafe/OS/common/EnhancedHapticOutput.h"
#include "GCore/Interfaces/IPlatformHardware.h"
#include "GImplementations/Utils/GamepadOutput.h"
#include <array>
#include <cstdlib>
#include <iostream>

static void Check(bool condition, const char* message)
{
	if (!condition) { std::cerr << message << '\n'; std::exit(1); }
}

// Only the hardware write is replaced. Packet generation is the pinned
// Gamepad-Core production GamepadOutput.cpp, including trigger composition.
class CaptureHardware : public IPlatformHardware
{
public:
	std::array<unsigned char, 78> packet{};
	void Read(FDeviceContext*) override {}
	void Write(FDeviceContext* context) override
	{
		std::memcpy(packet.data(), context->GetRawOutputBuffer(), packet.size());
	}
	void Detect(std::vector<FDeviceContext>&) override {}
	bool CreateHandle(FDeviceContext*) override { return true; }
	void InvalidateHandle(FDeviceContext*) override {}
	void ProcessAudioHaptic(FDeviceContext*) override {}
};
static CaptureHardware hardware;
IPlatformHardware& IPlatformHardware::Get() { return hardware; }

struct SettingsCapture
{
	uint8_t headset{}, speaker{}, mode{};
	void DualSenseSettings(uint8_t, uint8_t hp, uint8_t sp, uint8_t,
		uint8_t, uint8_t rumbleMode, uint8_t, uint8_t)
	{
		headset = hp; speaker = sp; mode = rumbleMode;
	}
};

int main()
{
	for (const bool headset : {false, true})
	{
		SettingsCapture settings;
		EnhancedHapticOutput::ConfigureAmplitudeTransport(settings, headset);
		Check(settings.mode == 255, "amplitude backend must select compatible rumble");
		Check((settings.headset != 0) == headset && (settings.speaker != 0) == !headset, "jack routing preserved");
		FDeviceContext context;
		context.ConnectionType = EDSDeviceConnection::Usb;
		// This two-valued translation is the pinned DualSenseSettings contract.
		context.Output.Feature.VibrationMode = settings.mode == 255 ? 0xFF : 0xFC;
		context.Output.Audio.Mode = headset ? 0 : 1;
		context.Output.Rumbles = {70, 30};
		context.bOverrideTriggerBytes = true;
		context.OverrideTriggerRight[0] = 0x22;
		context.OverrideTriggerRight[1] = 0x04;
		context.OverrideTriggerRight[2] = 0x3F;
		FGamepadOutput::OutputDualSense(&context);
		Check(hardware.packet[0] == 0x02, "USB report id");
		Check((hardware.packet[1] & 3) == 3, "both motor-valid and haptics-select bits required");
		Check(hardware.packet[3] == 30 && hardware.packet[4] == 70, "motor bytes survive serialization");
		Check(hardware.packet[8] == (headset ? 0x02 : 0x30), "audio route survives serialization");
		Check(hardware.packet[11] == 0x22 && hardware.packet[12] == 4 && hardware.packet[13] == 0x3F,
			"raw trigger bytes survive amplitude output");
		context.Output.Rumbles = {0, 0};
		FGamepadOutput::OutputDualSense(&context);
		Check((hardware.packet[1] & 3) == 3 && hardware.packet[3] == 0 && hardware.packet[4] == 0,
			"stop sends valid zero amplitudes");
		// Reproduce the old active-clip mode: bytes exist, but neither enable bit is set.
		context.Output.Feature.VibrationMode = 0xFC;
		context.Output.Rumbles = {70, 30};
		FGamepadOutput::OutputDualSense(&context);
		Check((hardware.packet[1] & 3) == 0 && hardware.packet[4] == 70, "old mode disables motor bytes");
	}
	std::cout << "DualSense production packet tests PASS\n";
}
