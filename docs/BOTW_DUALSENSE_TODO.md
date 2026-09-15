# BOTW DualSense TODO

## Project goal

Turn Wii U BOTW on Cemu into a DualSense-enhanced edition while preserving game correctness and using Nintendo-authored data wherever possible.

Priority policy:

1. Prefer **Switch BOTW HD Rumble** over Wii U GamePad rumble for final haptic output.
2. Keep Wii U `VPADControlMotor` only as an event/timing reference and fallback when no Switch equivalent is available.
3. Route **Link-local original BOTW sounds** to the DualSense speaker where appropriate.
4. Add adaptive-trigger behavior after semantic event identification is stable.
5. Avoid custom/synthetic effects when an original Nintendo BOTW effect or rumble pattern can be reused.

---

## P0 — Research / source capture

- [x] Confirm Wii U GamePad rumble is a 60 Hz temporal ON/OFF pattern.
- [x] Confirm Cemu preserves the original `VPADControlMotor` temporal pattern.
- [x] Confirm BOTW Switch has higher-level `ControllerRumble` / `TimeSpecControllerRumble` actions.
- [x] Confirm Switch HD Rumble exposes low/high frequency + amplitude components.
- [x] Locate public BOTW Joy-Con rumble capture data.
- [x] Pin external research sources and revisions in `docs/BOTW_HAPTICS_SOURCE_INDEX.md`.
- [ ] Decode the public BOTW Joy-Con capture into a timestamped table:
  - left/right device
  - low-band frequency
  - low-band amplitude
  - high-band frequency
  - high-band amplitude
- [ ] Segment the capture into distinct rumble events and identify any known action/event boundaries.
- [ ] Trace Switch BOTW `ControllerRumble.Pattern` from AI/action parameters to the final vibration service calls.
- [ ] Find the pattern/resource table that maps BOTW pattern IDs to actual HD Rumble values.
- [ ] Build a first semantic catalog for:
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

At least one Nintendo-authored Switch BOTW rumble event must be decoded end-to-end from game/event identity to frequency/amplitude timeline.

---

## P1 — Switch HD Rumble → DualSense renderer

- [ ] Determine the best DualSense output path for Nintendo HD Rumble data:
  - native DualSense haptic/audio actuator path if available
  - otherwise the highest-fidelity Gamepad-Core path that preserves frequency and amplitude changes
- [ ] Implement a standalone converter accepting:
  - `amp_low`
  - `freq_low`
  - `amp_high`
  - `freq_high`
  - duration/timestamp
- [ ] Render a known Switch test pattern on physical DualSense.
- [ ] Compare weak/strong, low/high, pulse and sweep patterns by hand.
- [ ] Add global haptic strength scaling without destroying relative Nintendo-authored amplitudes.
- [ ] Handle stop/reset/reconnect cleanly.
- [ ] Ensure no DSX runtime dependency.

### Exit condition

A decoded Switch BOTW rumble sequence must be physically reproducible on the DualSense with clearly distinguishable low/high-frequency behavior.

---

## P2 — Wii U BOTW event → Switch rumble matching

- [ ] Reuse existing Wii U BOTW semantic probes only where they reduce identification cost.
- [ ] Add low-overhead logging around `VPADControlMotor` for event timing/reference only.
- [ ] Record controlled Wii U BOTW sessions for one action at a time.
- [ ] Match Wii U events against Switch BOTW pattern IDs/events.
- [ ] Prefer semantic matching over raw Wii U pulse matching.
- [ ] Build mapping table:

  `Wii U BOTW event -> Switch BOTW rumble pattern -> DualSense renderer`

- [ ] First physical targets:
  1. bow draw/release
  2. Link taking damage
  3. weapon swing/impact
  4. horse movement
  5. Master Cycle
- [ ] Use original Wii U rumble only for events with no confirmed Switch equivalent.

### Exit condition

At least three BOTW actions trigger the intended Nintendo-authored Switch rumble patterns on DualSense during Wii U BOTW gameplay.

---

## P3 — DualSense speaker / original BOTW sound routing

- [x] Confirm Cemu has independent TV and DRC/GamePad audio mixes per AX voice.
- [x] Confirm DualSense USB speaker can receive Cemu GamePad PCM once speaker routing is initialized.
- [x] Confirm Cemu Audio Debugger can be extended to expose TV vs DRC mix state.
- [ ] Finish ARM64 audio-routing diagnostic build validation.
- [ ] Add reliable voice transition logging; do not rely only on 100 ms GUI refresh.
- [ ] Use BOTW sound-resource metadata to identify likely original assets before blind fingerprinting.
- [ ] Identify and validate Link-local sound groups:
  - Link voice/grunts
  - weapon swing/whoosh
  - Link body hit/damage
  - Link fall/landing/body reaction
- [ ] First test in **Duplicate mode**: keep TV output and additionally enable DRC.
- [ ] After validation, add optional **Move mode** or TV attenuation for selected sounds.
- [ ] Keep world/external sounds on TV by default:
  - enemy hit sounds
  - environment collision
  - explosions/world ambience
- [ ] Initialize DualSense speaker route natively on USB connect/reconnect so DSX is never required.

### Exit condition

Original BOTW Link-local effects play from the DualSense speaker at correct in-game timing while the world mix remains spatially sensible on TV/speakers.

---

## P4 — Adaptive triggers

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

## P5 — Integration architecture

- [ ] Keep BOTW-specific semantic logic isolated from generic Cemu controller code.
- [ ] Define one central BOTW DualSense state/event layer consumed by:
  - haptics
  - speaker routing
  - adaptive triggers
- [ ] Avoid multiple independent scanners for the same game state.
- [ ] Add settings:
  - Switch BOTW HD Rumble on/off
  - haptic strength
  - Wii U rumble fallback on/off
  - DualSense speaker enhancements on/off
  - Link-local sound routing on/off
  - adaptive triggers on/off
- [ ] Default to safe behavior for non-DualSense controllers.
- [ ] Keep non-BOTW titles unaffected.

---

## P6 — Validation / performance

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
- [ ] Weapon material/type-specific haptics beyond Nintendo-authored Switch patterns.
- [ ] Custom synthesized effects where no Nintendo-authored equivalent exists.

---

## Current next action

**Do not spend more time reproducing Wii U GamePad rumble quality.**

Next work order:

1. Decode the existing public BOTW Switch HD Rumble capture.
2. Trace `ControllerRumble.Pattern` to the final Switch vibration values/table.
3. Prove one decoded Nintendo BOTW pattern on physical DualSense.
4. In parallel, finish the current AX TV/DRC audio-routing diagnostic build.
5. After both proof paths pass, begin semantic integration in Wii U BOTW.
