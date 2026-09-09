# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> Canonical policy: `BRANCH_POLICY.md`
> Active-role manifest: `ACTIVE_BRANCH_ROLES.md`
> Always verify the actual GitHub branch HEAD/workflow/source before writing or building.

## ROLE

**[Release]**

Repository:
- `npark2860-cyber/Cemu-Windows-ARM64`

Branch:
- `final-adreno-compat-arm64`

Workflow:
- `.github/workflows/final-adreno-compat-arm64.yml`
- display name: `[Release] Cemu Windows ARM64`

Artifact:
- `cemu-arm64-release`
- executable: `Cemu.exe`

## CURRENT RELEASE CONTRACT

Release contains only verified common behavior fixes/features. It must not contain diagnostic-only UI/logging or experimental runtime behavior.

Current Adreno driver baseline no longer requires per-title Vulkan query workarounds for:
- Bayonetta 2
- Star Fox Zero
- Xenoblade Chronicles X (XCX)

Release must use the normal upstream Cemu occlusion-query path for those titles. No title-gated `vkGetQueryPoolResults` direct readback, XCX direct-readback experiment, forced zero-to-one visibility, or equivalent query-result override is allowed.

## PROTECTED / DO NOT REGRESS

- VS `DEFAULT_VAL` synthesize/linkage compatibility FIX
- FidelityFX FSR1 EASU + RCAS
- verified Adreno / pre-e834 compatibility fixes unrelated to the retired per-title query workaround
- `main` must not be touched
- rejected experiments are not repeated without new evidence

## NEXT ACTION

Build the Release branch with its own workflow and verify the produced artifact identity. Runtime smoke validation should use the current Adreno driver baseline.
