# NEXT_ACTION — SE Haptic experiment

## Current task

Continue on:
`test/se-fingerprint-index-v1`

Do not modify `Release+SE` for haptic experiments until the user runtime-verifies a haptic change and explicitly requests promotion.

## First objective

Use the existing test branch as the haptic laboratory.

User's target:
- BOTW DualSense haptics
- motorbike vibration
- UI interaction haptics
- reuse the user's existing 46 Nintendo Switch TOTK `.bnvib` samples where appropriate

## Exact user-approved sample mappings

These mappings are authoritative. Do not reinterpret them.

- UI tab change -> `UIFadeIn.bnvib`
- UI cursor movement -> `UiRollOver.bnvib`
- elevator/lift -> `PresetDohoon.bnvib`
- invalid/unavailable action -> `PresetPiton.bnvib`

The user previously corrected a mapping mistake: tab change is specifically `UIFadeIn.bnvib`.

## Execution rules

1. Re-check actual test HEAD before any write.
2. Preserve the promoted fingerprint-index optimization.
3. Do not change CPU/Vulkan behavior.
4. Add one haptic behavior at a time where practical.
5. Keep haptic work isolated to the test branch.
6. Check active/queued workflow state once before build.
7. Trigger only one test build.
8. Wait for user runtime validation before calling a haptic experiment a FIX.
9. Do not promote haptic changes to Release+SE without explicit user approval.

## Release+SE status

Current Release+SE source HEAD at handoff:
`f2a5ad15b191d30eb2c870db7626518628cd90a2`

Fingerprint optimization is already promoted there, but no new Release+SE artifact has been built after that promotion.

## Do not redo

- Do not re-investigate the temporary TV-mute misunderstanding unless new evidence appears.
- Do not re-add `g_tvAudio->Play()` after DualSense routing.
- Do not redo the fingerprint linear-scan diagnosis from scratch.
- Do not replace the indexed lookup with a single-entry hash mapping; multiple candidates must remain supported.
