# BOTW Haptics / Rumble Research Source Index

Purpose: preserve every external source currently being used for the BOTW Wii U -> DualSense haptics work, pinned by repository commit/path where possible. This file is a source-of-truth index; it does **not** vendor third-party raw files unless their license is explicitly checked.

## 1. Switch BOTW real HD Rumble captures

Repository: `dekuNukem/Nintendo_Switch_Reverse_Engineering`
Pinned master: `b354f21ae81f7b0d1d060b2b61e66ad0d9bc1756`

Key files:
- `logic_captures/left_grey_joycon_botw_rumble.logicdata`
  - upstream blob SHA: `8da47a3fcd1c8c7ecec6f39c36b5c6056e517ec5`
  - real logic-analyzer capture of BOTW rumble traffic to a left Joy-Con.
- `logic_captures/left_grey_joycon_botw_rumble.txt`
  - upstream blob SHA: `0375fe284a096d433c41e5d1d72534cbf3462b80`
  - text transcript of the capture; comment states button press / rumble begins around line 358.
- GitHub issue `#11` — `HD-rumble data`
  - historical reverse-engineering discussion using BOTW data, including packet-field experiments and amplitude/frequency decoding work.
- `bluetooth_hid_notes.md`
  - Joy-Con/Pro Controller protocol notes including HD Rumble packet format/encoding background.

Research status:
- [x] Source located and pinned.
- [x] Raw BOTW capture confirmed to exist.
- [ ] Parse complete capture into timestamped `(low amp, low freq, high amp, high freq)` samples.
- [ ] Label individual BOTW actions contained in the capture.

## 2. Switch HD Rumble API semantics

Repository: `switchbrew/libnx`
Pinned master: `dbcc1beafc6b47b5ffbeb8ba82463a7d45da40bb`

Key file:
- `nx/include/switch/services/hid.h`
  - `HidVibrationValue` exposes `amp_low`, `freq_low`, `amp_high`, `freq_high`.

Use:
- authoritative public API-level representation for Nintendo Switch vibration values.
- basis for a Switch HD Rumble -> DualSense translation layer.

Research status:
- [x] Field model confirmed.
- [ ] Choose initial DualSense mapping function and validate physically.

## 3. BOTW Switch-side semantic rumble actions

Repository: `zeldaret/botw`
Pinned master: `7c65472576f5857bbcca71697f5e71aa93af6f8c`
Target: BOTW Switch v1.5.0 decompilation.

Key files:
- `src/Game/AI/Action/actionControllerRumble.cpp`
- `src/Game/AI/Action/actionControllerRumble.h`
  - loads static `Pattern` and dynamic `Count`.
- `src/Game/AI/Action/actionTimeSpecControllerRumble.cpp`
- `src/Game/AI/Action/actionTimeSpecControllerRumble.h`
  - loads `Pattern`, `Seconds`, `IsWait`.
- `data/status_action.yml`
- `data/aidef_action_vtables.yml`

Use:
- recover BOTW semantic event -> rumble pattern linkage.
- correlate Nintendo-authored pattern IDs with captured HD Rumble output.

Research status:
- [x] semantic rumble action classes confirmed.
- [ ] locate pattern table / manager that resolves `Pattern` into vibration output.
- [ ] build event/pattern catalog: bow, weapon swing, Link damage, horse, Master Cycle, environment, etc.

## 4. Wii U GamePad rumble hardware baseline

Repository: `opencma/libdrc`
Pinned master: `eb53344e4cd68500ca050c14c182ee3173c08848`

Key file:
- `web/docs/re/gpio.rst`
  - DRC GPIO4 controls the rumble motor.
  - GPIO output is explicitly switched 0/1.

Use:
- confirms Wii U GamePad physical motor control is fundamentally ON/OFF, not a native multi-band HD-haptic value model.

Research status:
- [x] GPIO motor control confirmed.

## 5. Cemu Wii U VPAD rumble path

Repository: this repository.
Relevant files:
- `src/Cafe/OS/libs/vpad/vpad.cpp`
- `src/input/emulated/VPADController.cpp`

Confirmed behavior:
- `VPADControlMotor(pattern, length)` data is preserved by Cemu as a temporal pattern.
- up to 120 bits / 1 second are decoded into 60 ON/OFF slots.
- `VPADController::update()` consumes the sequence at ~60 Hz and calls `start_rumble()` / `stop_rumble()`.

Use:
- fallback/original Wii U rumble layer.
- Nintendo Switch-derived haptics can be additive or preferred where a stable BOTW semantic mapping exists.

Research status:
- [x] temporal path confirmed.
- [ ] native DualSense renderer for VPAD pattern not yet integrated.

## 6. BetterVR precedent for intercepting BOTW/Cemu rumble

Repository: `Crementif/BotW-BetterVR`
Pinned main: `2e06b31f062408d3293a392df418da0ab37b1f23`

Key files:
- `src/hooking/rumble.cpp`
  - hooks `VPADControlMotor` / `VPADStopMotor` path.
- `resources/BreathOfTheWild_BetterVR/patch_CTRL_Rumble.asm`
  - BOTW v208 patch group routes to the custom rumble hook.
- `src/hooking/cemu_hooks.h`
  - registers custom rumble HLE hooks.

Use:
- proof that BOTW-specific rumble interception/rerouting is practical without rewriting the game's whole input system.

Research status:
- [x] precedent confirmed.

## 7. Current project direction

Preferred hierarchy:
1. Nintendo-authored Switch BOTW HD Rumble, when a reliable action/pattern mapping exists.
2. Original Wii U `VPADControlMotor` temporal pattern as compatibility/fallback.
3. DualSense-specific enhancements only after original/Nintendo-authored behavior is preserved.

Target architecture:

```text
BOTW semantic event
  -> Switch BOTW rumble Pattern (when mapped)
  -> decoded low/high frequency + amplitude timeline
  -> DualSense haptic renderer

fallback:
BOTW Wii U VPADControlMotor
  -> original 60 Hz ON/OFF envelope
  -> DualSense renderer
```

## 8. Packed PlayerVoice / Linkle diagnostic reference

A local Linkle mod package supplied for research was inspected to determine where player voice resources actually live at runtime. The third-party binary/audio assets are **not** committed to this repository.

Reproducibility hashes:

- archive: `BreathOfTheWild_Linkle.zip`
  - SHA-256: `ae9cb068fc2f3e71347d6b151e8076301cc04e03ee5e3ec35d17c1b4843d0a83`
- `BreathOfTheWild_LinkleMod/content/Pack/TitleBG.pack`
  - SHA-256: `ebb2e9681de9aac5991cfb6d2a10f1025bdc5c0d73a7f16a32b4fee775af1b64`
- embedded `TitleBG.pack::Sound/Resource/PlayerVoice.bars`
  - SHA-256: `8aed11b65f4523636152343e921ff88e6f08fe0391291d30a63f4503ebc7dc09`

Verified structure:

```text
BreathOfTheWild_LinkleMod/content/Pack/TitleBG.pack
└─ Sound/Resource/PlayerVoice.bars
```

Verified metadata from this sample:

- `TitleBG.pack` is SARC.
- SARC entry count: 410.
- embedded `.bars` entry count: 35.
- `PlayerVoice.bars` size: 2,336,032 bytes.
- BARS track count: 267.
- all 267 AMTA names parsed successfully and follow the `PVxxx_xx` naming form.

Implementation consequence:

The v1-v3 tracer starts from standalone FS sound paths, so an embedded `PlayerVoice.bars` never appears as its own FS open. This materially changes the sound-source tracing direction: the next revision must parse SARC/pack contents and register embedded BARS with the existing BFWAV fingerprint catalog.

Detailed record and v4 pass conditions:

- `docs/BOTW_SOUND_SOURCE_TRACER_FINDINGS.md`

Research status:

- [x] PlayerVoice packed-resource location confirmed from supplied diagnostic sample.
- [x] SARC structure and PlayerVoice BARS metadata confirmed.
- [ ] add SARC/pack BARS discovery to tracer v4.
- [ ] physically prove `AX voice -> TitleBG.pack::PlayerVoice.bars -> PVxxx_xx`.

## 9. Data preservation rule

- Keep exact upstream repository, commit SHA, path/blob SHA for every research dependency.
- Do not rely on mutable `master/main` URLs alone.
- Do not vendor copyrighted game assets.
- Do not vendor third-party source/captures until license compatibility is checked; pin them instead.
- When a new source materially changes implementation direction, add it here before coding against it.
