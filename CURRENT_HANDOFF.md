# CURRENT HANDOFF — Test_SE generic voice haptics

## Source and scope

- Source branch: `test_SE`.
- Verified upstream baseline: `7c5bb3fdce5d23f1349a421bb465d9db8db215d9`.
- Development/PR branch: `codex/generic-voice-haptics`.
- `build/test-se-once` is a historical build carrier, not the source branch.
- The user authorized binary changes only for reusable, game-independent haptic functionality.

## Change

Voice-bound BNVIB playback now follows voice completion/free/reset, supports concurrent effects, and optionally follows the synchronized TV sends/envelope with `haptic_follow_tv=true`. Missing AX updates mute output after 100 ms. Source recognition and SE lookup optimizations are retained; no BOTW addresses, actor state or distance formulas were added to Cemu.

See [design, limitations and test checklist](docs/GENERIC_VOICE_HAPTICS.md) and the [optional Master Cycle test pack](enhanced_sound_policies/BreathOfTheWild/DualSenseExperienceUnified/README.md).

## Validation

- Native ARM64 MSVC C++20 haptic mixer/route tests: PASS.
- Existing Enhanced Sound lookup/range/catalog tests: PASS (pre-existing signedness warning in EnhancedSoundPackedBars.h).
- Full Cemu build: not performed; standalone tests do not compile the full AX/GraphicPack/backend integration.
- DualSense/gameplay regression, distance and despawn tests on this revision: pending.
- No claim that the reported motorcycle issues are hardware-verified fixed.

## Next step

Build this experimental revision through a verified Test workflow/carrier, then follow the acceptance checklist. The inherited workflow on `test_SE` still guards the stock Release branch; this change does not dispatch it or modify that guard. Do not promote to Release+SE until user runtime verification and explicit promotion approval.

The raw adaptive-trigger bridge and sequence/revision behavior remain unchanged. Existing local SE and Bow work is separate from this PR.
