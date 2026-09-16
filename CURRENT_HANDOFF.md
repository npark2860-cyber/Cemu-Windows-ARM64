# CURRENT HANDOFF — Enhanced Sound Experience v1

Status snapshot: 2026-09-16

## Source of truth

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Active implementation branch:

`feat/enhanced-sound-experience-v1`

Branch HEAD at the start of this handoff session:

`f0d87acccba81819e8019d3eeb67bdf4f97ab411`

This branch was created from the latest BOTW DualSense speaker-duplicate work. Always query the actual branch HEAD before changing anything. `main` is not part of this work.

No production Enhanced Sound implementation was committed in this session before this handoff. The work performed was architecture/code-path inspection only.

## Already physically proven — do not repeat without regression

### BOTW AX voice -> DualSense speaker Duplicate proof: PASS

Known-good diagnostic path:

```text
BOTW AX voice
-> existing TV mix preserved
-> selected voice receives DRC0 stereo main-bus route
-> Cemu GamePad PCM
-> Windows DualSense USB audio endpoint
-> DualSense internal speaker
```

Physically confirmed weapon-swing tracks:

- `Spear_Swing1`
- `Spear_Swing2`
- `Spear_SwingFast1`
- `Spear_SwingFast2`
- `LSword_Swing1`
- `LSword_Swing3`
- `LSword_Swing5`

Diagnostic implementation: `tools/botw_speaker_duplicate_patch.py`

CI run `35078312616` — SUCCESS.

The diagnostic hook adds DRC only when no DRC route already exists and leaves TV routing untouched.

### Native DualSense USB speaker route initialization: PASS / CLOSED

Separate validation branch:

`exp/dualsense-gamepad-core-arm64`

Validated implementation commit:

`638d19309f94acde70e9a0496c5a3bbe3027c25d`

CI run `35084659609` — SUCCESS.

Proven call:

```cpp
settings->DualSenseSettings(
    0,   // mic state
    0,   // headset disabled
    1,   // internal speaker enabled
    0,   // mic volume
    180, // audio volume
    255, // preserve Gamepad-Core native DualSense output mode
    0,   // rumble reduction
    0);  // trigger reduction
gamepad->UpdateOutput();
```

Important: the standalone Haptic Lab clears rumble/trigger state only for test isolation. Production Cemu integration must NOT copy those clearing calls. It should only initialize speaker route/volume and preserve all other controller output state.

DSX is not required in the target design.

## Final user-facing architecture — agreed

### Cemu UI

Cemu exposes exactly one global checkbox:

`Enhanced Sound Experience`

Meaning:

- OFF = stock/native Cemu behavior;
- ON = enhanced-sound capability is armed/ready;
- the checkbox does NOT choose sound categories;
- there are no Cemu-side checkboxes for weapon, hit, voice, etc.

The setting should live on the Audio page and persist in Cemu config.

### Native Wii U GamePad / DRC audio must be preserved

Some Wii U games already author separate TV and GamePad audio. That behavior is authoritative and must continue to work.

Example:

```text
BOTW native Sheikah Slate sound -> DRC already authored -> unchanged
BOTW weapon swing -> TV only normally
Enhanced Sound pack -> add DRC to selected weapon swing -> TV + DRC
```

Enhanced Sound is additive. It must not globally reinterpret or replace native DRC routing.

### Responsibility split

Cemu core is generic infrastructure only.

Game-specific sound selection belongs to a Graphic Pack / data policy.

```text
Cemu:
  Enhanced Sound enabled?
  -> expose generic sound-routing policy engine
  -> preserve existing TV/DRC routing
  -> duplicate only when active game policy requests it

Graphic Pack:
  game-specific semantic/resource/track rules
  -> destination/policy for selected sounds
```

Do NOT grow a BOTW exact-name whitelist inside C++.

Preferred match order:

```text
semantic event/category
> resource/path/category/prefix
> exact track fallback
```

Exact track names are acceptable as a narrow data-driven fallback or regression rule, but not as hundreds of hardcoded C++ comparisons.

## Proposed code-level hook

The inspected GraphicPack2 path is suitable for a generic extension.

Recommended production shape:

1. extend `GraphicPack2` with an Enhanced Sound rule structure;
2. parse one or more game-owned sound-routing sections from `rules.txt` during graphic-pack activation;
3. provide a static resolver over active packs, e.g. optional semantic identity + source path + track name -> routing policy;
4. call the resolver from the existing AX voice start/routing point;
5. if policy requests controller duplication and the voice has no existing DRC route, add DRC0 stereo main bus;
6. never remove or rewrite the existing TV route;
7. if the game already authored DRC for that voice, leave it unchanged.

The known-good DRC duplicate code in `tools/botw_speaker_duplicate_patch.py` is the reference for the actual AX device-mix operation, but the proof whitelist must not be copied into production C++.

## Config/UI paths already inspected

Relevant config fields are in:

- `src/config/CemuConfig.h`
- `src/config/CemuConfig.cpp`

Audio UI is in:

- `src/gui/wxgui/GeneralSettings2.h`
- `src/gui/wxgui/GeneralSettings2.cpp`

Add one persisted boolean such as `enhanced_sound_experience`, default false.

Do not silently overwrite the user's existing GamePad audio volume/device settings merely because the checkbox is enabled. Native DRC audio compatibility is the reason the feature is opt-in.

## DualSense production initialization direction

When Enhanced Sound Experience is enabled, Cemu should run a small native DualSense USB speaker-route service using the already pinned `dependencies/Gamepad-Core` revision.

Target behavior:

```text
Enhanced Sound OFF
-> no special DualSense speaker HID initialization

Enhanced Sound ON
-> detect DualSense / DualSense Edge USB
-> on new connection or reconnect only
-> send proven speaker route/volume settings
-> UpdateOutput()
-> preserve rumble, trigger and other output state
```

Do not require a final manual `Enable speaker` button.

The existing Cemu GamePad PCM path remains the actual audio transport; Gamepad-Core is only needed to initialize the controller's speaker route/volume.

## Important unresolved coverage issue: packed PlayerVoice

Current tracer v3 can fingerprint direct `.bars` reads, but BOTW `PlayerVoice.bars` lives inside `TitleBG.pack`.

Required provenance chain:

```text
TitleBG.pack
-> SARC
-> Sound/Resource/PlayerVoice.bars
-> BARS
-> embedded BFWAV / PVxxx_xx
-> runtime AX voice
```

Therefore PlayerVoice coverage still needs packed-resource tracer v4 (`SARC -> embedded BARS`).

This is NOT required to prove the generic framework with the already-confirmed weapon-swing tracks, but it IS required before claiming broad PlayerVoice support is complete.

Do not omit this stage.

## Suggested implementation staging

Stage A — generic Enhanced Sound framework:

- add persisted checkbox;
- add generic GraphicPack2 routing-policy parser/resolver;
- replace diagnostic C++ whitelist with generic policy lookup;
- keep TV untouched and preserve existing DRC;
- create a BOTW policy using already physically confirmed weapon-swing rules;
- integrate native DualSense USB speaker init/reconnect behavior without rumble/trigger clearing.

Stage B — build/physical regression:

- native Windows ARM64 Cemu build;
- verify OFF = stock behavior;
- verify ON + BOTW pack = known weapon swing still reaches controller speaker;
- verify native authored DRC sound remains intact;
- verify reconnect reinitializes speaker route without DSX.

Stage C — PlayerVoice expansion:

- finish SARC -> embedded BARS tracer v4;
- recover `TitleBG.pack::Sound/Resource/PlayerVoice.bars` runtime provenance;
- correlate semantic SLink/GameROMPlayer identity where possible;
- extend BOTW policy using semantic/resource categories first, exact tracks only as fallback.

## Closed / do not retest without regression

- BOTW weapon-swing -> DRC/DualSense narrow physical proof
- CI run `35078312616`
- native DualSense USB speaker route/volume physical proof
- CI run `35084659609`
- DSX requirement for target design
- diagnostic speaker-enable button as a final UX requirement

## Workstream boundary

TOTK/Switch BNVIB / 46-pattern Haptic Explorer work is handled in another tab. Do not mix that implementation into this Enhanced Sound branch.

See also:

- `NEXT_ACTION.md`
- `HANDOFF_PROMPT.md`
- `docs/BOTW_DUALSENSE_SPEAKER_DUPLICATE.md`
- `docs/BOTW_SOUND_SOURCE_TRACER_FINDINGS.md`
- `docs/BOTW_PLAYERVOICE_TRACK_LIST.md`
- `docs/DUALSENSE_NATIVE_SPEAKER_INIT_VALIDATION.md`
