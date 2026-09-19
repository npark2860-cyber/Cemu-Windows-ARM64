# NEXT_ACTION — Generic GraphicPack Adaptive Trigger Redesign

Work only on:
`test/se-fingerprint-index-v1`

GitHub is the only source of truth.

## Current validated reference

Latest validated code build:
- code HEAD: `63172d8a28e773cabbf14220e440823bd441a428`
- run: `35443550198`
- result: SUCCESS

User runtime result:
- bow-specific tension: PASS
- moving-aim capture: incomplete/unreliable

The current BOTW implementation is a working prototype, not the final architecture.

## Immediate next action: DESIGN FIRST

Do not modify source immediately.

First inspect the current implementation and propose a minimal generic architecture that satisfies all of these requirements:

1. Cemu core must not contain BOTW-specific addresses, actor IDs, weapon tables, or title-specific adaptive-trigger logic.
2. Game-specific information must live in the GraphicPack side.
3. Adding another game must not require rebuilding Cemu with new game-specific source.
4. Adaptive-trigger state must be able to persist across normal gameplay and update on relevant game-state changes such as weapon/item changes.
5. Sound events may still be used for sound/haptic cues, but must not be the only lifecycle source for persistent trigger state.
6. Existing generic DualSense trigger output code should be reused where possible.
7. Prefer a small reusable interface over a large generic memory-structure language.

## Designs to compare

At minimum compare:

- Direct GraphicPack declarative memory/state watch.
- GraphicPack PPC patch/hook -> simple generic state/value handoff -> Cemu adaptive-trigger engine.

For BOTW, remember the current prototype obtains the equipped bow by walking a game-specific pouch linked list. Do not blindly move that traversal into a generic Cemu polling loop. Determine whether the GraphicPack can expose a simpler stable state at the moment the game changes the equipped item.

The first response in the next work session should explain the proposed architecture and exact responsibilities of Cemu vs GraphicPack. Get user approval before coding.

## Existing prototype to use as reference

Relevant files:
- `src/Cafe/OS/common/BotwBowAdaptiveTrigger.h`
- `src/Cafe/OS/common/EnhancedSoundDualSenseService.h`
- `src/Cafe/OS/common/EnhancedSoundRouter.h`
- `src/Cafe/OS/libs/snd_core/ax_voice.cpp`
- `src/Cafe/GraphicPack/GraphicPack2.cpp`

Current parser recognizes:
- `adaptive_trigger = botw_bow`
- `adaptive_trigger = stop`
- `trigger_min`
- `trigger_max`
- `trigger_start_zone`

These names are prototype API and may be replaced by the redesign.

## Do not redo

- Do not rerun the already successful `35443550198` just to confirm it.
- Do not add more BOTW-specific polling or cue matching as a workaround.
- Do not add per-game branches/cases to Cemu core.
- Do not delete the working prototype before the replacement is proven.
- Do not touch CPU/Vulkan for this task.
- Do not regress fingerprint indexing, SE audio, BNVIB haptics, or DualSense jack routing.

## Build discipline after architecture approval

- fetch actual Test HEAD;
- check active/queued workflows once;
- one experimental variable at a time;
- one build only;
- no automatic polling/rebuild;
- runtime validation by user before any promotion.
