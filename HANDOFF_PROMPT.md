# HANDOFF PROMPT — Cemu ARM64 / Enhanced Sound Experience

Continue the Enhanced Sound Experience work from GitHub source of truth.

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Active branch: `feat/enhanced-sound-experience-v1`

At the start of the new tab:

1. read `CURRENT_HANDOFF.md`;
2. read `NEXT_ACTION.md`;
3. query the actual feature-branch HEAD;
4. inspect the current `sound_routes.ini` and the latest relevant workflow/run before editing;
5. do not touch `main`;
6. do not rerun PASS/CLOSED experiments without a real regression.

Validated implementation baseline before handoff documentation:

`731a6a0fb5533f254feca3538f67881eded70e4b`

Latest Spatial DRC build:

- workflow: `Enhanced Sound Spatial DRC ARM64`
- run `35212129171` — SUCCESS
- job `105171882774` — SUCCESS
- artifact `Cemu-EnhancedSound-SpatialDRC-ARM64`
- artifact ID `10495075044`

The build PASS proves compile/structure only. `spatial_drc` is not yet physically validated in BOTW.

## Current architecture

Cemu core is generic. BOTW sound selection stays in Graphic Pack `sound_routes.ini`.

Current modes:

```text
add_drc
  -> additive DualSense/DRC send
  -> matched TV mix = 50 percent
  -> persistent across later game TV/DRC writes

spatial_drc
  -> native TV mix unchanged
  -> DualSense/DRC send follows native TV front L/R main-bus volume
  -> route gain is the maximum send
  -> native TV delta is also propagated proportionally
  -> intended for distance-aware world sounds such as explosions
```

No BOTW bomb/explosion identity is hardcoded yet. Confirm a real track/source before adding the first `spatial_drc` rule.

## Latest physical report that still needs regression testing

On the earlier pre-persistence build the user reported:

- TV sound for routed effects did not become quieter;
- one-handed sword routed only the 3rd combo hit;
- the other one-handed hits/charge stages did not all route;
- overlapping controller-speaker sounds sometimes felt swallowed.

Commit `06bcc9580cddd3ffeff640f801abfa34c2a10253` added TV+DRC persistence and is intended to address game mix writes undoing enhancement. It still requires physical validation.

## Critical policy inconsistency — fix before claiming one-handed coverage

Current policy contains:

```ini
[Route.SwordSwingFourth]
source = M_SceneStatic.bars
track = SE_NSword_SwingMiddleEnemy
mode = add_drc
gain = 0x6000
```

Current Spatial DRC workflow also asserts that this is a confirmed fourth-hit route.

However, earlier fingerprint interpretation classified `SE_NSword_SwingMiddleEnemy` as enemy audio and said it should be excluded.

Treat this as unresolved. Re-check evidence. If it is not proven to be player 4th-hit audio, remove both the route and the workflow assertion. Do not keep an enemy route merely to fill combo coverage.

Known evidence-backed one-hand candidates include:

- `SE_NSword_SwingPlayer*` — previous physical match corresponded to 3rd hit;
- `SE_ESf_SWING_SWORD_S`;
- `NSword_Charge_Lv1`;
- `SE_SW_KAITENGIRI`.

If coverage is still incomplete, use one focused ordered diagnostic (`1 -> 2 -> 3 -> 4`, then charge stages) rather than broad wildcard guessing.

## DualSense speaker level

Current source uses:

`DualSenseSettings(0, 0, 1, 0, 255, 255, 0, 0)`

The source change from 180 to 255 is present. Physical loudness improvement has not been separately proven. If the user reports no difference, inspect settings overwrite / GamePad volume / Windows endpoint paths before changing AX gain.

## Already PASS / CLOSED

Do not redo without regression:

- narrow BOTW weapon swing -> DRC0 -> DualSense physical proof: run `35078312616`;
- native DualSense USB speaker route without DSX: commit `638d19309f94acde70e9a0496c5a3bbe3027c25d`, run `35084659609`;
- packed PlayerVoice discovery and physical controller-speaker output;
- Spatial DRC native ARM64 compile: run `35212129171`.

## Next order

Follow `NEXT_ACTION.md` exactly:

1. resolve the `SE_NSword_SwingMiddleEnemy` contradiction;
2. physically validate TV/DRC persistence;
3. verify one-handed sequence precisely;
4. identify one real world-positioned bomb/explosion sound and add first `spatial_drc` policy;
5. investigate DualSense 255 only if physical volume still appears unchanged.

Do not mix TOTK/Switch BNVIB/Haptic Explorer work into this branch.