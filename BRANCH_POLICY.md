# Cemu Windows ARM64 / Adreno — Branch Policy

This document is the canonical branch-role and promotion policy for this repository.

GitHub is the only source of truth. Before every write, build, promotion, or artifact handoff, fetch the actual branch HEAD and inspect the actual source/workflow on that branch.

## Five active source-of-truth branches

There are exactly five active source-of-truth roles.

1. **[Release] `final-adreno-compat-arm64`**
   - Stock production/release baseline.
   - Verified ARM64/Adreno fixes and release features only.
   - No Enhanced Sound, CueCapture, haptic experiments, or diagnostic-only instrumentation.

2. **[Diagnostics] `fix/arm64-diagnostics-ui-artifact-gate`**
   - Diagnostic counterpart of the stock Release line.
   - Used for non-SE investigation/instrumentation.
   - Diagnostic-only UI/logging must never be promoted wholesale into Release.

3. **[Release+SE] `Release+SE`**
   - Production Enhanced Sound line.
   - Based on Release plus runtime-verified SE features.
   - This is the promotion target for verified SE and haptic features.
   - CPU/Vulkan behavior must remain aligned with the protected Release baseline unless the user explicitly requests otherwise.

4. **[Diagnostics+SE] `feat/enhanced-sound-experience-v1`**
   - Enhanced Sound diagnostic line.
   - Contains SE diagnostic tooling including CueCaptureV2.
   - Used to investigate route/fingerprint/cue issues that need instrumentation.
   - Diagnostic instrumentation must not be promoted wholesale into Release+SE.

5. **[Test] `test/se-fingerprint-index-v1`**
   - Current SE/haptic experiment line.
   - Based on Release+SE, not on the stock Diagnostics line.
   - Keep verified Release+SE behavior intact and change one experimental variable at a time.
   - Current next use: DualSense haptic experiments.

## Historical/reference branches

The following are not active source-of-truth branches unless the user explicitly reactivates them:

- `Final+SE`
- `test-haptic`
- `runtime-experiments-arm64`
- old `diag/*`, `exp/*`, `test-*`, bisect, archive and temporary branches
- `main`

Build/helper branches such as `build/release-se-once` are build carriers only. They are never source of truth.

## Promotion flows

### Stock / non-SE fixes

Diagnostics -> runtime verification as appropriate -> Release.

If a stock fix affects code shared by SE builds, sync only the verified fix into Release+SE and Diagnostics+SE. Do not merge entire diagnostic branches.

### Enhanced Sound fixes

Diagnostics+SE and/or Test -> runtime verification -> Release+SE.

After promotion:
- keep Diagnostics+SE compatible with the promoted SE behavior when that diagnostic line is next used;
- advance/rebase the Test line from the current Release+SE baseline before a new unrelated experiment when necessary.

### Haptic experiments

All new haptic behavior is developed on [Test] first.

A haptic experiment may be promoted to Release+SE only after:
1. static/build validation,
2. user runtime validation,
3. explicit user approval to promote.

Do not put haptic experiments directly into stock Release or stock Diagnostics.

## Non-negotiable branch isolation

- Never fast-forward or merge Diagnostics/Diagnostics+SE/Test wholesale into a release branch when that would carry diagnostic or experimental code.
- Promote only the verified patch/change.
- Never call a Test or Diagnostics artifact a release build.
- Verify branch + HEAD + workflow + artifact identity before handing off a binary.
- Do not touch `main`.
- Do not silently substitute an older branch-role scheme for these five active roles.

## Protected baseline behavior

Unless the user explicitly changes policy, preserve:

- Bayonetta 2 / Star Fox Zero / Xenoblade Chronicles X `vkGetQueryPoolResults` direct query readback FIX for all JPN / USA / EUR application title IDs.
- Bayonetta 2: `00050000-1011B900`, `00050000-10172600`, `00050000-10172700`.
- Star Fox Zero: `00050000-101AFF00`, `00050000-101B0400`, `00050000-101B0500`.
- Xenoblade Chronicles X: `00050000-10116100`, `00050000-101C4D00`, `00050000-101C4C00`.
- Do not promote the historical XCX `0 -> 1 force-visible` experiment.
- VS `DEFAULT_VAL` synthesize/linkage FIX.
- FidelityFX FSR1 EASU + RCAS.
- Existing verified Adreno / pre-e834 behavior.
- Do not repeat already rejected experiments without new evidence.

## Build discipline

Before starting CI:
1. verify the intended role and actual HEAD;
2. inspect active/queued runs once;
3. trigger one build only;
4. do not auto-rerun failed/cancelled work;
5. do not repeatedly poll unless needed for a direct user request.

For Release+SE, `build/release-se-once` may be used as a one-shot build carrier when the release workflow guard prevents direct building. The carrier must contain the exact intended Release+SE source and must not become a source-of-truth branch.
