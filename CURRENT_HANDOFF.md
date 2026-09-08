# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> Canonical policy: `BRANCH_POLICY.md`
> Active-role manifest: `ACTIVE_BRANCH_ROLES.md`
> Do **not** trust a hardcoded HEAD in a handoff. Before every write/build, fetch the actual branch HEAD and workflow from GitHub.

## ROLE

**[Test]**

Repository:
- `npark2860-cyber/Cemu-Windows-ARM64`

Branch:
- `runtime-experiments-arm64`

Only active workflow on this branch:
- `.github/workflows/runtime-experiments-arm64.yml`
- display name: `[Test] Cemu Windows ARM64`

Only valid artifact identity:
- `cemu-arm64-test`
- executable: `Cemu-Test.exe`

## TEST CONTRACT

All behavior-changing experiments happen here only.

Rules:
- start from the current Diagnostics baseline
- change one behavior variable at a time
- static-verify the diff before CI
- do not call an experiment a FIX until required CI/runtime validation passes
- keep XCX query experiments separate from Bayonetta 2 / Star Fox Zero paths
- do not repeat rejected experiments without new evidence
- never promote the whole Test branch into Release

## VERIFIED FIX PROMOTION

When a Test change is verified as a FIX:
1. apply **only that FIX** to **[Release] `final-adreno-compat-arm64`**
2. apply the **same FIX** to **[Diagnostics] `fix/arm64-diagnostics-ui-artifact-gate`**
3. keep diagnostics/test-only code out of Release
4. advance/reset Test from the updated Diagnostics baseline before starting the next experiment

## PROTECTED / DO NOT REGRESS

- Bayonetta 2 / Star Fox Zero `vkGetQueryPoolResults` direct query readback FIX
- VS `DEFAULT_VAL` synthesize/linkage FIX
- FidelityFX FSR1 EASU + RCAS
- existing Adreno / pre-e834 verified fixes
- XCX query behavior remains separate
- `main` must not be touched

## NEXT ACTION RULE

There is no implicit experiment. Before changing runtime behavior, identify the single variable being tested and fetch the current Test HEAD/source.
