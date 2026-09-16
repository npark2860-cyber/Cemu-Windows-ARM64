# BOTW DualSense Speaker Duplicate Proof

Status: active physical-proof experiment

Branch: `diag/botw-dualsense-speaker-duplicate`
Base branch snapshot: `diag/botw-sound-source-tracer` at `c7c42a16ca1382edc672a224417757dafe97d67b`

## Goal

Prove the smallest useful routing primitive for the BOTW DualSense audio project:

```text
one already-identified BOTW local sound
  -> keep original TV mix
  -> add DRC0 mix
  -> existing Cemu GamePad PCM path
  -> DualSense USB speaker
```

This is **Duplicate mode** only. No TV attenuation/removal is attempted.

## Why weapon swing first

The v3 physical tracer already resolved pure empty-air weapon swing cues by exact BARS/track name. Using those cues avoids mixing source-identification uncertainty with routing uncertainty.

Current proof whitelist:

- `Spear_Swing1`
- `Spear_Swing2`
- `Spear_SwingFast1`
- `Spear_SwingFast2`
- `LSword_Swing1`
- `LSword_Swing3`
- `LSword_Swing5`

Do not expand this list from timing guesses. Add only runtime-confirmed local cues.

## Diagnostic implementation

`tools/botw_speaker_duplicate_patch.py` first applies the validated sound-source tracer v3 hooks, then adds a narrow routing hook at `AXSetVoiceState(ON)`.

For a whitelisted resolved sample:

1. Existing TV device mix is left untouched.
2. If DRC0 already has an authored route, it is preserved.
3. Otherwise DRC0 stereo main bus is added at nominal volume `0x6000` on channels 0/1.
4. The CSV emits an additional event:
   - `route_drc_duplicate`: diagnostic route added.
   - `route_drc_existing`: DRC0 route already existed, so no overwrite was performed.

The experiment does not route impact, equip, landing, enemy-hit, ambience, explosions, or unresolved PlayerVoice cues.

## Known transport prerequisite

Cemu GamePad PCM -> DualSense USB speaker has already passed physically, but a fresh USB reconnect currently needs the DualSense speaker route initialized once by DSX. After that DSX can be closed and Cemu continues using the speaker until reconnect.

That route-initialization defect is separate from this proof. Do not change firmware or re-investigate the already-closed generic output-flag bug during this experiment.

## Physical PASS

1. Use the ARM64 artifact from workflow `BOTW DualSense Speaker Duplicate ARM64`.
2. Delete/rename any old `botw_sound_source_trace.csv`.
3. Initialize the known DualSense USB speaker route and select it as Cemu GamePad audio output.
4. Load BOTW in a quiet area.
5. Swing a spear repeatedly in empty air; optionally test a two-handed sword.
6. Confirm the original TV swing sound remains.
7. Confirm the same local swing/whoosh is clearly audible from the DualSense speaker.
8. Confirm ambient/world sounds did not generally move to the controller.
9. Confirm fresh CSV contains `route_drc_duplicate` for the corresponding resolved swing track.

Primary PASS statement:

```text
BOTW resolved weapon-swing AX voice -> original TV + added DRC0 -> DualSense speaker
```

## After PASS

Do not broaden routing blindly. Next audio work is:

1. finish packed-resource tracer v4 (`SARC -> embedded BARS`) for `PlayerVoice.bars`;
2. correlate `PVxxx_xx` with SLink/GameROMPlayer semantics where possible;
3. add Link-local player voice/body reactions to the same semantic routing layer;
4. solve native DualSense USB speaker route initialization so DSX is no longer needed;
5. only then evaluate optional Move/TV-attenuation policy.

Haptics/BNVIB exploration is being handled independently and should not be mixed into this diagnostic branch.
