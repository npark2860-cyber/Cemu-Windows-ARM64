# HANDOFF PROMPT — Cemu ARM64 / Enhanced Sound Experience

Continue the Enhanced Sound Experience implementation from GitHub source of truth.

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

Active implementation branch:
`feat/enhanced-sound-experience-v1`

At the start of the new tab:

1. read `CURRENT_HANDOFF.md`;
2. read `NEXT_ACTION.md`;
3. read `docs/BOTW_DUALSENSE_SPEAKER_DUPLICATE.md` and `docs/DUALSENSE_NATIVE_SPEAKER_INIT_VALIDATION.md`;
4. query the actual `feat/enhanced-sound-experience-v1` HEAD before editing;
5. treat GitHub branch/HEAD/source/workflow as source of truth;
6. do not touch `main`;
7. do not rerun already PASS/CLOSED experiments without a real regression.

## Agreed final architecture

Cemu has exactly one global Audio-page checkbox:

`Enhanced Sound Experience`

Its meaning is readiness/capability only.

```text
OFF -> stock Cemu behavior
ON  -> Enhanced Sound infrastructure armed
```

It is NOT a weapon/hit/voice category selector.

Game-specific sound selection belongs to a Graphic Pack/data policy, not emulator-core BOTW hardcoding.

Native Wii U DRC/GamePad audio must remain authoritative and unchanged. Enhanced rules are additive only.

Example:

```text
native Sheikah Slate sound already on DRC -> unchanged
weapon swing normally TV-only
BOTW Enhanced Sound policy -> add DRC -> TV + DRC
```

## Already physically PASS

### BOTW weapon-swing duplicate proof

Known BOTW weapon swing voices were successfully duplicated to DRC0 while TV routing remained intact, and were physically heard from the DualSense internal speaker.

CI run `35078312616` — SUCCESS.

Do not copy the diagnostic C++ exact-name whitelist into production architecture.

### Native DualSense USB speaker initialization

Validated on `exp/dualsense-gamepad-core-arm64` at commit:

`638d19309f94acde70e9a0496c5a3bbe3027c25d`

CI run `35084659609` — SUCCESS.

Native `Gamepad-Core -> DualSenseSettings(...) -> UpdateOutput()` enables the DualSense USB internal speaker route without DSX.

In production, initialize on connection/reconnection only while Enhanced Sound is enabled. Do NOT clear rumble or trigger state; the validation tool did that only for test isolation.

## Immediate implementation target

Implement Stage A on `feat/enhanced-sound-experience-v1`:

1. persisted `Enhanced Sound Experience` boolean in `CemuConfig` + Audio UI;
2. generic `GraphicPack2` Enhanced Sound policy parser/resolver;
3. AX hook calls the generic resolver and only adds DRC when requested;
4. TV route is never removed;
5. existing authored DRC is never overwritten;
6. first BOTW Graphic Pack policy contains only already physically confirmed weapon-swing regression rules;
7. integrate the already-proven DualSense USB speaker route init/reconnect service.

Preferred rule identity order:

```text
semantic event/category
> resource/path/category/prefix
> exact track fallback
```

Exact names may exist in Graphic Pack data as a narrow fallback, but not as expanding C++ BOTW lists.

## Important incomplete coverage

BOTW `PlayerVoice.bars` is embedded in `TitleBG.pack`, so the current direct-BARS tracer is insufficient for broad PlayerVoice support.

Required follow-up after Stage A framework works:

```text
TitleBG.pack -> SARC -> embedded PlayerVoice.bars -> BFWAV/PVxxx_xx -> runtime AX voice
```

Finish packed-resource tracer v4 and correlate `SLink/GameROMPlayer` semantics where possible before claiming PlayerVoice support is complete.

Do not let this block the first generic framework regression using already-confirmed weapon-swing voices, but do not forget it.

## Workstream boundary

Do not mix TOTK/Switch BNVIB / 46-pattern Haptic Explorer work into this branch. That is handled separately.
