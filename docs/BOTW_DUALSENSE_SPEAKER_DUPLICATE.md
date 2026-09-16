# BOTW DualSense Speaker Duplicate Proof

Status: **PHYSICAL PASS / proof CLOSED**

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

This proof uses Duplicate mode only. No TV attenuation/removal is attempted.

## Proof whitelist

The v3 physical tracer had already resolved pure empty-air weapon swing cues by exact BARS/track name.

The diagnostic proof whitelist is:

- `Spear_Swing1`
- `Spear_Swing2`
- `Spear_SwingFast1`
- `Spear_SwingFast2`
- `LSword_Swing1`
- `LSword_Swing3`
- `LSword_Swing5`

This list is now frozen as a regression/proof fixture. Do not grow it into the production architecture.

## Diagnostic implementation

`tools/botw_speaker_duplicate_patch.py` first applies the validated sound-source tracer v3 hooks, then adds a narrow routing hook at `AXSetVoiceState(ON)`.

For a whitelisted resolved sample:

1. existing TV device mix is left untouched;
2. if DRC0 already has an authored route, it is preserved;
3. otherwise DRC0 stereo main bus is added at nominal volume `0x6000` on channels 0/1;
4. CSV emits `route_drc_duplicate` when the diagnostic hook adds the route;
5. CSV emits `route_drc_existing` when the game already had DRC0 routing and no overwrite occurs.

The experiment does not route impact, equip, landing, enemy-hit, ambience, explosions, or unresolved PlayerVoice cues.

## CI result

Workflow:
`BOTW DualSense Speaker Duplicate ARM64`

Run:
`35078312616`

Job:
`104735889958`

Result:
**SUCCESS**

## Physical result

**PASS.**

The user physically tested BOTW with the DualSense speaker path active and confirmed the weapon swing/whoosh is clearly emitted from the DualSense internal speaker. The controller-local presentation produces a much stronger and substantially different physical/spatial impression than the same effect buried in the TV mix.

The user also observed that the TV swing can feel almost absent while the controller speaker is active. The implementation intentionally preserves the TV mix, so this is currently treated as a perceptual dominance/masking observation, not evidence that the TV route was removed. A strict speaker-muted TV A/B is optional if later documentation needs it.

Primary proven primitive:

```text
resolved BOTW weapon-swing AX voice
-> original AX playback
-> added DRC0 route
-> Cemu g_padAudio
-> DualSense speaker
```

No separate WAV extraction or secondary sound player is used.

## Native DualSense speaker init status

The old DSX one-time initialization limitation has separately been solved and physically validated.

Branch:
`exp/dualsense-gamepad-core-arm64`

Validated implementation commit:
`638d19309f94acde70e9a0496c5a3bbe3027c25d`

CI run:
`35084659609` — PASS

Gamepad-Core can enable the DualSense internal speaker route/volume natively over USB HID. Cemu/Windows USB audio remains the PCM transport.

Final integration should perform this initialization automatically on controller connect/reconnect. A manual Enable Speaker button is diagnostic-only.

## Production architecture decision

The exact-name whitelist is proof-only hardcoding.

Do not scale the production feature by embedding hundreds of sound names in C++.

Preferred production pipeline:

```text
BOTW semantic sound identity
-> semantic routing classifier/policy
-> TV | DualSense | both + gain
-> existing AX/DRC path
```

Preferred identity hierarchy:

1. `SLink` / `GameROMPlayer` semantic event or category;
2. resource/path/category or stable prefix;
3. exact track name only as a fallback/exception.

A data-driven mapping file can hold policy, but simply relocating hundreds of exact names into JSON is not by itself a semantic solution.

## Next work

1. resume packed-resource tracer v4 (`SARC -> embedded BARS`);
2. recover runtime `TitleBG.pack::Sound/Resource/PlayerVoice.bars` provenance;
3. correlate `PVxxx_xx` playback with SLink/GameROMPlayer semantics;
4. determine the least-hardcoded routing identity/category available at runtime;
5. implement the generic routing-policy layer;
6. integrate the already-proven native speaker route initialization into Cemu DualSense connect/reconnect.

Haptics/BNVIB exploration remains a separate workstream and must not be mixed into this diagnostic branch.
