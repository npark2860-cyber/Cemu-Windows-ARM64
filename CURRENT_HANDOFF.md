# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> Canonical branch-role/promotion policy: `BRANCH_POLICY.md`
>
> If an older debug/handoff document names a different active branch or promotion flow, ignore that stale branch instruction. Fetch the actual GitHub branch/HEAD/workflow/source first.

## ROLE

**[Diagnostics]**

Repository:
- `npark2860-cyber/Cemu-Windows-ARM64`

Active diagnostics branch:
- `fix/arm64-diagnostics-ui-artifact-gate`

Functional diagnostics baseline before docs-only policy commits:
- `c26842d0dca4d0bbb8f468c5aedc83cde7557beb`
- release behavior baseline plus switchable diagnostics UI
- persistent diagnostics checkbox state / hitch threshold
- safe `Disable all` behavior

## DIAGNOSTICS RULE

This branch must always equal:

**current Release FIX set + diagnostics instrumentation/UI**

Therefore every FIX promoted to `final-adreno-compat-arm64` must also be applied here.

Diagnostics-only code may stay here:
- switchable logging/instrumentation
- diagnostics UI
- checkbox/preset/hitch-threshold persistence
- observation-only failure correlation

Do not promote diagnostics-only code into Release unless explicitly requested.

## PROTECTED / DO NOT REGRESS

- Bayonetta 2 / Star Fox Zero `vkGetQueryPoolResults` direct query readback FIX
- VS `DEFAULT_VAL` synthesize/linkage FIX
- FidelityFX FSR1 EASU + RCAS
- existing Adreno / pre-e834 verified fixes
- XCX query path remains separate
- `main` must not be touched
- excluded query/workaround experiments must not be repeated without new evidence

## PROMOTION RULE

When a Test change is runtime-verified as a FIX:
1. apply the verified FIX to Release
2. apply the same verified FIX here
3. keep diagnostics extras here only
4. reset/advance Test from this updated Diagnostics baseline before the next experiment

## NEXT ACTION RULE

Use this branch for investigation and log collection.
Behavior-changing experiments belong on **[Test] `runtime-experiments-arm64`**, not here.
