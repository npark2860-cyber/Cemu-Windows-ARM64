# Cemu Windows ARM64 / Adreno — Branch Policy

This document is the canonical branch-role and promotion policy for this repository.

Actual GitHub branch / HEAD / workflow / source remains the source of truth. If an older handoff or debug-history document conflicts with this file about current policy, this file wins.

## Exactly three active work branches

1. **[Release] `final-adreno-compat-arm64`**
   - Production/release baseline only.
   - Contains verified behavior fixes and release features only.
   - No diagnostic-only UI/logging and no unverified experiments.
   - Active workflow: `.github/workflows/final-adreno-compat-arm64.yml`
   - Artifact: `cemu-arm64-release`

2. **[Diagnostics] `fix/arm64-diagnostics-ui-artifact-gate`**
   - Current Release behavior + observation-only diagnostic instrumentation/UI.
   - Diagnostics must not change game behavior while their switches are OFF.
   - Active workflow: `.github/workflows/diagnostics-arm64.yml`
   - Artifact: `cemu-arm64-diagnostics`

3. **[Test] `runtime-experiments-arm64`**
   - Behavior-changing experiments only.
   - One behavior variable at a time.
   - An experiment is not a FIX until static verification, CI and required runtime validation pass.
   - Active workflow: `.github/workflows/runtime-experiments-arm64.yml`
   - Artifact: `cemu-arm64-test`

All other branches/workflows are historical reference only unless explicitly requested. `main` must not be modified.

## Current Adreno Vulkan query baseline

As of 2026-09-09, the current Adreno driver baseline is treated as having the previously observed Vulkan query behavior normalized.

Therefore the active Release and Diagnostics baselines must use the normal upstream Cemu occlusion-query path for:

- Bayonetta 2
- Star Fox Zero
- Xenoblade Chronicles X (XCX)

The following are no longer active fixes and must not be present in Release/Diagnostics behavior:

- title-gated `vkGetQueryPoolResults` direct-readback workaround for Bayonetta 2 / Star Fox Zero
- XCX-specific direct-readback experiment
- XCX forced `0 -> 1` occlusion visibility experiment
- any equivalent title-ID-gated query-result override for those games

Generic observation-only query diagnostics are still allowed in Diagnostics, but they must not select, replace, force, or synthesize query results.

The old query experiments remain in DEBUG_HISTORY only as historical evidence. Do not reintroduce them unless a new regression is reproduced on the current driver baseline.

## Non-negotiable protected behavior

- Do not touch `main`.
- Keep the verified VS `DEFAULT_VAL` synthesize/linkage compatibility fix.
- Keep AMD FidelityFX FSR1 EASU + RCAS.
- Keep existing verified Adreno / pre-e834 compatibility behavior that is unrelated to the retired per-title query workarounds.
- Do not repeat rejected experiments without new evidence.

## Role isolation

Before any write or CI run, determine the intended role first.

- Never merge Diagnostics/Test wholesale into Release.
- Never run a Release workflow from Diagnostics/Test.
- Never run a Diagnostics workflow from Release/Test.
- Never run a Test workflow from Release/Diagnostics.
- Never hand off an artifact unless branch + HEAD + workflow + artifact identity match the intended role.

## Promotion flow

**Diagnostics baseline -> Test one-variable experiment -> runtime-verified FIX -> promote only that FIX to Release and Diagnostics -> advance Test from the updated Diagnostics baseline**

When a Test change is verified:

1. apply only the verified FIX to Release;
2. apply the same FIX to Diagnostics;
3. keep diagnostics/test-only code out of Release;
4. reset/advance Test from the updated Diagnostics baseline before the next experiment.

## Start-of-work verification

Before code change or CI:

1. identify Release / Diagnostics / Test role;
2. fetch actual branch HEAD;
3. inspect the actual workflow/source;
4. confirm protected fixes are present;
5. confirm retired per-title query workarounds are absent from Release/Diagnostics;
6. make the smallest role-appropriate change;
7. statically verify before CI.
