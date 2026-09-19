# HANDOFF_PROMPT

Continue the Cemu Windows ARM64 Enhanced Sound / DualSense project.

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

GitHub is the only source of truth. Do not infer live Git state from conversation memory.

Start on:
`test/se-fingerprint-index-v1`

Read, in this order:
1. `BRANCH_POLICY.md`
2. `ACTIVE_BRANCH_ROLES.md`
3. `CURRENT_HANDOFF.md`
4. `NEXT_ACTION.md`
5. `DEBUG_HISTORY_20260919_SE_FINGERPRINT_INDEX.md`
6. `DEBUG_HISTORY_20260919_BOTW_BOW_ADAPTIVE_TRIGGER_PROTOTYPE.md`

Then fetch the actual current HEADs for the active source-of-truth branches. If Git and docs differ, Git wins and report the mismatch before source changes.

## Current adaptive-trigger reference state

The latest validated bow-trigger code build was:
- HEAD `63172d8a28e773cabbf14220e440823bd441a428`
- run `35443550198`
- SUCCESS

User runtime validation established:
- bow-specific R2 tension differences work correctly;
- moving while aiming is not reliably captured.

The existing BOTW bow implementation is a PROTOTYPE.

It currently couples adaptive-trigger activation to GraphicPack sound-route events and contains BOTW-specific guest-memory traversal / bow data in Cemu source.

## New architectural requirement

Do not continue by adding more BOTW-specific code.

Final target:

`Cemu core = generic state/adaptive-trigger mechanism`
`GraphicPack = all game-specific state detection and mapping`

Adding another game must not require hardcoding that game's memory addresses, actor IDs, weapon tables, or title-specific trigger logic into Cemu.

The trigger should be able to change when the relevant game state changes, such as equipped-item change, and then remain configured until that state changes again. Do not rely on Bow_Draw/Bow_Release sound cues as the persistent trigger lifecycle.

## FIRST TASK — no coding yet

Inspect the current prototype and existing GraphicPack capabilities, then present the user with the simplest viable generic design.

Compare at least:
1. direct declarative guest-memory/state watch in GraphicPack;
2. GraphicPack PPC patch/hook that exposes a simple state/value/event to a generic Cemu interface.

BOTW currently requires a game-specific pouch linked-list walk to discover the equipped bow. Avoid solving this by building a huge generic linked-list interpreter unless it is actually the simplest reusable solution.

Favor reuse and minimum moving parts.

Get the user's approval on the architecture before modifying code or starting a build.

## Preserve

Do not regress:
- Release+SE CPU/Vulkan behavior;
- indexed fingerprint lookup;
- Enhanced Sound routing;
- BNVIB GraphicPack haptics;
- DualSense audio/headset routing;
- the already proven variable bow-tension output path.

Do not delete the working prototype until a generic replacement has built and passed user runtime validation.

After architecture approval, work on Test only. Before a build, check active/queued once and trigger one build only. Do not automatically poll or rerun.
