# HANDOFF PROMPT — Cemu ARM64 / BOTW DualSense Audio

Continue the BOTW DualSense audio-routing work from GitHub source of truth.

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

Audio proof branch:
`diag/botw-dualsense-speaker-duplicate`

At the start of the new chat/tab:

1. read `CURRENT_HANDOFF.md`
2. read `NEXT_ACTION.md`
3. read `docs/BOTW_DUALSENSE_SPEAKER_DUPLICATE.md`
4. query actual branch HEADs before editing
5. also inspect `diag/botw-sound-source-tracer` before continuing tracer v4
6. treat GitHub branch/HEAD/workflow/source as source of truth

Do not touch `main`.

Do not re-run or re-investigate CLOSED/PASS items without an actual regression.

## Already physically PASS

### BOTW speaker Duplicate proof

`resolved BOTW weapon-swing AX voice -> added DRC0 -> Cemu GamePad PCM -> DualSense USB speaker`

Workflow run `35078312616` succeeded.

The user physically heard the original BOTW weapon swing/whoosh clearly from the DualSense speaker and reported a dramatically different feel.

The proof currently uses a deliberately narrow exact-name whitelist. This whitelist is diagnostic only.

### Native DualSense speaker initialization

Separate branch:
`exp/dualsense-gamepad-core-arm64`

Validated implementation commit:
`638d19309f94acde70e9a0496c5a3bbe3027c25d`

Workflow run:
`35084659609` — PASS

Physical result: native speaker route/volume enable works without DSX.

Final design should initialize the speaker automatically on DualSense connect/reconnect. The diagnostic Enable Speaker button is not a final runtime requirement.

## Key architectural decision

Do NOT continue by hardcoding more individual sound names into C++.

The next problem is semantic identification, not output transport.

Preferred production identity order:

```text
SLink / GameROMPlayer semantic event or category
> source/resource/path category
> exact track-name fallback
```

A JSON/config mapping can hold routing policy and exceptions, but simply moving hundreds of exact track names from C++ into JSON is not considered a complete solution.

## Immediate next work

Continue packed PlayerVoice discovery:

```text
TitleBG.pack
-> SARC
-> Sound/Resource/PlayerVoice.bars
-> embedded BFWAV/PVxxx_xx
-> runtime AX voice
-> SLink/GameROMPlayer semantic correlation
```

Then design the generic semantic routing-policy layer:

```text
semantic sound identity
-> TV / DualSense / both
-> gain/policy
-> existing AX/DRC path
```

Do not mix the 46 TOTK BNVIB/Haptic Explorer implementation into this tab. That is a separate workstream.

If a simple TV-vs-controller A/B is useful, the code intentionally preserves TV routing; the user only reported that the controller-local swing perceptually dominates. This check is optional and must not block semantic work.
