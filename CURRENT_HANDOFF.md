# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> Canonical policy: `BRANCH_POLICY.md`
> Active-role manifest: `ACTIVE_BRANCH_ROLES.md`
> Do **not** trust a hardcoded branch HEAD in a handoff. Before every write/build, fetch the actual branch HEAD/workflow/source from GitHub.

## ROLE

**[Test]**

Repository:
- `npark2860-cyber/Cemu-Windows-ARM64`

Branch:
- `runtime-experiments-arm64`

Workflow:
- `.github/workflows/runtime-experiments-arm64.yml`
- display name: `[Test] Cemu Windows ARM64`

Artifact identity:
- `cemu-arm64-test`
- executable: `Cemu-Test.exe`

`main`, Release, and Diagnostics are not to be modified in this stage.

## LAST VALIDATED NON-DOCUMENTATION CHECKPOINT

- code commit: `04b5626c77503aceed1fb712e45563bf620262fc`
- message: `test: fix ARM64 compare reuse patch ordering`
- workflow Run #56: `34558962681`
- result: **SUCCESS**
- artifact: `cemu-arm64-test`
- artifact ID: `10184443139`
- artifact digest: `sha256:7294b62139b1f53aa56205a5a060dbd54d6dea62963a710125dbf03aa22efb82`

## CURRENT P1 EXPERIMENT — BUILD FAILED

Experiment:
- `arm64-rname-ldp`

Behavior-changing code commit:
- `f929fa8007d6ef17f90a3c166b5d248d2ee30e3d`
- message: `jit: pair adjacent ARM64 state loads`

Changed source:
- `src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp`

Intent:
- pair two consecutive non-GPR `ImlOperation::R_NAME` loads when the second `PPCInterpreter_t` state offset is exactly `+8`
- result registers must differ
- positive scaled `LDP` immediate must be legal/aligned
- otherwise fall back to the existing single-instruction lowering
- no guest memory load/store semantics, query path, Vulkan path, or RA/liveness policy is intentionally changed

GitHub Actions result for this code commit:
- workflow: `ARM64 Windows Test Build`
- run ID: `34576700718`
- job ID: `103190682420`
- result: **FAILURE**
- failing step: **Build Cemu**
- checkout/configure/vcpkg steps succeeded
- artifact upload was skipped

The exact compiler error line was **not recovered before handoff** because the job-log download endpoint did not decode successfully through the current connector. Do not guess the cause from the source diff. The next tab must recover the actual compiler diagnostic first (GitHub UI/API/local reproduction are all acceptable), then make the smallest P1-only compile fix.

Documentation commits after `f929fa8...` may advance the branch HEAD. Always fetch the real branch HEAD before continuing.

## TEST CONTRACT

All behavior-changing experiments happen here only.

Rules:
- change one behavior variable at a time
- static-verify the diff before CI
- do not call an experiment a FIX until CI + runtime + controlled A/B validation pass
- keep XCX query experiments separate from Bayonetta 2 / Star Fox Zero paths
- do not repeat rejected experiments without new evidence
- never promote the whole Test branch into Release
- `main` must not be touched

## PROTECTED / DO NOT REGRESS

- Bayonetta 2 / Star Fox Zero `vkGetQueryPoolResults` direct query readback FIX
- VS `DEFAULT_VAL` synthesize/linkage FIX
- FidelityFX FSR1 EASU + RCAS
- existing Adreno / pre-e834 verified fixes
- XCX query behavior remains separate

## PERFORMANCE WORK — CURRENT STATE

A reusable BOTW performance harness is present. `perf-log` records 10-second windows including average FPS/frame time, p99, approximate 1% low, barriers/frame and renderpasses/frame.

Controlled BOTW benchmark protocol:
- same save/location/camera
- no movement for first-pass static benchmark
- same graphics/FPS++ settings
- weather fixed by graphic pack
- restart Cemu for each preset
- ignore startup/warmup and compare `t=70s..260s`

### Closed / non-winning directions for this scene

Do not repeat without new evidence:
- timer `UDIV64`
- `NO_EXTRA_FENCE`
- ARM64 timer serialize
- skip WAW barrier
- skip RT load barrier
- force render-pass reuse
- ARM64 NEON texture-hash experiment
- historical `perf-arm64-jit-ab` compare/branch-fusion and direct-dispatch variants

## PPC PROFILER / P0 EVIDENCE

Current profiler uses RUNNING-only sampling at 10 ms cadence. The earlier 1 ms cadence materially perturbed FPS and must not be restored casually.

Latest important guest hotspots:
- `0x0420CB80` — 5.56%
- `0x02A281A0` — 4.12%
- `0x03B84854` — 3.68%
- `0x0399B4DC` — 1.77%

P0 analysis of `0x0420CB80` established a concrete backend pattern:
- pre-RA and post-RA IML show repeated non-GPR `R_NAME` state reads
- examples include contiguous 64-bit pairs such as `SPR::LR + SPR::CTR` and `SPR::XER + temporaryFPR`
- native lowering emits separate `LDR` instructions for these adjacent `PPCInterpreter_t` fields
- examples observed:
  - `F940A546  ldr x6, [x10,#328]`
  - `F940A942  ldr x2, [x10,#336]`
  - `F9410146  ldr x6, [x10,#512]`
  - `F9410542  ldr x2, [x10,#520]`
- these are state loads, not guest-memory loads
- RA does not merge/remove them
- this evidence motivated the `arm64-rname-ldp` P1 experiment

For `0x02A281A0`, the mapped native entry begins with an AArch64 branch/thunk. Do not interpret trailing raw words as a straight-line body until the first branch destination is resolved.

See `DEBUG_HISTORY_20260911_ARM64_JIT_PERF.md` for detailed evidence.

## PRESERVED POSITIVE CANDIDATE — ARM64 COMPARE REUSE

Experiment token:
- `arm64-compare-reuse`

Controlled same-build BOTW A/B (`t=70..260s`):
- baseline: 52.091 FPS
- compare-reuse: 52.968 FPS
- delta: +1.68%
- average frame time: -1.65%
- mean p99: -3.58%
- mean 1% low: +3.34%

Generated-code reduction is real, but this is still a **candidate, not a FIX**. Do not promote it yet.

## CURRENT NEXT ACTION

Read `NEXT_ACTION.md`, `HANDOFF_PROMPT.md`, `DEBUG_HISTORY_20260911_ARM64_JIT_PERF.md`, and `PERFORMANCE_OPTIMIZATION_PLAN.md`.

Immediate order:
1. fetch actual Test branch HEAD and confirm `f929fa8...` remains the latest behavior-changing code commit beneath any handoff docs
2. recover the exact compiler diagnostic from failed run `34576700718` / job `103190682420`, or reproduce the same build error locally
3. determine whether the failure is caused by the `arm64-rname-ldp` source change; do not infer without the diagnostic
4. if it is P1-local, make the smallest compile-only correction on Test branch; do not broaden the optimization
5. static-inspect the corrected diff and rerun Test CI
6. **only after CI is green**, verify the target native sequence actually becomes legal `LDP` without changing branch/control structure
7. then run controlled BOTW BASELINE vs `arm64-rname-ldp` A/B
8. if neutral/negative/unstable, reject the experiment; if repeatably positive and correct, reprofile before considering promotion

No runtime A/B is meaningful until the current build failure is resolved.
