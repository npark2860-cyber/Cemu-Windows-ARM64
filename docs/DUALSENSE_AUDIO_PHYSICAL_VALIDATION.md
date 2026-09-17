# DualSense Audio Physical Validation

Status: native USB speaker path PASS; AX selective routing PASS; spatial DRC physical behavior PASS
Status date: 2026-09-18
Historical donor branch: `feat/enhanced-sound-experience-v1`

> This branch is now a donor/reference branch only. Current overall sound status and migration rules are recorded in `docs/ENHANCED_SOUND_CURRENT_STATUS.md`.

## Confirmed USB architecture

The physical USB audio path is validated:

`Wii U DRC/GamePad audio -> Cemu g_padAudio -> Windows audio backend -> DualSense USB audio endpoint -> DualSense internal speaker`

A separate custom PCM engine is not needed for the USB baseline. Cemu's existing GamePad/DRC audio pipeline remains the transport.

## Historical DSX observation

Early validation established that:

1. a fresh DualSense USB connection could initially have its internal speaker route disabled;
2. starting DSX initialized speaker routing;
3. the route remained active after DSX exited;
4. reconnecting the controller reset that route state.

This isolated the missing behavior to controller-side output initialization rather than PCM transport.

## Native Cemu-side initialization

Native DualSense speaker initialization was subsequently integrated using Gamepad-Core support. The production path no longer relies on DSX as a runtime dependency.

The validated design keeps Cemu in control of PCM transport and uses controller initialization only to configure the DualSense speaker/output state.

Known production service:

`EnhancedSoundDualSenseService`

Current initialization path uses DualSense output settings with speaker enabled and a non-zero/full speaker volume.

Native USB speaker routing without DSX was physically validated during the Enhanced Sound work.

## AX selective routing validation

Cemu exposes separate TV and DRC/GamePad mixes per AX voice. Enhanced Sound uses that existing architecture instead of post-mix separation.

Validated chain:

`BOTW resource/source -> AX voice -> EnhancedSoundRouter -> TV/DRC policy -> Cemu GamePad PCM -> DualSense speaker`

Physical tests confirmed original BOTW effects can be routed to the controller speaker at in-game timing.

## `add_drc`

`add_drc` is the direct/player-local routing mode.

Production behavior:

- preserves native game DRC state;
- adds the configured DRC send;
- applies the matched TV policy;
- persists after later game-side TV/DRC mix writes.

TV/DRC persistence is represented by production commit:

`06bcc9580cddd3ffeff640f801abfa34c2a10253`

The implementation uses `internalMixWrite` to avoid treating Cemu's own device-mix writes as fresh native game state.

## `spatial_drc`

`spatial_drc` is the world-positioned routing mode.

Production behavior:

- TV output remains native;
- controller DRC send follows native TV main-bus spatial volume/delta;
- route gain is the maximum controller send;
- later native TV mix updates refresh the controller send.

Physical BOTW validation confirmed distance-sensitive controller-speaker behavior for world-positioned sounds.

Confirmed examples include:

- Master Cycle world audio;
- Remote Bomb explosion.

User physical result: `spatial_drc` behavior worked as intended when distance changed.

## Source/fingerprint reliability

Repeated/rapid one-shot source resolution was hardened in:

`a8d5b5537bac09a7dcffaece724b205ec18f7a96`

`audio: harden BARS fingerprint catalog parsing`

After this fix the user reported the previously dropping repeated sound routing as fully corrected. Treat this issue as PASS/CLOSED unless a concrete regression is reproduced.

## Current unresolved audio cases

### Magnesis / Stasis continuous hum

The continuous active sounds are not fixed by exact routes for:

- `SE_MagneCatch_Hold`
- `BitaLock_Timer03`

Current leading hypothesis is that an already-running loop voice may be activated through VE/volume-envelope changes rather than a new voice start/sample replacement.

This remains unproven and should be diagnosed later through VE/lifecycle telemetry on a diagnostic Sound edition.

### Player/enemy shared weapon cues

At least one weapon-swing cue appears reusable by enemies. Source+track identity alone may therefore be insufficient for player-only routing.

Do not solve this with BOTW-specific hardcoding in the generic router. Future diagnostics should inspect contextual AX/spatial/emitter evidence.

### Intermittent session state

One Ancient-weapon test session appeared silent and worked again after restart with no policy change. This is currently classified as an intermittent runtime-state observation, not as a confirmed route-definition regression.

## Decision

- USB Cemu -> DualSense speaker PCM transport: **PASS**.
- Native Cemu-side DualSense speaker initialization: **PASS**.
- DSX runtime dependency: **not required**.
- Per-voice TV/DRC routing: **PASS**.
- `add_drc` production architecture: **PASS**.
- TV/DRC persistence: **PASS**.
- BARS fingerprint hardening for rapid/repeated sounds: **PASS/CLOSED**.
- `spatial_drc` physical distance behavior: **PASS**.
- Magnesis/Stasis continuous-loop routing: **OPEN**.
- player/enemy shared-cue discrimination: **OPEN**.

Do not replace Cemu's existing DRC audio pipeline. Do not continue production development directly on the historical donor branch after the official Sound lineage is reconstructed.