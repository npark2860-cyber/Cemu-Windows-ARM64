# BOTW Haptics / Rumble Research Source Index

Purpose: preserve every external source currently being used for the BOTW Wii U -> DualSense haptics work, pinned by repository commit/path where possible. This file is a source-of-truth index; it does **not** vendor third-party raw files unless their license is explicitly checked.

## 1. BOTW Switch rumble capture — useful transport evidence, not HD Rumble authoring proof

Repository: `dekuNukem/Nintendo_Switch_Reverse_Engineering`
Pinned master: `b354f21ae81f7b0d1d060b2b61e66ad0d9bc1756`

Key files:
- `logic_captures/left_grey_joycon_botw_rumble.logicdata`
- `logic_captures/left_grey_joycon_botw_rumble.txt`
- GitHub issue `#11` — `HD-rumble data`
- `bluetooth_hid_notes.md`

Use:
- confirms real BOTW Switch rumble traffic was captured at the Joy-Con transport level.
- useful for packet timing/encoding validation and comparison with decoded vibration output.

Important correction:
- this capture must **not** be treated as proof that BOTW Switch shipped Nintendo-authored HD Rumble patterns.
- official pre-release statements from Eiji Aonuma said BOTW would not use Switch HD Rumble because the Switch and Wii U versions were intended to provide the same gameplay experience.

Research status:
- [x] Public BOTW Joy-Con rumble capture located.
- [x] Reclassified as transport/reference evidence rather than a source of authored BOTW HD Rumble assets.
- [ ] Decode enough of the capture to compare ordinary BOTW rumble transport with Cemu/Wii U timing.

## 2. Official BOTW HD Rumble limitation

Source family:
- 2017 Eiji Aonuma interviews reported by Nintendo-focused press.

Confirmed conclusion:
- BOTW Switch did not use the Switch-specific HD Rumble feature.
- rationale given: preserve essentially the same gameplay experience between Wii U and Switch.

Project consequence:
- the previous plan "recover native Switch BOTW HD Rumble and replay it on DualSense" is invalid as a primary source strategy.
- BOTW Switch may still emit ordinary rumble, and its runtime packets remain useful as a timing/transport reference.
- for rich Nintendo-authored frequency/amplitude patterns, use a later Nintendo Zelda title that actually ships HD Rumble data.

## 3. TOTK `.bnvib` — preferred Nintendo-authored rich haptic donor source

Public research source:
- `TotkMods/Research`
  - identifies `.bnvib` as `Binary Vibration`
  - describes it as the HD Rumble data format used by Tears of the Kingdom resources.

Format reference:
- SwitchBrew `BNVIB`
  - BNVIB = Binary NX Vibration
  - sample payload uses 4-byte samples
  - sample interval is stored in milliseconds
  - vibration types include one-shot, loop, and loop+wait variants

Important distinction:
- the on-disk BNVIB sample encoding is not simply four IEEE float fields per sample.
- at the Switch API/service level, vibration values are represented as low/high band frequency and amplitude components.
- therefore the decoder pipeline is:

```text
BNVIB binary encoding
  -> decoded vibration timeline
  -> low/high frequency + amplitude representation
  -> DualSense renderer
```

Planned use:
1. enumerate `.bnvib` files from a user-owned TOTK RomFS dump.
2. record path, file size, type, sample interval, loop metadata, sample count and hashes.
3. decode several representative files to a normalized timeline.
4. correlate filenames / SLink / action metadata to semantic events where possible.
5. use those Nintendo-authored patterns as donor haptics for semantically equivalent BOTW actions.

Research status:
- [x] `.bnvib` format existence and purpose confirmed from public research.
- [x] public binary format reference located.
- [ ] enumerate actual TOTK `.bnvib` files from a user-owned RomFS dump.
- [ ] determine exact count and naming taxonomy in the target dump revision.
- [ ] implement/validate a decoder.
- [ ] build semantic donor catalog for weapon, player damage, movement, horse, environmental and ability events.

## 4. Switch vibration API semantics

Repository: `switchbrew/libnx`
Pinned master: `dbcc1beafc6b47b5ffbeb8ba82463a7d45da40bb`

Key file:
- `nx/include/switch/services/hid.h`
  - `HidVibrationValue` exposes `amp_low`, `freq_low`, `amp_high`, `freq_high`.

Use:
- authoritative public API-level representation for Switch vibration values.
- normalized intermediate model for BNVIB -> DualSense translation.

Research status:
- [x] Field model confirmed.
- [ ] choose the initial DualSense mapping function and validate physically.

## 5. BOTW Switch-side rumble action semantics

Repository: `zeldaret/botw`
Pinned master: `7c65472576f5857bbcca71697f5e71aa93af6f8c`
Target: BOTW Switch v1.5.0 decompilation.

Key files:
- `src/Game/AI/Action/actionControllerRumble.cpp`
- `src/Game/AI/Action/actionControllerRumble.h`
- `src/Game/AI/Action/actionTimeSpecControllerRumble.cpp`
- `src/Game/AI/Action/actionTimeSpecControllerRumble.h`

Use:
- recover BOTW semantic rumble event timing and action identity.
- do **not** assume `Pattern` resolves to an HD-Rumble BNVIB-like asset in BOTW.
- use these actions as semantic anchors when mapping Wii U BOTW events to richer TOTK donor patterns.

Research status:
- [x] semantic rumble action classes confirmed.
- [ ] trace enough of the BOTW path to understand pattern/event identity and timing.
- [ ] build semantic event catalog: bow, weapon swing, Link damage, horse, Master Cycle, environment, etc.

## 6. Wii U GamePad rumble hardware baseline

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

## 7. Cemu Wii U VPAD rumble path

Repository: this repository.
Relevant files:
- `src/Cafe/OS/libs/vpad/vpad.cpp`
- `src/input/emulated/VPADController.cpp`

Confirmed behavior:
- `VPADControlMotor(pattern, length)` data is preserved by Cemu as a temporal pattern.
- up to 120 bits / 1 second are decoded into 60 ON/OFF slots.
- `VPADController::update()` consumes the sequence at ~60 Hz and calls `start_rumble()` / `stop_rumble()`.

Use:
- authoritative BOTW Wii U event/timing baseline.
- compatibility/fallback output when no richer semantic donor mapping exists.

Research status:
- [x] temporal path confirmed.
- [ ] native DualSense renderer for VPAD pattern not yet integrated.

## 8. BetterVR precedent for intercepting BOTW/Cemu rumble

Repository: `Crementif/BotW-BetterVR`
Pinned main: `2e06b31f062408d3293a392df418da0ab37b1f23`

Key files:
- `src/hooking/rumble.cpp`
- `resources/BreathOfTheWild_BetterVR/patch_CTRL_Rumble.asm`
- `src/hooking/cemu_hooks.h`

Use:
- proof that BOTW-specific rumble interception/rerouting is practical without rewriting the game's whole input system.

Research status:
- [x] precedent confirmed.

## 9. Current project direction

Preferred hierarchy:
1. BOTW Wii U semantic event/timing remains the source of truth for **when** an effect happens.
2. TOTK `.bnvib` is the preferred Nintendo-authored donor source for **how a rich Zelda haptic should feel**, when a semantically equivalent event can be justified.
3. Original Wii U `VPADControlMotor` pattern remains fallback/compatibility behavior.
4. Custom synthesized DualSense effects are last resort when neither a suitable TOTK donor nor useful Wii U pattern exists.

Target architecture:

```text
BOTW Wii U semantic event
  -> semantic category / action identity
  -> matching TOTK BNVIB donor pattern (when justified)
  -> decoded low/high band timeline
  -> DualSense haptic renderer

fallback:
BOTW Wii U VPADControlMotor
  -> original 60 Hz ON/OFF envelope
  -> DualSense renderer
```

Important labeling rule:
- TOTK-derived effects must be documented as **Nintendo-authored donor mappings**, not as "original BOTW HD Rumble".

## 10. Packed PlayerVoice / Linkle diagnostic reference

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
- sound tracer v4 should parse SARC/pack contents and register embedded BARS with the existing BFWAV fingerprint catalog.

Detailed record and v4 pass conditions:
- `docs/BOTW_SOUND_SOURCE_TRACER_FINDINGS.md`

Research status:
- [x] PlayerVoice packed-resource location confirmed from supplied diagnostic sample.
- [x] SARC structure and PlayerVoice BARS metadata confirmed.
- [ ] add SARC/pack BARS discovery to tracer v4.
- [ ] physically prove `AX voice -> TitleBG.pack::PlayerVoice.bars -> PVxxx_xx`.

## 11. Data preservation rule

- Keep exact upstream repository, commit SHA, path/blob SHA for every research dependency.
- Do not rely on mutable `master/main` URLs alone.
- Do not vendor copyrighted game assets.
- Do not vendor third-party source/captures until license compatibility is checked; pin them instead.
- User-owned game dumps may be analyzed locally, but only structural metadata, hashes, decoder code and user-generated diagnostics belong in the repository.
- When a new source materially changes implementation direction, add it here before coding against it.
