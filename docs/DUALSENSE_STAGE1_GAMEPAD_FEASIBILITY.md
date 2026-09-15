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

Current DRC format is 48 kHz, 16-bit PCM. Cemu's UI currently exposes Stereo only for GamePad audio and the default `pad_channels` value is Stereo.

Cemu settings already expose a dedicated GamePad output selector:

- `config.pad_device`
- UI tooltip: `Select the active audio output device for Wii U GamePad`

On Windows, the XAudio2 backend enumerates `AudioEndpoint` devices and creates a mastering voice for the selected device ID. It then accepts the DRC stereo blocks through the existing `FeedBlock()` path. No new Cemu audio transport is required for a normal Windows render endpoint.

### DualSense USB audio endpoint

A physical DualSense connected by USB exposes a standard USB Audio Class render interface. Public descriptor dumps identify the output stream as:

- 48 kHz
- 16-bit PCM
- 4 channels
- front L/R = ordinary controller audio path
- surround L/R = DualSense voice-coil haptic actuators

The internal speaker is fed from the ordinary front-channel audio path; speaker/headset routing and volume are controlled by DualSense output settings.

This is highly compatible with Cemu's existing 48 kHz DRC path. Cemu currently supplies stereo rather than an authored 4-channel DualSense stream, which is appropriate for the speaker-only baseline because Stage 1 must not accidentally feed the haptic actuator channels.

XAudio2 permits an explicit input-channel count on the mastering voice and handles device-side format/sample-rate conversion. Therefore a direct stereo-to-DualSense render-endpoint test is the cheapest first step. Physical validation is still required because the final Windows channel routing depends on the controller endpoint/driver configuration.

### Important Cemu headphone-state finding

Cemu's `VPADStatus` contains `headphoneStatus` at offset `0x90`, but no code path was found that sets it. `VPADRead()` zero-initializes the status structure, so the emulated Wii U GamePad currently reports no connected headphones unless another path is added later.

This matters for BOTW.

Historical Wii U user reports consistently indicate that BOTW behaves roughly as follows:

- normal TV play: GamePad speaker is normally silent / not used as the main game mix;
- headphones connected to the Wii U GamePad: the full BOTW audio mix is available through the GamePad headphone path;
- in at least some configurations, activating that headphone path changes or disables TV audio simultaneously.

Therefore a silent BOTW DRC stream in the first DualSense test must **not** immediately be interpreted as a failed DualSense/Cemu audio bridge. It may be the correct result for the no-headphone BOTW state.

Do not force `headphoneStatus = 1` as a production shortcut. That would emulate a plugged-in headset, not the original GamePad speaker, and may change BOTW's TV mix/routing.

### Consequence for the project

There are two separate goals that must not be confused:

1. **Generic Cemu fidelity:** preserve each game's actual Wii U DRC/GamePad audio and route it to DualSense where useful. This is broadly valuable across Wii U titles that deliberately use the GamePad speaker.
2. **BOTW DualSense enhancement:** BOTW appears to have little or no unique GamePad-speaker content during normal TV play. Its DualSense speaker experience may therefore need to be added later from semantic game events rather than treated as recovered Wii U speaker effects.

For BOTW, routing the headphone-mode full game mix into the tiny DualSense speaker would be technically possible but is probably not the desired final design.

### Cheapest USB validation

No source modification first:

1. Connect DualSense by USB.
2. Confirm Windows exposes a `DualSense` / `Wireless Controller` render endpoint.
3. In Cemu Audio settings, set Wii U GamePad output to that endpoint.
4. Set GamePad volume above zero (Cemu's default pad volume can be zero).
5. Run a Wii U title known to emit GamePad-specific audio to validate the transport independently of BOTW.
6. Then test BOTW and classify the actual DRC content.

If the endpoint is visible but sound is routed incorrectly, the smallest likely addition is DualSense HID speaker-route/volume control through Gamepad-Core. Do not replace Cemu's PCM pipeline unless direct XAudio2 routing fails.

### Bluetooth

Bluetooth is deliberately deferred.

A stock DualSense does not expose the same standard USB Audio Class render endpoint to Windows over ordinary Bluetooth. Recent open-source projects demonstrate controller-speaker audio over Bluetooth through the proprietary DualSense HID audio transport using Opus framing, and the pinned Gamepad-Core upstream documents a Bluetooth audio-to-speaker path as well.

That path is materially more complex than USB and may require additional audio/codec dependencies. It should not block Stage 1 USB completion.

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

For USB, prefer the simplest path first: let Cemu's existing `g_padAudio` use the Windows DualSense audio endpoint. Gamepad-Core should initially be limited to speaker route/volume control only if Windows defaults do not expose the desired internal-speaker path.

For Bluetooth, defer until USB Stage 1 is proven.

## Cheapest validation order

### Test A — zero-code USB audio transport

Use a Wii U title with known GamePad-speaker output:

USB DualSense -> Cemu Audio settings -> Wii U GamePad output -> DualSense render endpoint.

Pass condition: DRC audio reaches the controller with stable playback.

This validates the transport independently of BOTW's unusual GamePad-audio policy.

### Test B — BOTW DRC classification

With the USB transport already proven, determine whether BOTW sends:

- silence during normal TV mode,
- any GamePad-only effects,
- full mix only in off-TV/headphone-like states,
- or another pattern.

Do not alter `headphoneStatus` for this baseline test.

### Test C — optional speaker-route control

Only if Test A reaches the DualSense endpoint but not the internal speaker, use the existing Gamepad-Core audio mode/volume controls to select the internal speaker. Keep PCM transport in Cemu/XAudio2.

### Test D — original VPAD rumble baseline

Capture/log a few raw `VPADControlMotor` patterns in BOTW and confirm current Cemu playback timing.

No action recognition needed.

### Test E — direct DualSense rumble replay

Feed the same existing 60 Hz ON/OFF sequence into the native DualSense backend. Compare feel with the ordinary SDL path.

Only after the Stage 1 baseline is understood should Stage 2 semantic work resume.

## Work-saving decision

Do **not**:

- scan BOTW RAM for Stage 1;
- synthesize new BOTW speaker sound effects yet;
- force Wii U headphone-connected state merely to get audio;
- redesign Cemu's existing DRC audio pipeline;
- implement Bluetooth speaker transport before USB works;
- redesign the VPAD rumble API;
- replace original rumble with semantic haptics.

Stage 1 should be an adapter, not a new feedback engine.

Final layering target:

`Wii U original feedback -> preserved baseline`

`BOTW semantic category -> DualSense enhancement`

`Detailed state -> fine tuning`
