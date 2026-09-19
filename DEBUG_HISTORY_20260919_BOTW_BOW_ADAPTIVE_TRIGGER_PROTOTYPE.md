# DEBUG_HISTORY_20260919_BOTW_BOW_ADAPTIVE_TRIGGER_PROTOTYPE

## Scope

This document records the first BOTW bow adaptive-trigger prototype on the Test branch and the architectural decision made after runtime testing.

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

Branch:
`test/se-fingerprint-index-v1`

GitHub is the only source of truth. Always fetch the actual branch HEAD before new work.

## Prototype implementation

Initial adaptive-trigger implementation commit:
`0b4010d8d84ff0f1454230897fc9b88719edf83a`

Compile-fix commit:
`63172d8a28e773cabbf14220e440823bd441a428`

Successful build:
- workflow: `[Test] Cemu ARM64 SE + GraphicPack Haptics + Bow Trigger`
- run: `35443550198`
- result: SUCCESS
- built HEAD: `63172d8a28e773cabbf14220e440823bd441a428`

The preceding run `35439630568` failed because adaptive-trigger fields were accidentally duplicated in `RouteRule` and omitted from `RouteMatch` in `EnhancedSoundRouter.h`. The fix only corrected those declarations.

## Current prototype flow

The prototype is sound-route driven:

`GraphicPack sound_routes.ini`
-> `GraphicPack2::LoadEnhancedSoundRoutes()`
-> `EnhancedSoundRouter`
-> AX voice route match in `ax_voice.cpp`
-> `EnhancedSoundDualSenseService::ApplyBotwBowTrigger()`
-> `BotwBowAdaptiveTrigger::ResolveEquippedBow()`
-> DualSense right adaptive trigger

Current GraphicPack parser supports:
- `adaptive_trigger = botw_bow`
- `adaptive_trigger = stop`
- `trigger_min`
- `trigger_max`
- `trigger_start_zone`

## BOTW-specific prototype code

`src/Cafe/OS/common/BotwBowAdaptiveTrigger.h` currently contains game-specific logic.

It:
- restricts itself to BOTW title IDs and v208;
- reads `PauseMenuDataMgr` from guest address `0x10469978`;
- walks the pouch item list;
- finds an equipped item with pouch type Bow;
- reads its `Weapon_Bow_xxx` actor ID;
- contains a 26-entry bow/BaseAttack table;
- maps BaseAttack into the configured adaptive-trigger strength range.

This code proved the concept but is NOT the intended final architecture.

## Runtime validation reported by user

PASS:
- different bows produce different trigger tensions;
- the bow-dependent strength calculation/output path works on real hardware.

Observed limitation:
- aiming while moving is not reliably captured by the current prototype.

The exact missed sound/cue path was not independently proven. The important architectural finding is that adaptive-trigger state is currently activated from sound-route events, so the trigger lifecycle is coupled to audio events instead of the equipped-item state.

## Architecture decision

Do NOT extend the prototype by adding more BOTW-specific checks, more BOTW sound cues, or game-specific polling in Cemu core.

The final direction must be:

- Cemu core provides a generic adaptive-trigger/state mechanism.
- GraphicPack owns game-specific state detection/configuration.
- Adding another game must not require adding that game's addresses, actor names, weapon tables, or rules to Cemu source.
- Trigger configuration should follow persistent game state/change (for example equipped-item change), not depend on a draw/release sound being emitted.
- Audio routing/haptic cue routing and adaptive-trigger state detection should remain separable.

The precise generic GraphicPack interface is NOT yet finalized.

## Required redesign question

Before modifying source again, compare the simplest ways for a GraphicPack to expose game state to a generic Cemu adaptive-trigger engine.

At minimum evaluate:
1. direct declarative guest-memory watch/state rules;
2. GraphicPack game-side patch/hook that writes a simple value/event to a generic watched location/interface.

Do not assume a complex generic linked-list interpreter is necessary. Prefer the smallest reusable interface that can represent BOTW cleanly and can also be used by other games.

## Preserve during redesign

Do not regress:
- Release+SE CPU/Vulkan behavior;
- indexed sound fingerprint optimization;
- existing Enhanced Sound routing;
- existing GraphicPack BNVIB haptic routing;
- DualSense headset/speaker routing behavior;
- already validated bow strength/output behavior as a reference.

Do not delete the current prototype until a generic replacement builds and is runtime-validated. Treat it as a working reference implementation, not as the final design.
