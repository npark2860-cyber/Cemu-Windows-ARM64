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

> Enhanced Sound current status, validated routing modes, unresolved loop issues, and lineage migration rules are tracked in `docs/ENHANCED_SOUND_CURRENT_STATUS.md`.

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
- [x] Confirm DualSense USB speaker can receive Cemu GamePad PCM.
- [x] Confirm the existing Cemu GamePad/DRC PCM pipeline should remain the transport; no separate replacement PCM engine is required.
- [x] Build FS/BARS -> AX source tracing and fingerprint recovery.
- [x] Harden BARS fingerprint parsing for rapid/repeated one-shot resolution (`a8d5b5537bac09a7dcffaece724b205ec18f7a96`).
- [x] Physically prove original BOTW player/effect audio can be selectively routed through DRC to the DualSense speaker.
- [x] Add native DualSense USB speaker initialization through Gamepad-Core so DSX is not a runtime dependency.
- [x] Add generic Graphic Pack-driven `sound_routes.ini` routing; keep BOTW-specific selection out of the common router.
- [x] Add persistent TV/DRC enhancement across later game-side mix writes (`06bcc9580cddd3ffeff640f801abfa34c2a10253`).
- [x] Add and physically validate `add_drc` for direct/player-local feedback.
- [x] Add and physically validate `spatial_drc` for world-positioned sounds; Master Cycle and Remote Bomb distance-sensitive behavior confirmed in BOTW.
- [x] Identify high-confidence Sheikah Sensor cue: `M_UI.bars / Sys_Item_SheikSensor`.
- [x] Identify player paraglider family: `M_SceneStatic.bars / Pl_Parashawl_*` (Equip/Flap/Squeak/UnEquip observed).
- [x] Capture player-specific footstep families using `_Pl_` naming; grass material physically heard through routed output.
- [ ] Verify generalized player footstep wildcard coverage on stone/other terrain and verify multi-`*` glob behavior if needed.
- [ ] Resolve Magnesis continuous active hum. Exact `SE_MagneCatch_Hold` routing did not solve it.
- [ ] Resolve Stasis/Time Lock continuous active hum. Exact `BitaLock_Timer03` routing did not solve it.
- [ ] Diagnose whether Magnesis/Stasis loop activation occurs through `AXSetVoiceVe()` / pre-existing loop volume-envelope changes rather than a new voice start.
- [ ] Resolve player/enemy shared weapon-swing cue discrimination using contextual evidence rather than BOTW-specific hardcoding in the generic router.
- [ ] Reproduce/classify the intermittent session where Ancient weapon routing disappeared until restart before changing the route definition.
- [ ] Perform final production performance/soak validation after the Sound feature is transplanted onto the official ARM64 lineage.

### Exit condition

The official Release+Sound edition preserves the validated ARM64/Adreno rendering baseline, Enhanced Sound OFF matches the original edition, and validated player-local/world-positioned BOTW effects route correctly to the DualSense speaker without a DSX runtime dependency.

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

### Enhanced Sound lineage correction takes priority before additional sound feature work

`feat/enhanced-sound-experience-v1` is now a historical donor/reference branch, not an official product lineage.

Proceed **one edition at a time**:

1. Start from an exact copy of the validated official Release edition, preserving its existing source/workflow/build behavior.
2. Create only the Release+Sound derivative first.
3. Transplant the validated Enhanced Sound **production** feature set from the donor branch; do not merge the donor branch wholesale.
4. Exclude Cue Capture V2, route-loss diagnostics, temporary logging/probe workflows and failed exact-loop route experiments from the release production transplant.
5. Diff Original Release vs Release+Sound and verify unrelated ARM64/Adreno/renderer behavior did not change.
6. Build once and physically validate rendering regression targets first, including the previously fixed BOTW stable/tent texture behavior.
7. After rendering passes, validate Enhanced Sound OFF and then the known speaker routes (`add_drc`, `spatial_drc`, PlayerVoice, weapon feedback, Remote Bomb, Master Cycle, footsteps/paraglider as applicable).
8. Do not create Test+Sound or Diagnostic+Sound until Release+Sound is physically PASS.
9. After lineage migration is stable, resume open sound investigations: Magnesis/Stasis VE-loop activation and player/enemy shared-cue discrimination.

Haptics/BNVIB work remains separate and should not be mixed into the Sound lineage migration.