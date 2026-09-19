# HANDOFF_PROMPT

Continue Cemu Windows ARM64 Enhanced Sound / DualSense work.

Repository: `npark2860-cyber/Cemu-Windows-ARM64`
Branch: `test/se-fingerprint-index-v1`
GitHub is the only source of truth. Do not create a branch.

Read BRANCH_POLICY.md, ACTIVE_BRANCH_ROLES.md, CURRENT_HANDOFF.md and NEXT_ACTION.md first.

Current architecture is Generic GraphicPack Adaptive Trigger:
- Cemu: generic frame callback + scalar trigger binding + DualSense output.
- GraphicPack: every game-specific address/state/table.
- API: `.callback frame <functionSymbol>`
- API: `.adaptiveTrigger <right|left> bow <stateSymbol> [startZone]`
- state 0 = off; 1..100 = tension percent.

BOTW implementation is in `enhanced_sound_policies/BreathOfTheWild/EnhancedSoundExperience/patch_AdaptiveTrigger.asm`.

Before CI, check active/queued once. One build only. No automatic polling/rerun.
Promotion requires user runtime PASS.
