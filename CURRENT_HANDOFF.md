# CURRENT HANDOFF — [Test] SE / DualSense Haptics + Adaptive Trigger Redesign

Canonical policy:
- `BRANCH_POLICY.md`
- `ACTIVE_BRANCH_ROLES.md`

GitHub is the only source of truth. Fetch actual HEADs before any write/build.

## Five active source-of-truth roles

- [Release] `final-adreno-compat-arm64`
- [Diagnostics] `fix/arm64-diagnostics-ui-artifact-gate`
- [Release+SE] `Release+SE`
- [Diagnostics+SE] `feat/enhanced-sound-experience-v1`
- [Test] `test/se-fingerprint-index-v1`

This branch is the current SE / DualSense haptic / adaptive-trigger laboratory.

Historical `test-haptic`, `Final+SE`, and `runtime-experiments-arm64` are reference/archive only unless the user explicitly reactivates them.

## Current Test baseline

Code HEAD that produced the latest validated build:
`63172d8a28e773cabbf14220e440823bd441a428`

Successful build:
- run: `35443550198`
- workflow: `[Test] Cemu ARM64 SE + GraphicPack Haptics + Bow Trigger`
- result: SUCCESS

Documentation commits may advance the branch after that code HEAD. Always fetch the actual branch HEAD before work.

## Runtime result — BOTW bow prototype

User runtime validation:

PASS:
- bow-specific adaptive-trigger tension works;
- changing between bows with different BaseAttack values produces different R2 resistance;
- the existing strength calculation and DualSense output path are proven on real hardware.

LIMITATION:
- aiming while moving is not reliably captured by the current implementation.

Do not treat the current sound-triggered lifecycle as final.

## Current prototype architecture

The present implementation is intentionally a prototype.

Current flow:

`GraphicPack sound_routes.ini`
-> sound route match
-> `adaptive_trigger = botw_bow` / `stop`
-> `EnhancedSoundDualSenseService`
-> `BotwBowAdaptiveTrigger.h`
-> BOTW guest-memory read
-> bow actor/BaseAttack resolution
-> DualSense R2 effect

BOTW-specific source currently exists in:
`src/Cafe/OS/common/BotwBowAdaptiveTrigger.h`

It contains BOTW v208-specific addresses, pouch-list traversal, actor IDs, and the bow/BaseAttack table.

This must NOT become the pattern for adding games.

## Architectural decision

The adaptive-trigger feature is being redesigned before further expansion.

Required final separation:

- Cemu core = generic adaptive-trigger/state engine only.
- GraphicPack = game-specific state detection/configuration.
- A new game must not require adding game-specific addresses, actor IDs, weapon tables, or title logic to Cemu source.
- Persistent trigger state should follow relevant game-state changes such as equipped-item changes, not depend on a sound cue being emitted.
- Audio routing / BNVIB haptic routing / adaptive-trigger state detection must remain separable.

Do NOT add BOTW polling to `EnhancedSoundDualSenseService` as the final solution.
Do NOT add more `Botw*` cases to the core.
Do NOT solve moving-aim by simply adding more sound cues.

The exact generic GraphicPack interface is not yet approved.

## Next design task

Before coding, compare the smallest reusable designs for exposing game state from a GraphicPack to Cemu:

1. declarative guest-memory watch/state rules;
2. GraphicPack game-side patch/hook that exposes a simple value/event to a generic Cemu interface.

Prefer the simplest design that handles BOTW cleanly without turning Cemu into a generic game-structure interpreter.

The user must approve the architecture before implementation/build work resumes.

## Preserve

Do not regress:
- indexed fingerprint lookup already promoted to Release+SE;
- existing Enhanced Sound routing;
- current BNVIB GraphicPack haptics;
- DualSense audio/headset behavior;
- Release+SE CPU/Vulkan behavior.

Do not delete the current BOTW bow prototype until the generic replacement is built and runtime-validated.

Detailed prototype history:
`DEBUG_HISTORY_20260919_BOTW_BOW_ADAPTIVE_TRIGGER_PROTOTYPE.md`
