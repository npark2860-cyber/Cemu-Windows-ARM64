# HANDOFF_PROMPT

Continue the Cemu ARM64 Enhanced Sound / DualSense haptic work from GitHub.

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

GitHub is the only source of truth. Do not infer current state from conversation memory.

Read these files first from branch `test/se-fingerprint-index-v1`:
1. `CURRENT_HANDOFF.md`
2. `NEXT_ACTION.md`
3. `DEBUG_HISTORY_20260919_SE_FINGERPRINT_INDEX.md`

Then verify the actual current HEADs of:
- `Release+SE`
- `test/se-fingerprint-index-v1`
- `final-adreno-compat-arm64` only as the base-release reference

Expected handoff state:
- Release+SE: `f2a5ad15b191d30eb2c870db7626518628cd90a2`
- Test: `9263604feff7d92cbe517cd75246ac97d15d853d`
- Base release reference: `d359c53da77dddac6c34554d3b894099896b070e`

If actual Git differs, actual Git wins and report the mismatch before changing anything.

Important workstream rule:
The user explicitly chose `Release+SE` as the SE production source and `test/se-fingerprint-index-v1` as the branch to keep for haptic experiments. This is a current user-directed exception to the older three-branch text in `BRANCH_POLICY.md`. Do not silently redirect this SE workstream to older branch roles.

The fingerprint lookup optimization has already been promoted to Release+SE. Preserve it.

Next work is HAPTIC TESTING ON THE TEST BRANCH ONLY.

Exact mappings:
- UI tab change = `UIFadeIn.bnvib`
- UI cursor movement = `UiRollOver.bnvib`
- elevator/lift = `PresetDohoon.bnvib`
- invalid/unavailable action = `PresetPiton.bnvib`

Also keep the goal of motorbike vibration.

Do not touch CPU/Vulkan sources for this task.
Do not promote haptic experiments until the user runtime-verifies them and explicitly requests promotion.
Before building, check active/queued once and run only one build.
