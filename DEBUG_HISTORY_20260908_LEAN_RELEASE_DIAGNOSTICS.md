# 2026-09-08 — Lean switchable ARM64 release diagnostics

## Scope

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Development branch: `exp/release-arm64-diagnostics-lean`

Release baseline branch: `final-adreno-compat-arm64`

Protected behavior that must not regress:

- Star Fox Zero JP direct query readback workaround
- Bayonetta 2 JP direct query readback workaround
- `vkGetQueryPoolResults` direct readback remains title-gated
- Xenoblade Chronicles X query behavior remains separate
- known-good pre-e834 Vulkan behavior
- AMD FidelityFX FSR1 EASU + RCAS release path
- `main` is not touched

## User-mandated diagnostic contract

1. Every heavy diagnostic must be individually switchable from `ARM64 Diagnostics`.
2. All diagnostic flags default to OFF.
3. OFF must not generate the diagnostic log family or shader dump files.
4. Expensive GPU timestamp resources must not even be allocated until the corresponding diagnostic is enabled.
5. A/B diagnostic builds that force heavy logging are prohibited.
6. The old `RuntimeExperiments` behavior-changing experiment harness must not be part of the release diagnostic path.
7. If a diagnostic has no concrete runtime probe, it must not have a UI checkbox.
8. `IsImplemented` and the UI item set must match exactly.
9. No build/CI is to be run until the user explicitly says to build.

## Why this redesign was required

The historical diagnostic edition created `RuntimeExperiments.h` transiently and applied `Apply-RuntimeExperiments.ps1`. That path also modified PPCTimer, depth-clip/pNext and render-target experiment behavior. Later A/B diagnostics also produced heavy logs regardless of whether the user wanted that diagnostic active.

The release path is therefore being separated from `RuntimeExperiments` and rebuilt around `RuntimeDiagnostics` only.

## Lean release implementation

New release-only patch layer under `tools/diagnostics/release/`:

- `Apply-LeanPipelineDiagnostics.py`
- `Apply-LeanRTDiagnostics.py`
- `Apply-LeanPerformanceDiagnostics.py`
- `Apply-LeanVulkanDiagnostics.py`
- `Apply-LeanFrameDiagnostics.py`
- `Apply-LeanArm64Diagnostics.py`
- `Apply-LeanSubmitLifetime.py`
- `Apply-LeanDiagnosticUI.py`
- `Apply-LeanReleaseDiagnostics.py`
- `Verify-LeanDiagnostics.py`

The orchestrator also reuses the existing shader-failure and completion probes, but transforms the sole legacy `rt-stats` anchor to a literal `false` before applying `Apply-CompleteDiagnostics.py`. No `RuntimeExperiments` source dependency is allowed to survive the verifier.

## Diagnostics targeted for real implementation

The final intended set is all 77 `RuntimeDiagnostics::Flag` entries. This includes the historical ARM64/JIT, Vulkan/pipeline, synchronization and performance probes plus later real probes for:

- command-buffer lifecycle
- fence lifecycle
- semaphore flow
- submit completion
- device-lost/submit error
- shader creation
- GLSL failure phases
- SPIR-V failure
- failed shader dump
- every-shader dump (manual heavy switch only)
- pipeline-cache mismatch
- shader interface
- FBO changes
- attachment usage
- load/store behavior
- render-target aliasing
- feedback-loop support/use/fallback/self-dependency/pass-split
- image layout transitions
- texture lifecycle/view/cache/alias/invalidation/suspicious state
- input diagnostics
- extended performance counters

`Dump every shader` is intentionally retained only as an explicit manual heavy switch; it is never enabled by default.

## Direct-query compatibility

`VulkanAPI.h` already contains `vkGetQueryPoolResults` for the accepted Star Fox Zero/Bayonetta 2 fix. Lean Vulkan diagnostics therefore add the loader only if absent and require the final declaration count to be exactly one.

GPU timestamp diagnostics create the diagnostic timestamp query pool lazily only inside a `GpuTimestamp`-enabled path.

## Verification contract

`Verify-LeanDiagnostics.py` fails if:

- flags do not default OFF
- an `IsImplemented` flag lacks a non-UI runtime consumer
- UI items and implemented probes differ
- a dead/grey unsupported checkbox remains
- any generated release source contains `RuntimeExperiments`
- behavior-changing A/B experiment switches appear
- `vkGetQueryPoolResults` loader declaration is duplicated
- the protected title-gated direct-query workaround is missing
- diagnostic GPU timestamp allocation is not switch-gated
- failed/every-shader dumps are not individually switch-gated

## Workflow state

The experiment branch version of `.github/workflows/final-adreno-compat-arm64.yml` has been staged to call only:

`python ./tools/diagnostics/release/Apply-LeanReleaseDiagnostics.py`

for diagnostics. It no longer calls the legacy runtime experiment harness in the staged workflow.

The workflow still triggers only on `final-adreno-compat-arm64`, so pushes to `exp/release-arm64-diagnostics-lean` do not start CI.

Confirmed Actions runs for `exp/release-arm64-diagnostics-lean`: **0** at this checkpoint.

The earlier accidental release run `34174244438` was canceled by the user and must not be treated as validation.

## Current validation status

- Source/patch design: staged on experiment branch
- Cross-anchor review: in progress; one RT completion-anchor mismatch was already found and normalized before build
- Lean verifier: staged
- CI/build: **NOT RUN by user instruction**
- Runtime validation: not yet performed

Do not claim the 77/77 set is compile-verified until the user explicitly authorizes a build and the workflow succeeds.

## Next action

Continue source-only/static review of the lean patch chain. Do not trigger CI. When the user explicitly says `빌드`, promote the reviewed lean workflow/scripts to the release branch and run the release build, then inspect the first real diagnostic if it fails.
