# CURRENT HANDOFF — [Test] SE / DualSense Haptics

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

This branch is the current SE/haptic laboratory.

Historical `test-haptic`, `Final+SE`, and `runtime-experiments-arm64` are reference/archive only unless the user explicitly reactivates them.

## Current code state

Validated test build/code HEAD:
`9263604feff7d92cbe517cd75246ac97d15d853d`

Run:
`35425264365`

Result:
SUCCESS

Artifact:
`cemu-arm64-test-se-fingerprint-index-v1`

After that SUCCESS, only handoff/policy documentation commits were added. Fetch the actual current branch HEAD before work.

## Fingerprint optimization

The test branch contains the indexed fingerprint lookup now promoted to Release+SE.

Release+SE implementation promotion commit:
`f2a5ad15b191d30eb2c870db7626518628cd90a2`

The implementation preserves existing matching semantics while avoiding a full scan of up to 32,768 entries on every lookup.

Do not remove/regress this optimization during haptic work.

## Current next work

DualSense haptic experiments.

User-approved exact mappings:
- UI tab change -> `UIFadeIn.bnvib`
- UI cursor movement -> `UiRollOver.bnvib`
- elevator/lift -> `PresetDohoon.bnvib`
- invalid/unavailable action -> `PresetPiton.bnvib`

Also planned:
- Master Cycle / motorbike vibration

The old `test-haptic` branch contains prior haptic engine/smoke work and may be consulted as historical reference, but do not fast-forward/merge it wholesale. Port only reviewed haptic pieces into this current Test branch.

## Important resolved issue

A temporary workaround that called `g_tvAudio->Play()` after DualSense route changes was reverted. The user determined there was no real global TV mute problem.

Do not re-add that workaround without new evidence.

## Build discipline

- check active/queued once;
- one build only;
- no automatic reruns;
- no repeated polling;
- preserve Release+SE CPU/Vulkan behavior;
- haptic work stays on Test until runtime-validated and explicitly approved for promotion.
