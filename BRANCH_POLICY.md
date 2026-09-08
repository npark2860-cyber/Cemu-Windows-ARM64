# Cemu Windows ARM64 / Adreno — Branch Policy

This document is the canonical branch-role and promotion policy for this repository.

If an older handoff/debug document conflicts with this file about which branch to use or how a verified fix is promoted, **this file wins**. Actual GitHub branch/HEAD/workflow/source remains the source of truth for the implementation currently present on each branch.

## Exactly three active work branches

Only these three branches are active for ongoing work:

1. **[Release] `final-adreno-compat-arm64`**
   - Production/release baseline only.
   - Contains only verified behavior fixes and release features.
   - Must not contain diagnostic-only UI, checkbox persistence, logging-only instrumentation, or unverified experiments.
   - Release artifacts are produced only from this branch.

2. **[Diagnostics] `fix/arm64-diagnostics-ui-artifact-gate`**
   - Must always represent **current Release + diagnostic instrumentation/UI**.
   - Every fix that has been verified and promoted to Release must also be applied here.
   - Diagnostic-only logging/UI/persistence may exist here and must not be promoted to Release unless explicitly requested.
   - This is the normal branch for reproducing and investigating failures with switchable diagnostics.

3. **[Test] `runtime-experiments-arm64`**
   - Must normally start from the current Diagnostics baseline.
   - Behavior-changing experiments are performed here only.
   - Change one variable at a time.
   - An experiment is not a FIX until static verification, CI, and required runtime validation pass.

All other historical branches are **read-only reference/archive branches** and are not valid targets for new work unless the user explicitly requests historical inspection. `main` is outside this workflow and must not be touched.

## Promotion flow

The fixed workflow is:

**Diagnostics baseline -> Test one-variable experiment -> runtime-verified FIX -> promote the same FIX to Release and Diagnostics -> reset/advance Test from updated Diagnostics baseline**

When a Test change is verified as a FIX:

1. Apply **only the verified FIX** to `final-adreno-compat-arm64`.
2. Apply the **same verified FIX** to `fix/arm64-diagnostics-ui-artifact-gate`.
3. Keep diagnostic-only code exclusive to the Diagnostics branch.
4. After both are synchronized, move/reset `runtime-experiments-arm64` to the updated Diagnostics baseline before the next experiment.

Do **not** fast-forward or merge an entire Diagnostics/Test branch into Release if that would carry diagnostic or experimental commits. Promote selected FIX commits/patches only.

## Artifact identity rules

- **Release artifact**: only from `final-adreno-compat-arm64`.
- **Diagnostics artifact**: only from `fix/arm64-diagnostics-ui-artifact-gate`.
- **Test artifact**: only from `runtime-experiments-arm64`.
- Never call a Diagnostics or Test artifact a release build.
- Before handing an artifact to the user, verify branch, HEAD, workflow run, and artifact source.

## Mandatory no-regression constraints

The following are protected and must survive every promotion unless the user explicitly changes policy:

- Do not touch `main`.
- Keep Bayonetta 2 / Star Fox Zero `vkGetQueryPoolResults` direct query readback FIX.
- Keep VS `DEFAULT_VAL` synthesize/linkage FIX.
- Keep FidelityFX FSR1 EASU + RCAS.
- Keep existing Adreno / pre-e834 verified fixes.
- Keep XCX query behavior separate from Bayonetta 2 / Star Fox Zero.
- Do not repeat already excluded query experiments.
- Do not reintroduce previously rejected workaround experiments as fixes without new evidence.

## Start-of-work verification

Before any code change or CI run:

1. Identify which of the three roles the requested work belongs to.
2. Fetch the actual branch HEAD.
3. Inspect the actual workflow/source on that branch.
4. Confirm protected fixes are present.
5. Make the smallest role-appropriate change only.

If a handoff document is stale, update the document instead of following the stale branch/HEAD.
