# Generic voice-bound haptics (Test_SE)

Status: experimental; standalone ARM64 tests pass. Full Cemu build and controller/gameplay validation are still required. Base: `test_SE` at `7c5bb3fdce5d23f1349a421bb465d9db8db215d9`.

## Problem and behavior

Previously a routed BNVIB clip used fixed `haptic_gain`, independently of AX voice volume. `spatial_drc` changed the sound send only. Free/reset could discard a playback ID without stopping its loop; natural sample completion did not run `AXSetVoiceState`. A single haptic player also let an action replace an engine loop permanently.

The runtime now owns independent playback IDs and timelines. Source completion, explicit stop, route replacement, free, steal/default reset and AX reset stop the associated playback, including one-shots. Each AX synchronization refreshes its playback lease. Missing snapshots for 100 ms mute output (e.g. pause/stalled audio); a surviving loop can resume when snapshots return. This is a host-time fail-safe, not an actor-destruction detector.

Concurrent clips combine using the maximum amplitude in each actuator channel. An action can dominate a quieter loop temporarily without deleting it. This deliberately avoids additive clipping and amplification of duplicate stereo voices. It is amplitude mixing, not frequency-preserving waveform synthesis.

## GraphicPack contract

In an existing `sound_routes.ini` route:

```ini
haptic = engine.bnvib
haptic_gain = 1.0
haptic_loop = true
haptic_follow_tv = true
```

`haptic_follow_tv` accepts true/false, yes/no or 1/0, case-insensitively. Default false preserves fixed-gain routes. Invalid values reject the haptic part of that route. Voice lifetime management applies regardless of this flag.

When true:

```text
effective gain = haptic_gain
               × clamp(max enabled TV channel/bus send / 32768, 0, 1)
               × clamp(voice envelope / 32768, 0, 1)
```

This is the synchronized AX shadow mix, including mixer-evolved ramps. It is sampled once per AX frame; it is not sample-accurate gain automation. It includes the Enhanced Sound TV policy: `add_drc` with `tv_volume=0` therefore mutes these haptics. Use `spatial_drc` for unchanged TV sends and a spatial controller sound send. Haptic-only routes also support TV following.

Limitations:

- TV sends are an audibility proxy, not player distance. A game that keeps a destroyed/distant object's AX voice running at nonzero volume will keep vibrating. Investigate the game's sound lifetime if this persists.
- Post-bus AUX effects, master/host volume, final-mix callbacks, filters and PCM silence are not measured. TV following is unsuitable for DRC-only effects without TV sends.
- Maximum-channel gain can vary with panning. No game-specific distance curve, actor ID, hook, address or velocity is added.
- After a host stall longer than 100 ms, silence is intentional until the next snapshot. BNVIB timelines use host time and continue while muted; this is not emulated-time pause/resume.
- Route edits require the usual pack reload/title restart. This patch does not introduce live route invalidation for already-running voices.
- The existing output backend sends low/high amplitudes through DualSense HapticsRumble. BNVIB frequency bytes are not rendered as audio haptics.

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
cmake -S tests/enhanced_sound -B build-haptic-tests
cmake --build build-haptic-tests --config Release
ctest --test-dir build-haptic-tests -C Release --output-on-failure
python tests/enhanced_sound/test_unified_pack.py
```

`haptic_tests.cpp` checks initial mute, live gain updates, zero gain/resume, overlap and natural one-shot completion, lease expiry/recovery, stale IDs, forced reconnect output, bounded allocation, nonfinite gain, concurrent updates and route-cache policy changes. Existing lookup tests check SE routing/fingerprint equivalence. These tests do not compile the complete AX/GraphicPack/service translation units and do not prove hardware behavior.

The accompanying [unified GraphicPack](../enhanced_sound_policies/BreathOfTheWild/DualSenseExperienceUnified/README.md) preserves all 63 routes and three UI assets from the user-provided UI/Sheikah v3 archive, then prepends eight exact motorcycle routes before its wildcard rules. Only motorcycle routes opt into TV following. The pack regression test checks the original settings/order and asset hashes, precedence, and all 11 BNVIB files. Original UI settings are preserved, but the new source-bound lifetime can truncate patterns longer than their source sounds; test menu/Sheikah feel on hardware.

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
