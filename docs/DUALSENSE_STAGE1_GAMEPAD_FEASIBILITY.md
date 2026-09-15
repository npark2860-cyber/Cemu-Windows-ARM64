# DualSense Stage 1 — Wii U GamePad Feedback Feasibility

Status: research only
Branch: `diag/botw-haptic-state-logger`
Priority: before further BOTW semantic expansion

## Goal

Before spending more effort on BOTW-specific semantic haptics, determine how much of the original Wii U GamePad feedback path is already preserved by Cemu and how cheaply it can be mapped to DualSense.

Target order:

1. Restore/preserve Wii U GamePad rumble and audio.
2. Identify broad BOTW semantic categories.
3. Refine within each category.

The implementation rule is: test existing paths first, then add the smallest missing bridge only.

## Conclusion

Stage 1 is structurally feasible and appears low risk, especially over USB.

Two important findings reduce the amount of new code needed:

- Cemu already keeps the Wii U GamePad (DRC) audio as a separate audio stream and already lets the user select a dedicated GamePad output device.
- Cemu already preserves the VPAD rumble timing pattern and evaluates it at about 60 Hz. The generic controller backend is where the physical character is reduced to ordinary rumble.

A separate BOTW VR project independently hooks `VPADControlMotor` and replays the same pattern as OpenXR haptics, which confirms that the VPAD rumble path can be reused without semantic reverse engineering.

## A. Wii U GamePad audio

### Existing Cemu path

Cemu already has separate audio objects:

- `g_tvAudio`
- `g_padAudio`
- `g_portalAudio`

The DRC path is generated separately in `snd_core/ax_out.cpp` and fed into `g_padAudio` through `AIInitDRCDMA()` / `AXOut_SubmitDRCFrame()`.

Current format is 48 kHz, 16-bit PCM, with the DRC path supporting stereo output.

Cemu settings already expose a dedicated GamePad output selector:

- `config.pad_device`
- UI tooltip: `Select the active audio output device for Wii U GamePad`

This means the first DualSense speaker test should require **no source modification**:

1. Connect DualSense by USB.
2. Confirm Windows exposes the controller speaker audio endpoint.
3. In Cemu Audio settings, set Wii U GamePad output to that endpoint.
4. Run BOTW and check the DRC audio stream.

If this succeeds, the USB GamePad-speaker bridge is already effectively implemented by Cemu/Windows.

### Important BOTW behavior

Public Wii U user reports indicate BOTW can send the full game mix to the GamePad/headphone path, depending on TV/off-TV/headphone state. Therefore the DRC stream must be inspected before deciding that it should always be routed to the small DualSense speaker.

Possible final policy:

- faithful optional mode: route original DRC stream directly to DualSense speaker;
- enhanced mode: use selected semantic/event audio only, if the raw DRC stream is mostly a full game mix.

Do not design an audio-effects system until the no-code DRC routing test is complete.

## B. Wii U GamePad rumble

### Existing Cemu path

`VPADControlMotor` sends a pattern plus length. Cemu stores this in `VPADController::m_rumble_queue`.

The parser converts each 2-bit group into a boolean motor state:

```cpp
const bool set = (p & (3 << j)) != 0;
```

The resulting pattern is replayed at approximately 60 Hz:

```cpp
if (it[m_parser])
    start_rumble();
else
    stop_rumble();
```

The SDL backend then reduces an ON state to equal-strength low/high generic rumble motors for a long timeout:

```cpp
SDL_RumbleGamepad(controller, strength, strength, 5000);
```

So the useful timing pattern survives; the generic backend changes the physical rendering.

### Original GamePad hardware implication

Public Wii U GamePad hardware documentation identifies the rumble motor as a GPIO-controlled output (`GPIO4 - Rumble motor`). This is strong evidence that there is not a hidden modern amplitude/frequency haptic stream to recover from VPAD. The important original signal is primarily the motor ON/OFF timing pattern.

Therefore Stage 1 rumble restoration does **not** require BOTW action recognition.

Preferred implementation:

`VPAD original pulse pattern -> DualSense body haptic renderer`

Use the existing VPAD pattern as the baseline layer. Later BOTW semantic haptics are additive and must not replace it.

## C. Existing precedent: BotW-BetterVR

`Crementif/BotW-BetterVR` already hooks:

- `VPADControlMotor`
- `VPADStopMotor`

and forwards the pattern to an OpenXR `RumbleManager`.

Its pattern parser is effectively the same as Cemu's current parser and its update thread also replays the state at 60 Hz.

This is valuable because it proves the architecture in another real BOTW/Cemu modification and means we should reuse the existing Cemu VPAD path instead of inventing a new rumble detector.

## D. DualSense side

Pinned Gamepad-Core upstream already exposes:

- compatible rumble
- adaptive triggers
- speaker enable/mode/volume fields
- audio-to-haptics support
- documented audio-to-speaker pipeline

For USB, prefer the simplest path first: let Cemu's existing `g_padAudio` use the Windows DualSense speaker endpoint. Do not add Gamepad-Core audio dependencies unless this path fails or speaker routing mode must be controlled by HID.

For Bluetooth, defer until USB Stage 1 is proven. Bluetooth controller-speaker transport is more complicated and may require the library's Opus/HID speaker path or equivalent handling. It should not block the first usable implementation.

## Cheapest validation order

### Test A — zero-code GamePad audio

USB DualSense -> Cemu Audio settings -> Wii U GamePad output -> DualSense speaker endpoint.

Pass condition: DRC audio reaches the controller with stable playback.

### Test B — inspect BOTW DRC content

Determine whether BOTW sends:

- full mix,
- special GamePad-only effects,
- or different content depending on off-TV/headphone mode.

This decides final speaker policy.

### Test C — original VPAD rumble baseline

Capture/log a few raw `VPADControlMotor` patterns in BOTW and confirm current Cemu playback timing.

No action recognition needed.

### Test D — direct DualSense replay

Feed the same existing 60 Hz ON/OFF sequence into the native DualSense backend. Compare feel with the ordinary SDL path.

Only after A-D pass should Stage 2 semantic work resume.

## Work-saving decision

Do **not**:

- scan BOTW RAM for Stage 1;
- synthesize new speaker sound effects yet;
- redesign the VPAD rumble API;
- implement Bluetooth speaker transport before USB works;
- replace original rumble with semantic haptics.

Stage 1 should be an adapter, not a new feedback engine.

Final layering target:

`Wii U original feedback -> preserved baseline`

`BOTW semantic category -> DualSense enhancement`

`Detailed state -> fine tuning`
