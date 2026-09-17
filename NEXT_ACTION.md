# NEXT ACTION — Enhanced Sound Experience v1

## Start here

Active branch: `feat/enhanced-sound-experience-v1`

Query actual HEAD before editing. Do not touch `main`.

Validated implementation baseline before handoff docs:

`731a6a0fb5533f254feca3538f67881eded70e4b`

Spatial DRC workflow run `35212129171` / job `105171882774`: SUCCESS.

Do not rerun this build merely to reconfirm it.

## Immediate order

### 1. Resolve the one-handed policy contradiction first

Current policy contains:

```ini
track = SE_NSword_SwingMiddleEnemy
```

under `[Route.SwordSwingFourth]`, and the Spatial DRC workflow currently asserts that it is a confirmed fourth-hit route.

Earlier fingerprint interpretation classified the same track as enemy audio. Treat this as unresolved. Do not claim one-handed 1/2/3/4 coverage until it is revalidated.

Preferred action:

- inspect the original focused trace/fingerprint evidence around the ordered one-handed sequence;
- if evidence does not prove player 4th hit, remove the rule and remove the workflow assertion;
- if still ambiguous, create one focused diagnostic build for `hit1 -> hit2 -> hit3 -> hit4`, then charge stages separately.

Do not broaden to generic `*Sword*` patterns and do not route enemy sounds merely to fill the missing hit.

### 2. Physically validate the persistence fix

Use the newest valid ARM64 build after step 1.

Check:

- matched `add_drc` sound is still heard from DualSense;
- matched TV sound is now audibly reduced to about 50 percent;
- nonmatched/BGM/environment TV audio is unchanged;
- later game mix updates do not restore matched TV to full level;
- DRC/controller send does not disappear after later game DRC writes;
- overlapping matched sounds are observed for any remaining swallowing behavior.

`06bcc958...` added persistence for both TV and DRC writes, but physical PASS is still required.

### 3. Verify one-handed sequence with exact observations

After policy cleanup, test in order:

```text
hit 1
hit 2
hit 3
hit 4
charge stage 1
charge stage 2
charge stage 3 / spin release as applicable
```

Record only which stages reach the controller speaker. If anything remains missing, use focused trace correlation rather than guessing track names.

### 4. Add the first real `spatial_drc` policy only after identity is confirmed

Core support already exists and compiles.

Desired first use is a world-positioned sound such as a bomb/explosion where native TV volume already changes with distance.

Do not invent a BOTW explosion track name. Find/confirm the exact source/track from existing trace data or one bounded diagnostic, then add for example:

```ini
mode = spatial_drc
gain = 0x6000
```

Expected behavior:

- TV remains native/full authored mix;
- DualSense send follows native TV front L/R volume/delta;
- far explosion becomes quieter on controller, near explosion louder;
- max controller send remains capped by route gain.

### 5. DualSense 255 loudness only if physical volume still seems unchanged

Source currently uses:

`DualSenseSettings(0, 0, 1, 0, 255, 255, 0, 0)`

If physical 180 vs 255 still sounds effectively identical, do not increase AX route gain blindly. First inspect:

- all `DualSenseSettings(...)` calls for later overwrite;
- GamepadCore output refresh behavior;
- Cemu GamePad audio volume path;
- Windows GamePad/DualSense endpoint volume.

Use bounded logging only if source inspection cannot settle persistence of the 255 setting.

## Already PASS / do not redo

- narrow weapon-swing -> DRC0 -> DualSense proof, run `35078312616`;
- native DualSense USB speaker-route initialization, run `35084659609`;
- packed PlayerVoice discovery and physical controller-speaker output;
- native ARM64 compile for Spatial DRC implementation, run `35212129171`.

## Workstream boundary

No TOTK/Switch BNVIB or 46-pattern Haptic Explorer work in this branch.