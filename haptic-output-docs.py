from pathlib import Path
r=Path('generic-voice-haptics')
p=r/'tests/enhanced_sound/haptic_output_tests.cpp';s=p.read_bytes().replace(b'settings.headset == headset && settings.speaker == !headset',b'(settings.headset != 0) == headset && (settings.speaker != 0) == !headset');p.write_bytes(s)
p=r/'src/Cafe/OS/common/EnhancedSoundDualSenseService.h';s=p.read_bytes().replace(b'"Haptic output send: low={} high={}", hapticFrame->lowLevel, hapticFrame->highLevel',b'"Haptic output send: low={} high={} valid0=0x{:02X}", hapticFrame->lowLevel, hapticFrame->highLevel,\n\t\t\t\t\t\t\t\tgamepad->GetMutableDeviceContext()->Output.Feature.VibrationMode');p.write_bytes(s)
p=r/'docs/GENERIC_VOICE_HAPTICS.md';s=p.read_text(encoding='utf-8');s=s.replace('through DualSense HapticsRumble','through DualSense compatible HID vibration');s=s.replace('```sh\ncmake','```sh\ngit submodule update --init dependencies/Gamepad-Core\ncmake');s+='''
## Output transport correction after 907dd4b

The subsequent user test still had no vibration. Its log proves route start (`played=true`), eligible USB DualSense detection, nonzero output submission, and nonzero AX gains. Thus snapshot gating is not the current blocking stage.

The pinned Gamepad-Core `9a16b81604fd711db3c445e8a8108e2b570f6477` exposes a misleading `HapticsRumble` name: `DualSenseSettings` maps any rumbleMode other than 255 to `0xFC`; `GamepadOutput.cpp` writes that value directly to output valid_flag0. The service selected it while writing ordinary HID motor amplitude bytes. `0xFC & 0x03 == 0`: compatible-vibration and haptics-select are both clear. No PCM haptic stream is supplied to replace those disabled motor bytes. This is a concrete protocol mismatch; it was already present in the restored BNVIB service, not introduced by the mixer.

The amplitude backend now keeps Gamepad-Core's default compatible vibration mode (255 -> `0xFF`) for active output and zero-amplitude stop packets. Speaker/headset selection and raw trigger bytes are preserved. This fixes the protocol mismatch for all games; it does not implement frequency/PCM haptics.

Evidence: [Linux Sony driver flags and output worker](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-playstation.c) selects haptics and compatible vibration when sending motor amplitudes. The production Gamepad-Core serializer is compiled into `haptic_output_tests.cpp`, replacing only hardware writes with capture. Tests verify enable bits, nonzero/zero motor bytes, speaker/headset routing and raw SetBow22 bytes; a negative fixture demonstrates that the old `0xFC` mode carries amplitudes without enabling them. ARM64 test PASS; physical vibration and concurrent audio behavior still require a new-binary test. Bounded output logs now include actual `valid0` (expected `0xFF`).
''';p.write_text(s,encoding='utf-8',newline='\n')
p=r/'CURRENT_HANDOFF.md';s=p.read_text(encoding='utf-8');s+='''
## Output-stage finding on 907dd4b

The next test still had no vibration, despite successful route/USB/nonzero-output logs. Found an existing transport mismatch: active BNVIB selected valid_flag0=0xFC (clears HID motor enable/select bits) while only writing motor amplitudes. Keep compatible HID rumble mode 255/0xFF via a shared output helper. Real pinned Gamepad-Core packet serializer tests pass on ARM64, including preserved audio and raw trigger fields. Full build/hardware confirmation of this transport correction is pending; mixer-only unit tests were insufficient to detect this issue.
''';p.write_text(s,encoding='utf-8',newline='\n')

