# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> Canonical policy: `BRANCH_POLICY.md`
> Active-role manifest: `ACTIVE_BRANCH_ROLES.md`
> Do **not** trust a hardcoded HEAD in a handoff. Before every write/build, fetch the actual branch HEAD and workflow from GitHub.

## ROLE

**[Release]**

Repository:
- `npark2860-cyber/Cemu-Windows-ARM64`

Branch:
- `final-adreno-compat-arm64`

Only active workflow on this branch:
- `.github/workflows/final-adreno-compat-arm64.yml`
- display name: `[Release] Cemu Windows ARM64`

Only valid artifact identity:
- `cemu-arm64-release`
- executable: `Cemu.exe`

## RELEASE CONTRACT

This branch is production/release only.

Allowed:
- runtime-verified fixes
- protected Adreno compatibility fixes
- FSR1
- release branding (`Cemu ARM64`)

Forbidden:
- ARM64 Diagnostics UI
- diagnostic checkbox persistence
- logging-only instrumentation
- `RuntimeDiagnostics` runtime hooks in the release binary
- `[ADRENO_DIAG]`, `[CEMU_DIAG]`, `[GPU_QUERY_VIS]`, `[PS_INPUT_LINKAGE]` diagnostic markers in the release binary
- unverified behavior experiments

The Release workflow contains branch-role and diagnostics-free guards and must fail if these constraints are violated.

## PROTECTED / DO NOT REGRESS

- Bayonetta 2 / Star Fox Zero / Xenoblade Chronicles X `vkGetQueryPoolResults` direct query readback FIX for all JPN / USA / EUR application title IDs
  - Bayonetta 2: `00050000-1011B900`, `00050000-10172600`, `00050000-10172700`
  - Star Fox Zero: `00050000-101AFF00`, `00050000-101B0400`, `00050000-101B0500`
  - Xenoblade Chronicles X: `00050000-10116100`, `00050000-101C4D00`, `00050000-101C4C00`
- XCX historical `0 -> 1 force-visible` experiment is not part of Release
- VS `DEFAULT_VAL` synthesize/linkage FIX
- FidelityFX FSR1 EASU + RCAS
- existing Adreno / pre-e834 verified fixes
- `main` must not be touched
- rejected query/workaround experiments are not repeated without new evidence

## PROMOTION RULE

A Test change becomes a release FIX only after required static verification, CI and runtime validation.

When verified:
1. promote only the verified FIX to Release
2. apply the same FIX to Diagnostics
3. do not carry Diagnostics/Test-only commits into Release

## NEXT ACTION RULE

- investigation/logging -> **[Diagnostics] `fix/arm64-diagnostics-ui-artifact-gate`**
- behavior-changing experiment -> **[Test] `runtime-experiments-arm64`**
- do not develop experiments directly on Release
