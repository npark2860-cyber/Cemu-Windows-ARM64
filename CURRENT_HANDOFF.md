# CURRENT HANDOFF — BOTW DualSense Speaker Duplicate

Status snapshot: 2026-09-16

## Source of truth

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Active experiment branch:

`diag/botw-dualsense-speaker-duplicate`

This branch was created from `diag/botw-sound-source-tracer` at:

`c7c42a16ca1382edc672a224417757dafe97d67b`

Always query the actual branch HEAD before changing anything. `main` is not part of this experiment.

## Current objective

Prove one original BOTW local sound can be duplicated to the Wii U DRC/GamePad mix while preserving the TV mix, then use the already-validated Cemu GamePad PCM -> DualSense USB speaker path.

Target proof:

```text
resolved BOTW weapon-swing AX voice
  -> TV remains unchanged
  -> DRC0 stereo mix added
  -> Cemu GamePad audio
  -> DualSense speaker
```

## Implemented on this branch

Commit `d358496f422939ca09a219e0443df5f4275df491`

- added `tools/botw_speaker_duplicate_patch.py`
- reuses the validated v3 sound-source tracer patch first
- adds routing only after exact source/track resolution
- whitelist is limited to already runtime-confirmed empty-air swing cues:
  - `Spear_Swing1`
  - `Spear_Swing2`
  - `Spear_SwingFast1`
  - `Spear_SwingFast2`
  - `LSword_Swing1`
  - `LSword_Swing3`
  - `LSword_Swing5`
- TV mix is untouched
- if DRC0 already has a route, it is preserved
- otherwise DRC0 stereo main bus is added at `0x6000` nominal volume on channels 0/1
- CSV event `route_drc_duplicate` means the diagnostic hook added the route
- CSV event `route_drc_existing` means the game already had DRC0 routing and the hook did not overwrite it

Commit `3fc397d58e7765d96bb29088cbbbc8ccf202e00a`

- added workflow `.github/workflows/botw-dualsense-speaker-duplicate-arm64.yml`
- artifact target: `Cemu-BOTW-DualSense-SpeakerDuplicate-ARM64`

Commit `0d6b606b72066c217878afed7c2f679b3f92bb99`

- added `docs/BOTW_DUALSENSE_SPEAKER_DUPLICATE.md`
- records design, safety boundary and physical PASS criteria

## Current CI

Workflow: `BOTW DualSense Speaker Duplicate ARM64`

Run: `35078312616`

Job: `104735889958`

Workflow head SHA: `3fc397d58e7765d96bb29088cbbbc8ccf202e00a`

Last verified status while preparing this handoff:

- checkout PASS
- patch application PASS
- `git diff --check` / diagnostic diff step PASS
- build environment setup in progress
- final ARM64 build result not yet recorded in this snapshot

Do **not** start a duplicate run until this run is checked.

## Physical prerequisites already proven

Cemu DRC/GamePad PCM can reach the DualSense USB speaker.

Known remaining transport limitation:

- after a fresh DualSense USB reconnect, DSX currently has to initialize the speaker route once
- DSX can then be closed and Cemu continues to use the speaker until reconnect

This limitation is separate from the current AX routing proof. Do not mix native speaker-init work into the first duplicate-routing validation.

## Physical PASS condition

Use the new artifact after CI succeeds.

1. Delete/rename previous `botw_sound_source_trace.csv`.
2. Initialize the known DualSense USB speaker route and select DualSense speaker as Cemu GamePad audio output.
3. Load BOTW in a quiet area.
4. Swing a spear repeatedly in empty air; optionally test a two-handed sword.
5. TV swing/whoosh must remain audible.
6. The same local swing/whoosh must also be clearly audible from the DualSense speaker.
7. Ambient/world sounds must not generally move to the controller.
8. Fresh CSV should contain `route_drc_duplicate` for the corresponding resolved swing track.

Primary PASS:

`BOTW swing AX voice -> original TV + added DRC0 -> DualSense speaker`

## Closed / do not retest without regression

- sound tracer v3 defect `bars_path known / track_name blank`: physical result 321 -> 0
- Haptic State Logger v0.1 baseline
- DualSense generic Gamepad-Core output-flag bug
- DualSense firmware/update path
- normal BOTW GamePad authored sound hunting: no useful broad authored DRC effect set found

## Important parallel work boundary

TOTK BNVIB / 46-pattern Haptic Explorer work is being handled in another tab. Do not mix that implementation into this speaker branch.

This tab/branch is now audio-routing first.

## After speaker Duplicate PASS

1. return to packed sound-source tracer v4: `SARC -> embedded BARS`
2. physically prove `AX -> TitleBG.pack::Sound/Resource/PlayerVoice.bars -> PVxxx_xx`
3. use SLink/GameROMPlayer metadata to recover semantic player-voice identity where possible
4. route confirmed Link-local player voice/body reactions through the same semantic layer
5. solve native DualSense USB speaker route initialization so DSX is no longer needed
6. only then consider optional Move/TV attenuation

See also:

- `docs/BOTW_DUALSENSE_SPEAKER_DUPLICATE.md`
- `docs/BOTW_SOUND_SOURCE_TRACER_FINDINGS.md`
- `docs/BOTW_PLAYERVOICE_TRACK_LIST.md`
- `docs/BOTW_DUALSENSE_TODO.md`
- `docs/BOTW_HAPTICS_SOURCE_INDEX.md`
