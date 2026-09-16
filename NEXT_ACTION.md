# NEXT ACTION — Enhanced Sound Experience v1

## Do not repeat completed proofs

Already PASS/CLOSED unless a regression appears:

- BOTW known weapon-swing AX voice -> DRC0 -> DualSense speaker physical proof;
- CI run `35078312616`;
- native DualSense USB speaker route/volume initialization without DSX;
- CI run `35084659609`;
- diagnostic manual Enable Speaker button as a final UX requirement.

## Active branch

`feat/enhanced-sound-experience-v1`

Query actual HEAD before editing. Do not touch `main`.

## Immediate implementation order

### 1. Add the global Cemu readiness switch

Add one persisted boolean on the Audio page:

`Enhanced Sound Experience`

Semantics:

- OFF = stock Cemu behavior;
- ON = Enhanced Sound infrastructure is armed;
- no per-category Cemu controls.

Do not automatically replace the user's existing GamePad audio device or volume settings just because the checkbox is enabled.

### 2. Build the generic Graphic Pack sound-routing layer

Extend `GraphicPack2` with a data-driven Enhanced Sound policy.

Core must stay game-agnostic.

Resolver inputs should be able to accept, in priority order:

```text
semantic event/category (when available)
resource/source path or category/prefix
track name fallback
```

Policy output should at minimum support:

```text
no change
duplicate to DRC/controller while preserving TV
```

The first implementation should preserve room for destination/gain metadata without forcing BOTW semantics into C++.

### 3. Replace the diagnostic whitelist with the generic resolver

Use the existing physically proven AX hook location and device-mix operation as reference.

Rules:

- never remove existing TV routing;
- if the game already authored DRC for the voice, preserve it and do not overwrite it;
- only add DRC0 stereo main-bus routing when the active Graphic Pack policy requests duplication;
- do not add more BOTW exact-name comparisons to C++.

Create a BOTW Enhanced Sound Graphic Pack policy containing the already-confirmed weapon-swing rules as the first regression set.

### 4. Integrate native DualSense speaker initialization

Use pinned `dependencies/Gamepad-Core` and the already validated `DualSenseSettings(...)` call.

When Enhanced Sound is ON:

```text
DualSense/DualSense Edge USB connects or reconnects
-> initialize internal speaker route + volume once
-> UpdateOutput()
```

Production integration must NOT clear rumble or adaptive-trigger state. Those calls existed only in the standalone validation tool for test isolation.

### 5. Build and validate once after the new implementation exists

Use a dedicated Windows ARM64 workflow for the new branch/change. Do not rerun old PASS workflows just to reconfirm them.

Physical checks after the new build:

- checkbox OFF: stock/native behavior;
- checkbox ON + BOTW Enhanced Sound pack: known spear/two-handed swing reaches DualSense speaker;
- TV route remains;
- an already-native DRC/GamePad sound remains intact;
- USB reconnect reinitializes speaker route without DSX;
- no unintended ambience/world sounds appear on the controller.

## PlayerVoice coverage — required follow-up, not optional for broad support

Current v3 tracer does not fully cover `PlayerVoice.bars` because it is embedded inside `TitleBG.pack`.

After Stage A framework passes, continue packed-resource tracer v4:

```text
TitleBG.pack
-> SARC
-> Sound/Resource/PlayerVoice.bars
-> BARS/BFWAV/PVxxx_xx
-> runtime AX voice
```

Then correlate with `SLink/GameROMPlayer` semantic events/categories where possible and expand the BOTW policy using semantic/resource rules before exact-name fallbacks.

Do not claim broad PlayerVoice support before this provenance path is proven.

## Workstream boundary

Do not mix TOTK/Switch BNVIB or the 46-pattern Haptic Explorer into this branch. That is a separate workstream.
