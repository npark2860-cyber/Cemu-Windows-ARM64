# HANDOFF_PROMPT

Continue the Cemu Windows ARM64 Enhanced Sound / DualSense haptic project.

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

GitHub is the only source of truth. Do not infer live state from conversation memory.

Start on:
`test/se-fingerprint-index-v1`

Read, in this order:
1. `BRANCH_POLICY.md`
2. `ACTIVE_BRANCH_ROLES.md`
3. `CURRENT_HANDOFF.md`
4. `NEXT_ACTION.md`
5. `DEBUG_HISTORY_20260919_SE_FINGERPRINT_INDEX.md`

Then fetch actual HEADs for all five active source-of-truth branches:
- `final-adreno-compat-arm64`
- `fix/arm64-diagnostics-ui-artifact-gate`
- `Release+SE`
- `feat/enhanced-sound-experience-v1`
- `test/se-fingerprint-index-v1`

If documents and Git differ, actual Git wins and report the mismatch before changing source.

The indexed fingerprint lookup is already promoted to Release+SE and must be preserved.

Next work is haptic testing on Test only.

Exact mappings:
- UI tab change = `UIFadeIn.bnvib`
- UI cursor movement = `UiRollOver.bnvib`
- elevator/lift = `PresetDohoon.bnvib`
- invalid/unavailable action = `PresetPiton.bnvib`

Also keep the Master Cycle / motorbike vibration target.

Historical `test-haptic` may be inspected for reusable haptic engine code but is not source of truth. Do not merge it wholesale.

Do not touch CPU/Vulkan for this haptic task.
Before a build, inspect active/queued once and trigger only one build.
Do not promote any haptic experiment until user runtime validation plus explicit promotion approval.
