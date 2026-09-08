# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> Canonical branch-role/promotion policy: `BRANCH_POLICY.md`
>
> If an older debug/handoff document names a different active branch or promotion flow, ignore that stale branch instruction. Fetch the actual GitHub branch/HEAD/workflow/source first.

## ROLE

**[Release]**

Repository:
- `npark2860-cyber/Cemu-Windows-ARM64`

Active release branch:
- `final-adreno-compat-arm64`

Functional release baseline:
- `6d26a324cf48b648a04442bb13c96ce10343d0ce`
- commit: `release: restore permanent PS DEFAULT_VAL linkage fix`

Verified release CI:
- run `34218238464`
- PASS
- artifact `cemu-arm64-release-direct-query-readback-fsr`
- artifact id `10054345029`
- digest `sha256:3e4f6ba33ac79251d8e54cfbcebef53cd61ce888532297766b1403dcba865994`

## RELEASE RULE

This branch contains verified production behavior only.

Do not add:
- diagnostic-only UI/persistence
- logging-only instrumentation
- unverified experiments

A Test change may reach this branch only after required verification/runtime validation. Promote only the verified FIX, not the whole Test/Diagnostics branch.

Every FIX promoted here must also be applied to the Diagnostics branch so Diagnostics remains current Release + diagnostics.

## PROTECTED / DO NOT REGRESS

- Bayonetta 2 / Star Fox Zero `vkGetQueryPoolResults` direct query readback FIX
- VS `DEFAULT_VAL` synthesize/linkage FIX
- FidelityFX FSR1 EASU + RCAS
- existing Adreno / pre-e834 verified fixes
- XCX query path remains separate
- `main` must not be touched
- excluded query/workaround experiments must not be repeated without new evidence

## NEXT ACTION RULE

New behavior-changing work starts on **[Test] `runtime-experiments-arm64`**.
For investigation/logging use **[Diagnostics] `fix/arm64-diagnostics-ui-artifact-gate`**.
Do not develop experiments directly on this Release branch.
