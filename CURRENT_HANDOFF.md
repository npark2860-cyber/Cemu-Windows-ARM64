# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> Canonical policy: `BRANCH_POLICY.md`
> Active-role manifest: `ACTIVE_BRANCH_ROLES.md`
> Do **not** trust a hardcoded HEAD in a handoff. Before every write/build, fetch the actual branch HEAD and workflow from GitHub.

## ROLE

**[Diagnostics]**

Repository:
- `npark2860-cyber/Cemu-Windows-ARM64`

Branch:
- `fix/arm64-diagnostics-ui-artifact-gate`

Only active workflow on this branch:
- `.github/workflows/diagnostics-arm64.yml`
- display name: `[Diagnostics] Cemu Windows ARM64`

Only valid artifact identity:
- `cemu-arm64-diagnostics`
- executable: `Cemu-Diagnostics.exe`

## DIAGNOSTICS CONTRACT

This branch must always represent:

**current Release FIX set + observation-only diagnostics UI/instrumentation**

Every FIX promoted to Release must also be applied here.

Diagnostics-only features stay here and do not move to Release unless explicitly requested.

Current targeted diagnostics include:
- switchable diagnostics UI with persisted checkbox state / hitch threshold
- `PS input linkage`
  - SPI_PS_INPUT_CNTL / semantic / DEFAULT_VAL / interpolation / VS producer visibility
- `GPU occlusion/query visibility`
  - generic GPU occlusion/query visibility tracing

Both targeted diagnostics are default OFF and are observation-only.

## PROTECTED / DO NOT REGRESS

- Bayonetta 2 / Star Fox Zero / Xenoblade Chronicles X `vkGetQueryPoolResults` direct query readback FIX for all JPN / USA / EUR application title IDs
  - Bayonetta 2: `00050000-1011B900`, `00050000-10172600`, `00050000-10172700`
  - Star Fox Zero: `00050000-101AFF00`, `00050000-101B0400`, `00050000-101B0500`
  - Xenoblade Chronicles X: `00050000-10116100`, `00050000-101C4D00`, `00050000-101C4C00`
- XCX historical `0 -> 1 force-visible` experiment is not part of Diagnostics behavior
- VS `DEFAULT_VAL` synthesize/linkage FIX
- FidelityFX FSR1 EASU + RCAS
- existing Adreno / pre-e834 verified fixes
- `main` must not be touched
- rejected experiments are not repeated without new evidence

## PROMOTION RULE

When a Test change is runtime-verified as a FIX:
1. apply only that FIX to Release
2. apply the same FIX here
3. keep diagnostics-only code here
4. advance/reset Test from the updated Diagnostics baseline before the next experiment

## NEXT ACTION RULE

Use this branch for investigation and log collection.
Behavior-changing experiments belong on **[Test] `runtime-experiments-arm64`**.
