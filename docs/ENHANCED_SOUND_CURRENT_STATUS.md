# Enhanced Sound Current Status

Status date: 2026-09-18
Repository: `npark2860-cyber/Cemu-Windows-ARM64`
Historical donor branch: `feat/enhanced-sound-experience-v1`
Donor HEAD at status write: `a751e4b18e9402666172da91bc724b2c7996de59`

## Scope

This document is the current source of truth for the Enhanced Sound / DualSense speaker work completed on the historical `feat/enhanced-sound-experience-v1` branch.

The branch itself is no longer an official product lineage. It is now a **donor/reference branch only**. Future official Sound editions must be created by copying the corresponding validated ARM64 baseline and then transplanting only the Enhanced Sound production changes.

Do not continue feature development directly on this donor branch after lineage reconstruction begins.

---

## Confirmed architecture

The validated audio path is:

`BOTW sound resource -> FS/BARS source tracking -> AX voice -> EnhancedSoundRouter -> TV/DRC mix -> existing Cemu GamePad audio -> Windows USB audio endpoint -> DualSense internal speaker`

Important consequences:

- no post-mix AI/source separation is required;
- no separate replacement WAV/PCM engine is required for USB;
- Cemu's existing DRC/GamePad PCM path remains the transport;
- Enhanced Sound operates at the AX voice/device-mix level;
- BOTW-specific sound selection belongs in `sound_routes.ini`, not in generic Cemu routing code.

## Production components that must survive migration

The production implementation currently depends on the following functional pieces:

- `EnhancedSoundRouter`
- `EnhancedSoundSourceTracker`
- `BotWSoundFingerprintCatalog`
- `BotWSoundSourceTracer`
- packed/fragmented BARS handling
- `coreinit_FS` tracking hooks needed for source provenance
- Graphic Pack `sound_routes.ini` loading
- AX TV/DRC routing and persistence in `ax_voice.cpp`
- Enhanced Sound config/UI switch
- Gamepad-Core dependency and native DualSense speaker initialization
- `EnhancedSoundDualSenseService`

Diagnostic-only cue capture, route-loss logging and temporary workflows are not production dependencies.

---

## Routing modes

### `add_drc`

Use for Link-local/direct-feedback sounds.

Current behavior:

- preserves the game's native DRC state;
- adds the configured route gain to DRC;
- applies the Enhanced Sound TV policy for the matched voice;
- persists routing when the game later rewrites TV/DRC device mixes;
- uses `internalMixWrite` so Cemu's own writes are not re-captured as native game state.

Typical targets:

- Link voice/grunts
- player weapon handling/swing feedback
- rune/UI feedback
- Sheikah Slate UI
- Sheikah Sensor
- player footsteps/jump/landing
- paraglider local feedback

### `spatial_drc`

Use for world-positioned sounds.

Current behavior:

- leaves TV mix native;
- derives DRC send from the current native TV front-channel main-bus volume/delta;
- route gain acts as the maximum controller send;
- follows later game TV mix updates so distance attenuation can propagate to the controller speaker.

Physical BOTW validation confirmed useful distance-aware behavior.

Confirmed examples:

- Master Cycle world-positioned audio
- Remote Bomb explosion

User physical result for the spatial test: **working**.

---

## Important production fixes already PASS/CLOSED

### TV/DRC persistence

Commit:

`06bcc9580cddd3ffeff640f801abfa34c2a10253`

Purpose:

- capture fresh native game TV/DRC mix writes;
- reapply enhancement after later `AXSetVoiceDeviceMix()` calls;
- prevent Enhanced Sound routing from disappearing after game-side mix updates.

Do not regress to a simple `drcAlreadyRouted` style implementation.

### BARS fingerprint/source resolution hardening

Commit:

`a8d5b5537bac09a7dcffaece724b205ec18f7a96`

Message:

`audio: harden BARS fingerprint catalog parsing`

Fixes include:

- AMTA STRG offset handling by version;
- DATA asset-name offset handling;
- correct STRG body handling;
- preserving fingerprints when a track name is empty;
- DSP raw-size handling correction.

This fixed rapid/repeated sound-source losses seen during bow/jump/repeated one-shot testing.

User physical result after this production fix: **"완벽해졌어."**

Treat this issue as CLOSED unless a concrete regression is reproduced.

### Native DualSense USB speaker initialization

Production path no longer requires DSX to initialize every session.

Known physical proof includes native DualSense USB speaker routing without DSX after Cemu-side initialization. DSX remains useful only as an external diagnostic comparison.

---

## Sound groups identified / routed during current work

The Git-tracked donor `sound_routes.ini` is older than the latest local route experiments. Do **not** assume the donor branch policy file contains every route listed below.

### Player voice

`PlayerVoice.bars`

Used as a broad player-voice family and physically proven to reach the DualSense speaker.

### Bow

Known route families include:

- `Bow_Draw*`
- `Bow_Release*`

### One-handed / spear / long-sword weapon feedback

Known candidates include:

- `Spear_Swing*`
- `LSword_Swing*`
- `SE_NSword_SwingPlayer*`
- `SE_ESf_SWING_SWORD_S`
- `NSword_Charge_Lv1`
- `SE_SW_KAITENGIRI`
- `LSword_AttackCharging*`
- `LSword_DownSwingAttackStart`
- `LSword_DownSwingAttackEnd`

Important unresolved issue:

`SE_NSword_SwingMiddleEnemy` has been observed in the one-handed attack investigation but its player/enemy semantics are unsafe. Enemy attacks may reuse the same or closely related cue. Do not treat source+track alone as sufficient proof of player ownership.

### Elemental / ancient weapon families

Identified route families include Fire/Ice/Electric/Ancient/Guardian-related weapon effects.

A later test showed an Ancient weapon sound appeared missing in one runtime session and worked again after restart with no route change. Treat that as **intermittent runtime state**, not as proof that the Ancient route itself is wrong.

Separate known coverage candidate:

- `GuardianSword04` does not match a `GuardianSword_*` pattern.

Do not conflate that coverage gap with the intermittent whole-session symptom.

### Remote Bomb

High-confidence routes:

- `RemoteBomb` -> world-positioned -> `spatial_drc`
- `RemoteBomb_Cancel` -> direct/UI feedback -> `add_drc`

`HoldOn_Stone01` was a false association and must not be treated as a dedicated bomb-draw cue.

### Magnesis

Known families include:

- `SE_MagneCatch_*`
- `MagneCatch_Power*`

The continuous Magnesis active hum is **not solved** by adding an exact `SE_MagneCatch_Hold` route.

### Stasis / Time Lock

Known families include:

- `Bitalock_*`
- `BitaLock_Timer*`

The continuous active Time Lock sound is **not solved** by adding an exact `BitaLock_Timer03` route.

### Cryonis / Slate / UI

Identified families include:

- `Sys_Item_IceMaker_*`
- `IceMakerBlock_*`
- `SheikerStoneOpen_*`
- `SheikerStoneClose_*`
- `SYS_AppHome_*`
- `Sys_Apptool_*`
- `Sys_Map_*`
- equipment shortcut/decision cues

### Sheikah Sensor

High-confidence capture:

- source: `M_UI.bars`
- track: `Sys_Item_SheikSensor`

### Player footsteps

Captured material-specific player tracks use the `_Pl_` marker, for example grass/leaf/moss/wood families.

Generalized route candidates were tested as:

- `Mt_*_Pl_Move*`
- `Mt_*_Pl_Jump*`
- `Mt_*_Pl_Land*`

Grass was physically heard. Stone-floor coverage was not yet proven when the generalized rule was created.

If stone remains absent, verify actual cue naming and multi-`*` glob semantics before changing generic C++.

### Paraglider

Latest capture clearly identified player paraglider tracks under:

- source: `M_SceneStatic.bars`
- family: `Pl_Parashawl_*`

Observed families include:

- Equip
- Flap
- Squeak
- UnEquip

This is a strong player-only naming family and is suitable for `add_drc`.

### Master Cycle Zero

Confirmed source groups:

- `GameROMMotorcycle.bars`
- `D_GameROMMotorcycle.bars`
- `D_GameROMMotorcycle_Mt.bars`

The current physical spatial test changed these world-positioned groups to `spatial_drc` and confirmed distance-sensitive controller-speaker behavior.

Terrain routing may become overly busy; if necessary narrow or remove terrain before weakening the main engine/world behavior.

---

## Current unresolved technical issues

### 1. Magnesis / Stasis continuous loop activation

Exact route additions for:

- `SE_MagneCatch_Hold`
- `BitaLock_Timer03`

had no effect.

The latest recapture also did not show a new named Magnesis/Stasis voice start in the expected place.

Current leading hypothesis:

- the loop voice may already exist;
- activation may occur by changing the voice envelope/volume rather than by a new `AXSetVoiceState` or sample replacement;
- current Cue Capture V2 records route resolution mainly when `AXApplyEnhancedSoundRoute()` is reached from voice start or running-voice sample replacement;
- `AXSetVoiceVe()` currently updates volume/delta but does not re-resolve the route.

Next diagnostic, after official lineage reconstruction: instrument VE/loop lifecycle on the **diagnostic Sound edition**, not on the release lineage.

This is a hypothesis until measured.

### 2. Player vs enemy shared weapon cues

At least one weapon-swing path appears to be shared/reused by enemy attacks.

Do not solve this with BOTW-specific hardcoding in `EnhancedSoundRouter`.

Evidence to collect later may include:

- native TV mix/pan/delta signature;
- spatial vs near-field pattern;
- AX voice metadata;
- caller/emitter provenance;
- higher-level actor/source association.

A simple absolute-volume threshold is not considered reliable because a close enemy can also be loud and centered.

### 3. Intermittent runtime route disappearance

One Ancient-weapon session appeared silent and worked again after restart without policy changes.

If reproduced, classify first:

- only Ancient family missing -> source/fingerprint/voice route state candidate;
- all Enhanced Sound missing -> speaker/DRC initialization or global service state candidate;
- one specific cue missing -> policy/coverage candidate.

Do not reopen the already-PASS fingerprint fix without evidence.

### 4. Long-session/random stability

Random crashes/Vulkan fatal symptoms were observed during some long diagnostic sessions, but no causal connection to audio has been proven.

Possible investigation areas, only if reproducible evidence points there:

- DualSense worker/global `IPlatformHardware` lifetime;
- thread/lifetime race;
- stale SourceTracker range state;
- unrelated/downstream Vulkan failure.

Do not claim that audio corrupts Vulkan without evidence.

---

## Diagnostic state

Cue Capture V2 diagnostic branch history includes:

- `d661bfb7b65de75218dd8b2f1a4fe4c5569d8ebd` — diagnostic instrumentation
- `a751e4b18e9402666172da91bc724b2c7996de59` — diagnostic workflow build

CSV schema:

`sequence,time_us,voice,playback,sample_base,candidate_index,candidate_count,source_found,source_path,track_name,route_match,route_mode,gain`

Current limitation: it does not record the native TV mix or VE changes needed for player/enemy contextual separation and pre-existing-loop activation analysis.

Diagnostic builds may be heavy; production builds should not retain high-volume capture/logging.

---

## Lineage correction / migration policy

A project-management error allowed `feat/enhanced-sound-experience-v1` to become a fourth working lineage even though the intended project rule was to operate only from the established official ARM64 baselines.

This donor branch is therefore frozen as historical source material.

The intended final structure is:

- three existing Original editions remain unchanged;
- each Original edition may later get one corresponding Enhanced Sound copy;
- total target lineage: `3 Original + 3 Enhanced Sound = 6`;
- no seventh feature branch is part of the official lineage.

Migration must be done **one edition at a time**, not all three at once.

First target only:

1. copy the validated Release edition exactly, including its existing workflow/build behavior;
2. create one Release+Sound derivative;
3. transplant only the Enhanced Sound production feature set from this donor branch;
4. exclude donor diagnostics/temporary workflows;
5. compare Original Release vs Release+Sound and ensure unrelated renderer/Adreno behavior is unchanged;
6. build once and let the user physically verify rendering first (including the previously fixed BOTW stable/tent texture behavior), then sound;
7. do not create Test+Sound or Diagnostic+Sound until Release+Sound passes.

The donor branch itself must not be used as the base for the new official Sound edition.

---

## Migration inclusion / exclusion summary

### Include

- generic Enhanced Sound routing architecture
- source/fingerprint production tracking
- packed BARS production handling
- TV/DRC persistence
- `add_drc`
- `spatial_drc`
- native DualSense USB speaker initialization
- config/UI and required build/dependency wiring
- BOTW Graphic Pack `sound_routes.ini` support

### Exclude

- Cue Capture V2 instrumentation from release production
- route-loss diagnostics
- temporary logging windows used only for investigation
- experimental CI-only probes
- stale handoff rules that declare `feat/enhanced-sound-experience-v1` the active official branch
- failed exact Magnesis/Stasis loop-route experiments

---

## Next sound-specific work after Release+Sound migration PASS

1. Confirm the migrated production Sound edition preserves all existing rendering fixes and Enhanced Sound OFF equals the original baseline.
2. Restore/validate the latest known route policy on the migrated branch.
3. Verify paraglider and generalized footsteps in physical BOTW.
4. Diagnose Magnesis/Stasis loop activation through VE/lifecycle telemetry on the future Diagnostic+Sound edition.
5. Investigate player/enemy shared swing discrimination only after collecting contextual AX evidence.
6. Keep `spatial_drc` for confirmed world-positioned sounds and `add_drc` for direct/player-local feedback.

Do not continue solving unresolved sound issues on the historical donor branch.