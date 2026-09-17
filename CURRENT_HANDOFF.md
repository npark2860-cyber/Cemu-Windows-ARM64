# CURRENT HANDOFF — Enhanced Sound Experience v1

Status snapshot: 2026-09-17

## Source of truth

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Active branch: `feat/enhanced-sound-experience-v1`

Do not touch `main`. Query the actual branch HEAD at the start of the next tab because the documentation commits that create this handoff advance the branch after the validated implementation commit below.

Validated implementation HEAD before handoff documentation:

`731a6a0fb5533f254feca3538f67881eded70e4b`

Commit message: `audio: add spatial DRC routing mode`

## Latest CI — PASS

Workflow: `Enhanced Sound Spatial DRC ARM64`

Run: `35212129171` — SUCCESS

Job: `105171882774` — SUCCESS

Workflow input HEAD: `13d65a38dbda97e0350fece15ae80fa330bd4cf1`

Workflow-generated validated source HEAD: `731a6a0fb5533f254feca3538f67881eded70e4b`

Artifact: `Cemu-EnhancedSound-SpatialDRC-ARM64`

Artifact ID: `10495075044`

This proves native Windows ARM64 configure/build and structural validation only. `spatial_drc` has NOT yet received a physical BOTW gameplay PASS.

## Current implementation chain

Important recent commits:

- `06bcc9580cddd3ffeff640f801abfa34c2a10253` — persist Enhanced Sound TV and DRC routing across later game `AXSetVoiceDeviceMix` writes.
- `4eb95378c14ece344d15b6cbd33533567f97867d` — add `tools/add_enhanced_sound_spatial_drc.py`.
- `13d65a38dbda97e0350fece15ae80fa330bd4cf1` — add dedicated Spatial DRC ARM64 validation workflow.
- `731a6a0fb5533f254feca3538f67881eded70e4b` — workflow-generated validated implementation.

## Implemented routing modes

`EnhancedSoundRouter::Mode` now supports:

- `add_drc`
- `spatial_drc`

`add_drc` keeps the existing enhanced-sound behavior:

- matched sound receives additive DRC/controller send;
- matched TV mix is reduced to 50 percent;
- later native TV/DRC writes are captured and enhancement is reapplied persistently.

`spatial_drc` is the new generic distance-aware mode:

- native TV mix is left unchanged;
- front L/R TV main-bus volume is used as the DRC distance envelope;
- `0x8000` TV volume means full route gain;
- controller send is approximately `routeGain * nativeTvVolume / 0x8000`;
- TV `delta` is proportionally carried into DRC so fades/distance changes do not become static;
- per-voice route mode/gain are retained for persistence when the game later rewrites TV/DRC mix.

No BOTW bomb/explosion track was hardcoded. A confirmed trace identity is still required before adding the first `spatial_drc` game policy rule.

## Physical evidence already PASS / CLOSED

Do not repeat without regression:

- narrow BOTW weapon swing -> DRC0 -> DualSense speaker physical proof; CI run `35078312616`.
- native DualSense USB internal-speaker route initialization without DSX; commit `638d19309f94acde70e9a0496c5a3bbe3027c25d`, CI run `35084659609`.
- packed `TitleBG.pack::Sound/Resource/PlayerVoice.bars` discovery and PlayerVoice controller-speaker output were later physically proven.

Current DualSense production service uses:

`DualSenseSettings(0, 0, 1, 0, 255, 255, 0, 0)`

The source value is therefore 255. Whether `180 -> 255` produces a meaningful physical loudness increase has not yet been confirmed separately.

## Latest physical regressions / unresolved behavior

User reported on the pre-persistence build:

1. matched sound TV volume did not audibly reduce despite intended 50 percent attenuation;
2. one-handed sword combo routed only the 3rd hit to DualSense;
3. 1st/2nd/4th hit and charge stages did not all route as intended;
4. when several sounds overlap, some controller-speaker sounds can feel swallowed.

`06bcc958...` is specifically intended to fix the first problem and also makes DRC enhancement persistent across later game mix writes. It has compiled, but the TV/DRC persistence change still needs physical confirmation.

The one-handed policy was expanded using prior fingerprint evidence, but exact hit-by-hit mapping is NOT fully proven.

## IMPORTANT policy inconsistency to resolve before trusting one-handed coverage

Current `sound_routes.ini` at `731a6a0...` contains:

```ini
[Route.SwordSwingFourth]
source = M_SceneStatic.bars
track = SE_NSword_SwingMiddleEnemy
mode = add_drc
gain = 0x6000
```

Earlier fingerprint interpretation treated `SE_NSword_SwingMiddleEnemy` as an enemy sound and said it should remain excluded. The current workflow instead labels it as a confirmed fourth-hit route and explicitly validates its presence.

This is a contradiction, not a PASS. Do not assume the track is the player's 4th hit. Revalidate/remove this rule before claiming one-handed 1/2/3/4 coverage.

Other current evidence-backed one-hand candidates include:

- `SE_NSword_SwingPlayer*` — the physically observed previous match corresponded to the 3rd hit;
- `SE_ESf_SWING_SWORD_S`;
- `NSword_Charge_Lv1`;
- `SE_SW_KAITENGIRI`.

If individual combo/charge stages remain missing, use a focused ordered diagnostic rather than broadening patterns blindly.

## Architecture constraints

- core Cemu remains game-agnostic;
- game-specific selection stays in Graphic Pack `sound_routes.ini`;
- no expanding BOTW exact-name whitelist in C++;
- native Wii U DRC/GamePad audio remains authoritative;
- feature OFF = stock behavior;
- do not rerun old PASS workflows without a regression;
- do not mix TOTK/Switch BNVIB/Haptic Explorer work into this branch.

See `NEXT_ACTION.md` and `HANDOFF_PROMPT.md`.