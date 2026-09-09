# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> Canonical policy: `BRANCH_POLICY.md`
> Active-role manifest: `ACTIVE_BRANCH_ROLES.md`
> Always verify the actual GitHub branch HEAD/workflow/source before writing or building.

## ROLE

**[Diagnostics]**

Repository:
- `npark2860-cyber/Cemu-Windows-ARM64`

Branch:
- `fix/arm64-diagnostics-ui-artifact-gate`

Workflow:
- `.github/workflows/diagnostics-arm64.yml`
- display name: `[Diagnostics] Cemu Windows ARM64`

Artifact:
- `cemu-arm64-diagnostics`
- executable: `Cemu-Diagnostics.exe`

## CURRENT DIAGNOSTICS CONTRACT

Diagnostics represents current Release behavior plus switchable observation-only instrumentation/UI.

Current Adreno driver baseline no longer requires per-title Vulkan query behavior changes for:
- Bayonetta 2
- Star Fox Zero
- Xenoblade Chronicles X (XCX)

The generated diagnostics build must retain the normal upstream Cemu query-result behavior. Generic query lifecycle/result visibility logging is allowed, but it must never choose a different result source, force visibility, synthesize a nonzero result, or gate behavior by those title IDs.

Current targeted diagnostics remain observation-only, including:
- PS input linkage
- generic GPU occlusion/query visibility

Both are default OFF.

## PROTECTED / DO NOT REGRESS

- VS `DEFAULT_VAL` synthesize/linkage compatibility FIX
- FidelityFX FSR1 EASU + RCAS
- verified Adreno / pre-e834 compatibility fixes unrelated to the retired per-title query workaround
- diagnostics remain switchable and observation-only
- `main` must not be touched

## NEXT ACTION

Build the Diagnostics branch with its own workflow, require all diagnostics verifiers to PASS, and verify the produced artifact identity. Runtime validation uses the current Adreno driver baseline.
