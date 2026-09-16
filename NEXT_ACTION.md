# NEXT ACTION — BOTW DualSense Speaker Duplicate

## Immediate action

Check existing CI first. Do not start a duplicate build.

Workflow run:

`35078312616`

Job:

`104735889958`

Branch:

`diag/botw-dualsense-speaker-duplicate`

The run already passed:

- checkout
- `tools/botw_speaker_duplicate_patch.py` application
- diagnostic diff / `git diff --check`

At handoff time the remaining ARM64 build pipeline was still in progress.

## If CI succeeds

1. Confirm artifact name `Cemu-BOTW-DualSense-SpeakerDuplicate-ARM64` exists.
2. Use that artifact for the first physical Duplicate-mode test.
3. Delete/rename old `botw_sound_source_trace.csv` before launch.
4. Use a spear in empty air as the primary test.
5. Expected:
   - TV swing remains
   - same swing/whoosh appears from DualSense speaker
   - CSV contains `route_drc_duplicate` with a whitelisted `Spear_Swing*` or `LSword_Swing*` track
6. Keep ambient/world sounds as a negative control.
7. Record physical result in `CURRENT_HANDOFF.md` and `docs/BOTW_DUALSENSE_SPEAKER_DUPLICATE.md`.

## If CI fails

Inspect only the first failing step.

Priority:

1. patch step / diagnostic diff: anchor or generated-code problem
2. configure/build: compiler diagnostic from `ax_voice.cpp` or generated tracer helper
3. packaging only after compile is clean

Do not change unrelated emulator code.

## After physical PASS

Return to audio semantic expansion, not haptics:

1. implement tracer v4 packed-resource discovery (`SARC -> embedded BARS`)
2. recover `PlayerVoice.bars` at runtime
3. correlate `PVxxx_xx` with SLink/GameROMPlayer semantics
4. extend Duplicate routing to confirmed Link-local voice/body cues
5. solve native DualSense speaker route init later

Do not work on the 46 TOTK BNVIB Haptic Explorer here; that is a separate tab/workstream.
