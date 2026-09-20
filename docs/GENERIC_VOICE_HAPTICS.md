# Generic voice-bound haptics (Test_SE)

Status: experimental; standalone ARM64 tests pass. Full Cemu build and controller/gameplay validation are still required. Base: `test_SE` at `7c5bb3fdce5d23f1349a421bb465d9db8db215d9`.

## Problem and behavior

Previously a routed BNVIB clip used fixed `haptic_gain`, independently of AX voice volume. `spatial_drc` changed the sound send only. Free/reset could discard a playback ID without stopping its loop; natural sample completion did not run `AXSetVoiceState`. A single haptic player also let an action replace an engine loop permanently.

The runtime now owns independent playback IDs and timelines. For loops or `haptic_follow_tv=true` effects, source completion, explicit stop, route replacement, free and steal/default reset stop the associated playback. Legacy finite effects with both flags false start immediately and finish independently of their source voice; AX reset/global disable stops all effects. Each AX synchronization refreshes its playback lease. Missing snapshots for 100 ms mute output (e.g. pause/stalled audio); a surviving loop can resume when snapshots return. This is a host-time fail-safe, not an actor-destruction detector.

Concurrent clips combine using the maximum amplitude in each actuator channel. An action can dominate a quieter loop temporarily without deleting it. This deliberately avoids additive clipping and amplification of duplicate stereo voices. It is amplitude mixing, not frequency-preserving waveform synthesis.

## GraphicPack contract

In an existing `sound_routes.ini` route:

```ini
haptic = engine.bnvib
haptic_gain = 1.0
haptic_loop = true
haptic_follow_tv = true
```

`haptic_follow_tv` accepts true/false, yes/no or 1/0, case-insensitively. Default false preserves fixed-gain routes. Invalid values reject the haptic part of that route. Voice lifetime management applies to loops and effects explicitly opting into TV following. Plain finite UI effects retain their original independent lifetime.

When true:

```text
effective gain = haptic_gain
               횞 clamp(max enabled TV channel/bus send / 32768, 0, 1)
               횞 clamp(voice envelope / 32768, 0, 1)
```

This is the synchronized AX shadow mix, including mixer-evolved ramps. It is sampled once per AX frame; it is not sample-accurate gain automation. It includes the Enhanced Sound TV policy: `add_drc` with `tv_volume=0` therefore mutes these haptics. Use `spatial_drc` for unchanged TV sends and a spatial controller sound send. Haptic-only routes also support TV following.

Limitations:

- TV sends are an audibility proxy, not player distance. A game that keeps a destroyed/distant object's AX voice running at nonzero volume will keep vibrating. Investigate the game's sound lifetime if this persists.
- Post-bus AUX effects, master/host volume, final-mix callbacks, filters and PCM silence are not measured. TV following is unsuitable for DRC-only effects without TV sends.
- Maximum-channel gain can vary with panning. No game-specific distance curve, actor ID, hook, address or velocity is added.
- After a host stall longer than 100 ms, silence is intentional until the next snapshot. BNVIB timelines use host time and continue while muted; this is not emulated-time pause/resume.
- Route edits require the usual pack reload/title restart. This patch does not introduce live route invalidation for already-running voices.
- The existing output backend sends low/high amplitudes through DualSense compatible HID vibration. BNVIB frequency bytes are not rendered as audio haptics.

## Implementation map

| Location | Responsibility |
| --- | --- |
| `GraphicPack2.cpp::LoadEnhancedSoundRoutes` | Parse the optional flag |
| `EnhancedSoundRouter.h` | Carry the flag through cached lookup and equivalence checks |
| `ax_voice.cpp::AXApplyEnhancedSoundRoute` | Start a muted, voice-bound playback generation |
| `ax_ist.cpp::AXIst_SyncVPB` | Publish synchronized state for unprotected allocated voices, including stopped ones |
| `ax_voice.cpp::AXUpdateVoiceHaptics` | Stop completed voices or publish gain/lease; no source/fingerprint/glob lookup |
| `AXVPB_SetVoiceDefault`, `__AXVPBResetVoices` | Stop before discarding IDs, including free/steal/reset |
| `EnhancedHapticMixer.h` | Bounded 256-entry mixer, unique IDs, lease, output deduplication |
| `EnhancedSoundDualSenseService.h` | Drive the mixer and replay current output on device reconnection |

Updates use playback IDs rather than AX index/sample addresses, so a delayed stop/update cannot target a recycled voice. IDs are not reused; overflow rejects new playback. The mixer serializes API/worker access. Allocations occur on playback creation, not gain refresh. The AX update exits immediately for voices without haptics and scans at most 24 TV sends for opted-in voices. No new per-sample locks or fingerprint lookups are introduced. The worker scans bounded active playbacks every ~2 ms and suppresses unchanged amplitude output. Full-title frame-time profiling remains necessary.

The generic raw adaptive-trigger bridge and its revision semantics are unchanged. Game-specific routes/assets live under `enhanced_sound_policies/`, not Cemu runtime code.

## Automated checks

```sh
git submodule update --init dependencies/Gamepad-Core
cmake -S tests/enhanced_sound -B build-haptic-tests
cmake --build build-haptic-tests --config Release
ctest --test-dir build-haptic-tests -C Release --output-on-failure
python tests/enhanced_sound/test_unified_pack.py
```

`haptic_tests.cpp` checks initial mute, live gain updates, zero gain/resume, overlap and natural one-shot completion, lease expiry/recovery, stale IDs, forced reconnect output, bounded allocation, nonfinite gain, concurrent updates and route-cache policy changes. Existing lookup tests check SE routing/fingerprint equivalence. These tests do not compile the complete AX/GraphicPack/service translation units and do not prove hardware behavior.

The accompanying [unified GraphicPack](../enhanced_sound_policies/BreathOfTheWild/DualSenseExperienceUnified/README.md) preserves all 63 routes and three UI assets from the user-provided UI/Sheikah v3 archive, then prepends eight exact motorcycle routes before its wildcard rules. Only motorcycle routes opt into TV following. The pack regression test checks the original settings/order and asset hashes, precedence, and all 11 BNVIB files. Original UI settings and independent finite-effect lifetime are preserved; test menu/Sheikah feel on hardware.

## Hardware acceptance checklist

- Record binary commit, enabled pack and selected route before testing; use the accompanying updated pack, not a legacy preview.
- Idle beside the source, walk away and return: output should follow TV sends without permanently stopping the loop.
- Despawn the source (including water), unload/reload, stop audio: output must reach zero when the AX source stops/frees/mutes.
- Rapidly create/destroy sources to exercise voice stealing and index reuse; no unrelated effect may be stopped by a stale ID.
- Trigger a short action during a loop; the ongoing loop must remain after the action ends.
- Pause for >100 ms, resume, disconnect/reconnect USB, disable Enhanced Sound, quit/relaunch: no stuck output.
- Check a different game's routes and a haptic-only route; fixed-gain routes must retain their gain policy.
- Compare frame time and AX-frame time with haptics disabled/enabled on Snapdragon X Elite, including many simultaneous voices. Instrument update count, active playback count, gain/lease mute transitions and cumulative microseconds if needed; avoid per-frame text logging.
- Confirm existing audio routing and raw adaptive-trigger behavior remain unchanged.

Do not mark distance/despawn behavior PASS until those cases are tested on the new binary. If TV gain remains nonzero after object destruction, collect AX playback state, envelope, sends and stop/free events before considering further generic controls.

## Regression follow-up: no vibration on 406ecf7

The user reported total haptic loss on build carrier `406ecf7` (runtime source identical to PR commit `36e3107`). The log confirmed Unified plus all three older motorcycle preview profiles were enabled; Enhanced Sound was true. These overlaps override motorcycle routes, but do not by themselves explain UI silence.

The first revision incorrectly made legacy finite UI effects wait for AX snapshots and stop with source lifetime. It also advanced their BNVIB clock while waiting: a short clip could finish before its first snapshot. A deterministic delayed-snapshot regression test now reproduces and guards that defect. Finite legacy effects now bypass snapshot/lease coupling, and bound clips do not consume samples before their first snapshot. This corrects proven design defects; the exact cause of *all* output loss remains unconfirmed without runtime telemetry.

Test-only diagnostics now log at most 16 route starts, 16 initial bound-voice snapshots and 8 nonzero output sends per process, plus first eligible USB device detection and worker exceptions. They distinguish route resolution, initial snapshot/volume, device availability and output submission without per-frame logging. Hardware retest remains required. No BOTW-specific runtime checks were introduced.

## Output transport correction after 907dd4b

The subsequent user test still had no vibration. Its log proves route start (`played=true`), eligible USB DualSense detection, nonzero output submission, and nonzero AX gains. Thus snapshot gating is not the current blocking stage.

The pinned Gamepad-Core `9a16b81604fd711db3c445e8a8108e2b570f6477` exposes a misleading `HapticsRumble` name: `DualSenseSettings` maps any rumbleMode other than 255 to `0xFC`; `GamepadOutput.cpp` writes that value directly to output valid_flag0. The service selected it while writing ordinary HID motor amplitude bytes. `0xFC & 0x03 == 0`: compatible-vibration and haptics-select are both clear. No PCM haptic stream is supplied to replace those disabled motor bytes. This is a concrete protocol mismatch; it was already present in the restored BNVIB service, not introduced by the mixer.

The amplitude backend now keeps Gamepad-Core's default compatible vibration mode (255 -> `0xFF`) for active output and zero-amplitude stop packets. Speaker/headset selection and raw trigger bytes are preserved. This fixes the protocol mismatch for all games; it does not implement frequency/PCM haptics.

Evidence: [Linux Sony driver flags and output worker](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-playstation.c) selects haptics and compatible vibration when sending motor amplitudes. The production Gamepad-Core serializer is compiled into `haptic_output_tests.cpp`, replacing only hardware writes with capture. Tests verify enable bits, nonzero/zero motor bytes, speaker/headset routing and raw SetBow22 bytes; a negative fixture demonstrates that the old `0xFC` mode carries amplitudes without enabling them. ARM64 test PASS; physical vibration and concurrent audio behavior still require a new-binary test. Bounded output logs now include actual `valid0` (expected `0xFF`).
