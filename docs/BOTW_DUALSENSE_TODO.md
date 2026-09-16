# BOTW DualSense TODO

## Project goal

Turn Wii U BOTW on Cemu into a DualSense-enhanced edition while preserving game correctness and using Nintendo-authored data wherever possible.

Priority policy:

1. Use BOTW Wii U as the source of truth for event timing/semantics.
2. Prefer **TOTK Nintendo-authored `.bnvib` HD Rumble patterns** as rich donor haptics when a semantically equivalent BOTW action can be justified.
3. Keep Wii U `VPADControlMotor` as compatibility/fallback behavior.
4. Route **Link-local original BOTW sounds** to the DualSense speaker where appropriate.
5. Add adaptive-trigger behavior after semantic event identification is stable.
6. Never describe TOTK-derived donor effects as "original BOTW HD Rumble"; BOTW Switch did not ship HD Rumble support.

---

## P0 — Research / source capture

- [x] Confirm Wii U GamePad rumble is a 60 Hz temporal ON/OFF pattern.
- [x] Confirm Cemu preserves the original `VPADControlMotor` temporal pattern.
- [x] Confirm BOTW Switch has higher-level `ControllerRumble` / `TimeSpecControllerRumble` actions.
- [x] Confirm Switch vibration API exposes low/high frequency + amplitude components.
- [x] Locate public BOTW Joy-Con rumble capture data.
- [x] Correct earlier premise: BOTW Switch did **not** use HD Rumble; public capture is transport/reference evidence, not a library of authored BOTW HD patterns.
- [x] Confirm TOTK research identifies `.bnvib` as Binary Vibration / HD Rumble data.
- [x] Locate public BNVIB structural documentation.
- [ ] Enumerate `.bnvib` files from a user-owned TOTK RomFS dump:
  - path
  - size
  - SHA-256
  - vibration type
  - sample interval
  - sample count
  - loop start/end/wait if present
- [ ] Determine naming taxonomy and likely semantic groups in TOTK.
- [ ] Trace BOTW rumble actions far enough to build reliable semantic/timing labels; do not assume they resolve to HD assets.
- [ ] Build a first BOTW semantic catalog for:
  - bow
  - sword
  - spear
  - heavy weapon
  - player hit/damage
  - horse
  - Master Cycle
  - bomb/explosion
  - climbing / landing / fall
  - rune/magic effects

### Exit condition

At least one TOTK `.bnvib` must be decoded end-to-end and paired with a justified, semantically equivalent BOTW action/event.

---

## P1 — BNVIB decoder / normalized haptic timeline

- [ ] Implement a standalone BNVIB parser with strict range validation.
- [ ] Support known vibration types:
  - normal one-shot
  - loop
  - loop + wait
- [ ] Decode the on-disk 4-byte sample representation into a normalized Switch vibration timeline.
- [ ] Normalize output to:
  - `amp_low`
  - `freq_low`
  - `amp_high`
  - `freq_high`
  - timestamp/duration
- [ ] Preserve original sample interval and loop semantics.
- [ ] Export decoded diagnostics to CSV/JSON for inspection.
- [ ] Compare at least one decoded pattern with known Switch vibration service semantics / packet behavior.

### Exit condition

A user-owned TOTK BNVIB can be decoded reproducibly into a timestamped low/high-band vibration sequence.

---

## P2 — Switch/TOTK haptic timeline → DualSense renderer

- [ ] Determine the best DualSense output path:
  - native DualSense haptic/audio actuator path if available
  - otherwise the highest-fidelity Gamepad-Core path that preserves useful frequency/amplitude behavior
- [ ] Implement renderer input as normalized low/high-band timeline.
- [ ] Render a known decoded BNVIB pattern on physical DualSense.
- [ ] Compare weak/strong, low/high, pulse and sweep behavior by hand.
- [ ] Add global haptic strength scaling without destroying relative Nintendo-authored amplitudes.
- [ ] Handle stop/reset/reconnect cleanly.
- [ ] Ensure no DSX runtime dependency.

### Exit condition

A decoded TOTK BNVIB sequence is physically reproducible on DualSense with clearly distinguishable temporal/frequency character.

---

## P3 — BOTW event → TOTK donor-pattern matching

- [ ] Reuse BOTW semantic probes only where they reduce identification cost.
- [ ] Use Wii U `VPADControlMotor` timing as one event/reference signal, not as the final rich haptic source.
- [ ] Use sound-source tracer / SLink / action state where these provide stronger semantic identity.
- [ ] Record controlled BOTW sessions one action at a time.
- [ ] Build mapping table:

  `BOTW Wii U semantic event -> semantically matched TOTK BNVIB donor -> DualSense renderer`

- [ ] First physical targets:
  1. bow draw/release
  2. Link taking damage
  3. weapon swing/impact
  4. horse movement
  5. fall/landing
- [ ] Do not force a donor mapping when the semantic match is weak.
- [ ] Use original Wii U rumble for events with no justified donor equivalent.

### Exit condition

At least three BOTW actions trigger intentionally selected Nintendo-authored donor haptics on DualSense with no obvious false activation.

---

## P4 — DualSense speaker / original BOTW sound routing

- [x] Confirm Cemu has independent TV and DRC/GamePad audio mixes per AX voice.
- [x] Confirm DualSense USB speaker can receive Cemu GamePad PCM once speaker routing is initialized.
- [x] Confirm Cemu Audio Debugger can be extended to expose TV vs DRC mix state.
- [x] Build FS/BARS -> AX source tracer v1.
- [x] Add copied BFWAV fingerprint recovery v2.
- [x] Resolve known-path blank track names / fragmented standalone BARS reads v3.
- [x] Confirm Linkle `TitleBG.pack` contains `Sound/Resource/PlayerVoice.bars` with 267 `PVxxx_xx` tracks.
- [ ] v4: parse SARC/pack contents and register embedded BARS in the existing fingerprint catalog.
- [ ] Physically prove `AX voice -> TitleBG.pack::PlayerVoice.bars -> PVxxx_xx`.
- [ ] Use SLink/GameROMPlayer metadata to recover semantic player-voice names where possible.
- [ ] Identify and validate Link-local sound groups:
  - Link voice/grunts
  - weapon swing/whoosh
  - Link body hit/damage
  - Link fall/landing/body reaction
- [ ] First test in **Duplicate mode**: keep TV output and additionally enable DRC.
- [ ] After validation, add optional **Move mode** or TV attenuation for selected sounds.
- [ ] Keep world/external sounds on TV by default.
- [ ] Initialize DualSense speaker route natively on USB connect/reconnect so DSX is never required.

### Exit condition

Original BOTW Link-local effects play from the DualSense speaker at correct in-game timing while the world mix remains on the main audio output.

---

## P5 — Adaptive triggers

- [ ] Use confirmed semantic events rather than button-only heuristics where possible.
- [ ] Bow:
  - draw resistance curve
  - release reset
  - optional weapon/bow-type variation
- [ ] Master Cycle:
  - throttle resistance/vibration
  - acceleration/load variation
- [ ] Heavy weapons:
  - optional attack resistance/mechanical cue
- [ ] Do not add trigger behavior when it conflicts with normal control feel.
- [ ] Keep all trigger effects independently disableable.

### Exit condition

Bow and Master Cycle have stable, action-aware adaptive-trigger behavior without false activation.

---

## P6 — Integration architecture

- [ ] Keep BOTW-specific semantic logic isolated from generic Cemu controller code.
- [ ] Define one central BOTW DualSense state/event layer consumed by:
  - haptics
  - speaker routing
  - adaptive triggers
- [ ] Avoid multiple independent scanners for the same game state.
- [ ] Settings should include:
  - Nintendo-derived enhanced haptics on/off
  - haptic strength
  - Wii U rumble fallback on/off
  - DualSense speaker enhancements on/off
  - Link-local sound routing on/off
  - adaptive triggers on/off
- [ ] Keep donor source/mapping metadata inspectable for every enhanced haptic.
- [ ] Default to safe behavior for non-DualSense controllers.
- [ ] Keep non-BOTW titles unaffected.

---

## P7 — Validation / performance

- [ ] Test on Snapdragon X Elite / Windows ARM64 / Adreno target machine.
- [ ] Measure BOTW FPS and frame-time impact before/after integration.
- [ ] No polling/logging path may remain enabled in normal play if it causes measurable overhead.
- [ ] Test DualSense USB disconnect/reconnect during Cemu runtime.
- [ ] Verify speaker route restores automatically after reconnect.
- [ ] Verify haptics stop immediately on pause/title exit/controller loss.
- [ ] Test long play sessions for stuck vibration/trigger/audio states.
- [ ] Compare ARM64 output with stock Cemu behavior to ensure no game regression.

---

## Deferred

- [ ] Bluetooth DualSense speaker/audio-haptics transport.
- [ ] Per-surface climbing haptics.
- [ ] Fine horse gait/terrain haptics.
- [ ] Fine Master Cycle RPM/terrain/drift modeling.
- [ ] Weapon material/type-specific donor mappings beyond the first semantic set.
- [ ] Custom synthesized effects where no Nintendo-authored equivalent exists.

---

## Current next action

**Do not spend more time trying to recover nonexistent BOTW Switch HD Rumble assets.**

Next work order:

1. Obtain/list `.bnvib` files from a user-owned TOTK RomFS dump and build an inventory.
2. Implement/validate BNVIB decoding on a few representative files before attempting Cemu integration.
3. In parallel, continue sound-source tracer v4 (`SARC -> embedded BARS -> PlayerVoice`).
4. After one BNVIB is physically reproduced on DualSense, begin semantic BOTW -> TOTK donor mapping.
5. Keep Wii U BOTW rumble as timing/fallback, not as the target haptic quality source.
