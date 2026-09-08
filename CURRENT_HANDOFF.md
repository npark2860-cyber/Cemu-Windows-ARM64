# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> Canonical branch-role/promotion policy: `BRANCH_POLICY.md`
>
> If an older debug/handoff document names a different active branch or promotion flow, ignore that stale branch instruction. Fetch the actual GitHub branch/HEAD/workflow/source first.

## ROLE

**[Test]**

Repository:
- `npark2860-cyber/Cemu-Windows-ARM64`

Active test branch:
- `runtime-experiments-arm64`

Functional test baseline before docs-only policy commits:
- `c26842d0dca4d0bbb8f468c5aedc83cde7557beb`
- same functional baseline as Diagnostics before the next experiment

## TEST RULE

All behavior-changing experiments happen here.

Rules:
- start from the current Diagnostics baseline
- change one variable at a time
- static-verify the diff before CI
- do not call an experiment a FIX until required CI/runtime validation passes
- do not mix XCX query experiments with Bayonetta 2 / Star Fox Zero paths
- do not repeat already excluded experiments without new evidence

## VERIFIED FIX PROMOTION

When a Test change is verified as a FIX:
1. apply **only that FIX** to **[Release] `final-adreno-compat-arm64`**
2. apply the **same FIX** to **[Diagnostics] `fix/arm64-diagnostics-ui-artifact-gate`**
3. keep diagnostics-only code out of Release
4. reset/advance this Test branch from the updated Diagnostics baseline before starting the next experiment

Never promote the whole Test branch into Release if that would carry diagnostics or experiment-only commits.

## PROTECTED / DO NOT REGRESS

- Bayonetta 2 / Star Fox Zero `vkGetQueryPoolResults` direct query readback FIX
- VS `DEFAULT_VAL` synthesize/linkage FIX
- FidelityFX FSR1 EASU + RCAS
- existing Adreno / pre-e834 verified fixes
- XCX query path remains separate
- `main` must not be touched

## NEXT ACTION RULE

There is no implicit experiment. Before changing behavior, identify the single variable being tested and confirm the actual current Test HEAD/source.
