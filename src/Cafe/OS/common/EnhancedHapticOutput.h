#pragma once

namespace EnhancedHapticOutput
{
	// SetVibration writes HID motor amplitudes, not PCM audio-haptics samples.
	// Gamepad-Core maps 255 to valid_flag0=0xFF; other values map to 0xFC,
	// which clears compatible-vibration and haptics-select (bits 0 and 1).
	template<class Settings>
	void ConfigureAmplitudeTransport(Settings& settings, bool headsetConnected)
	{
		settings.DualSenseSettings(0, headsetConnected ? 1 : 0,
			headsetConnected ? 0 : 1, 0, 255, 255, 0, 0);
	}
}
