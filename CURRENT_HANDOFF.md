# CURRENT HANDOFF — BOTW DualSense Speaker Duplicate

Status snapshot: 2026-09-16

## Source of truth

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Active audio experiment branch:

`diag/botw-dualsense-speaker-duplicate`

Branch HEAD before this handoff update was:

`3f58054adad268e1ba25c59ada15c22316c57c8d`

Always query the actual branch HEAD before changing anything. `main` is not part of this experiment.

## What is now physically proven

### 1. BOTW weapon-swing AX voice -> DualSense speaker: PASS

The narrow Duplicate-mode proof works on physical hardware.

Current diagnostic whitelist:

- `Spear_Swing1`
- `Spear_Swing2`
- `Spear_SwingFast1`
- `Spear_SwingFast2`
- `LSword_Swing1`
- `LSword_Swing3`
- `LSword_Swing5`

Implementation:

`tools/botw_speaker_duplicate_patch.py`

The patch keeps the original TV device mix untouched and, when the resolved track matches the diagnostic whitelist, adds DRC0 stereo main-bus routing at nominal volume `0x6000` if DRC0 was not already authored.

Physical result reported by the user:

- weapon swing/whoosh is clearly audible from the DualSense internal speaker;
- the controller-local presentation feels dramatically different from TV-only playback;
- the TV copy is perceptually much less obvious because the controller speaker is close to the user and strongly exposes the swing transient.

Important precision: code preserves the TV mix, but the user has not yet done a strict isolated A/B with the controller speaker muted to quantify how audible the TV swing remains. Do not misreport this as TV route removal.

### 2. Native DualSense USB speaker route initialization: PASS / CLOSED

This was validated on the separate branch:

`exp/dualsense-gamepad-core-arm64`

Validated implementation commit:

`638d19309f94acde70e9a0496c5a3bbe3027c25d`

CI:

`35084659609` — PASS

Validation doc branch HEAD after documentation:

`af6fa6fb1abf7d426fb5572dfc1b0e04fa9fe015`

Confirmed architecture:

`Gamepad-Core DualSenseSettings(...) -> speaker route/volume -> UpdateOutput() -> DualSense USB HID`

Cemu/Windows USB audio remains the PCM transport. DSX is no longer required in the target design. On connect/reconnect Cemu should initialize speaker route/volume automatically; there is no reason for the final user experience to require a manual Enable Speaker button.

## CI for the BOTW Duplicate proof

Workflow:

`BOTW DualSense Speaker Duplicate ARM64`

Run:

`35078312616`

Job:

`104735889958`

Result:

**SUCCESS**

Workflow head SHA:

`3fc397d58e7765d96bb29088cbbbc8ccf202e00a`

Do not duplicate this proof build without a regression or a new implementation change.

## Architectural correction after physical proof

The current exact-name whitelist is intentionally a proof-only hack. It must NOT become the production architecture.

Do not keep growing C++ lists such as `Spear_Swing*`, `LSword_Swing*`, or hundreds of `PVxxx_xx` entries.

Production direction:

```text
BOTW semantic sound identity
  -> routing classifier / mapping policy
  -> TV / DualSense / both + gain policy
  -> existing AX/DRC audio path
```

Preferred identification order:

1. SLink / GameROMPlayer semantic event/category if recoverable;
2. source path/resource category/prefix as a fallback;
3. exact track name only as a narrow fallback, not the main design.

A data-driven mapping file may still be useful for policy, but merely moving hundreds of exact names from C++ into JSON does not solve the semantic hardcoding problem by itself.

## Next technical target

Return to semantic source recovery rather than adding more hardcoded sound names.

Priority:

1. finish packed-resource tracer v4: `SARC -> embedded BARS`;
2. physically recover runtime `TitleBG.pack::Sound/Resource/PlayerVoice.bars -> PVxxx_xx` provenance;
3. correlate runtime player-voice playback with `SLink/GameROMPlayer` semantics where possible;
4. determine whether routing can be driven by semantic event/category instead of exact track enumeration;
5. build the generic routing-policy layer only after that evidence is available;
6. integrate the already-proven native speaker init into the Cemu-side DualSense connect/reconnect path.

## Current audio path model

```text
BOTW sound event
-> AX voice
-> existing TV route remains
-> selected local voice receives DRC0 route
-> Cemu g_padAudio
-> Windows DualSense USB audio endpoint
-> DualSense internal speaker
```

The actual PCM is not extracted to WAV and replayed separately. It is the same in-game AX voice routed to an additional Wii U DRC output bus.

## Final user-facing behavior target

No per-event runtime toggle is needed.

Expected final behavior:

```text
DualSense connects
-> speaker route initialized automatically once

BOTW local/player event occurs
-> semantic classifier decides destination automatically
-> target sound reaches DualSense speaker
```

An optional global `DualSense speaker enhancement` preference may exist, but diagnostic `Enable speaker` UI is not part of the final runtime design.

## Closed / do not retest without regression

- BOTW weapon-swing -> DRC/DualSense narrow routing proof
- native DualSense USB speaker route/volume enable proof
- DSX initialization dependency for the target design
- sound tracer v3 `bars_path known / track_name blank` defect
- Haptic State Logger v0.1 baseline
- DualSense generic Gamepad-Core output-flag bug
- DualSense firmware/update path
- normal BOTW GamePad authored-sound hunting as a broad source of effects

## Parallel work boundary

TOTK BNVIB / 46-pattern Haptic Explorer work is being handled in another tab. Do not mix that implementation into this audio-routing branch.

See also:

- `NEXT_ACTION.md`
- `HANDOFF_PROMPT.md`
- `docs/BOTW_DUALSENSE_SPEAKER_DUPLICATE.md`
- `docs/BOTW_SOUND_SOURCE_TRACER_FINDINGS.md`
- `docs/BOTW_PLAYERVOICE_TRACK_LIST.md`
