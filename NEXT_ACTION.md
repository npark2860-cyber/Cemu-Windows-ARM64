# NEXT_ACTION — [Test] DualSense Haptics

Work only on:
`test/se-fingerprint-index-v1`

## Goal

Use the current Release+SE-derived Test branch for BOTW DualSense haptic experiments while preserving the promoted fingerprint lookup optimization.

## First haptic work

Reuse/port the existing haptic engine work from historical branch `test-haptic` only after comparing it against the current Test baseline. Do not merge the historical branch wholesale.

Exact sample mappings are fixed:

- UI tab change = `UIFadeIn.bnvib`
- UI cursor movement = `UiRollOver.bnvib`
- elevator/lift = `PresetDohoon.bnvib`
- invalid/unavailable action = `PresetPiton.bnvib`

Also implement/test Master Cycle / motorbike vibration.

## Rules

1. Fetch actual Test and Release+SE HEADs first.
2. Read `BRANCH_POLICY.md` and `ACTIVE_BRANCH_ROLES.md`.
3. Preserve the indexed fingerprint lookup.
4. Do not touch CPU/Vulkan for this task.
5. Add/test haptic behavior on Test only.
6. Prefer one experimental variable at a time.
7. Check active/queued workflows once.
8. Trigger one test build only.
9. Do not promote to Release+SE until the user runtime-validates and explicitly requests promotion.

## Do not redo

- Do not re-investigate the discarded TV-mute workaround unless new evidence appears.
- Do not replace the fingerprint bucket with a single-entry hash mapping.
- Do not use `test-haptic` as source of truth.
- Do not switch back to the obsolete three-branch policy.
