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

## LAST VALIDATED NON-DOCUMENTATION CHECKPOINT

- code commit: `04b5626c77503aceed1fb712e45563bf620262fc`
- message: `test: fix ARM64 compare reuse patch ordering`
- workflow Run #56: `34558962681`
- result: **SUCCESS**
- artifact: `cemu-arm64-test`
- artifact ID: `10184443139`
- artifact digest: `sha256:7294b62139b1f53aa56205a5a060dbd54d6dea62963a710125dbf03aa22efb82`

Documentation commits may advance the branch HEAD beyond this code checkpoint. Always fetch the real HEAD before continuing.

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

Controlled BOTW benchmark protocol currently used:
- same save/location/camera
- no movement for the first-pass static benchmark
- same graphics/FPS++ settings
- weather fixed by graphic pack
- restart Cemu for each preset
- ignore startup/warmup and compare `t=70s..260s`

### Closed / non-winning directions for this scene

Do not repeat these without new evidence:
- timer `UDIV64`
- `NO_EXTRA_FENCE`
- ARM64 timer serialize
- skip WAW barrier
- skip RT load barrier
- force render-pass reuse
- ARM64 NEON texture-hash experiment
- historical `perf-arm64-jit-ab` compare/branch-fusion and direct-dispatch variants

These either matched baseline poorly or regressed the controlled BOTW scene.

## PPC PROFILER

Current in-app PPC thread profiler is diagnostic-only:
- selected thread: typically `0E001800 / Default Core 1`
- samples only after observing guest thread in `RUNNING`
- profiler-induced suspend/resume is used to materialize PPC context
- outer sampling cadence is **10 ms** (`aa2eba94f6ca6b7ce46b1e7dfc970f3e923fd511`)
- the earlier 1 ms cadence materially perturbed FPS and must not be restored casually

Latest compare-reuse profile (`04b5626` build):
- observations: 5058
- RUNNING: 3564 (70.46%)
- WAITING: 1463 (28.92%)
- top guest/runtime samples:
  - `coreinit.OSWaitEvent` 12.93%
  - guest `0x0420CB80` 5.56%
  - guest `0x02A281A0` 4.12%
  - `gx2.GX2SetAlphaToMaskReg` 3.73%
  - guest `0x03B84854` 3.68%
  - `coreinit.OSWaitSemaphore` 3.17%
  - guest `0x0399B4DC` 1.77%

HLE wait functions are observations, not automatic JIT optimization targets.

## FIRST POSITIVE JIT CANDIDATE — ARM64 CONSECUTIVE COMPARE REUSE

Experiment token:
- `arm64-compare-reuse`

Launcher:
- `ARM64_COMPARE_REUSE.cmd`

Implementation commits:
- `bafc464ce0a4b88b20b74c04f66b55899185a576` — add consecutive identical compare flag reuse
- `04b5626c77503aceed1fb712e45563bf620262fc` — fix patch ordering against diagnostics instrumentation

Static/native-code evidence:
- hotspot `0x03B84854` previously emitted repeated identical compare sequences
- with the experiment enabled, native words include `6b05009f 1a9f27ea 1a9f97eb 1a9f17ec`
- this corresponds to one compare feeding three conditional-set results instead of repeating the same compare for each result

Controlled same-build A/B, `t=70..260s`:

| metric | BASELINE | ARM64_COMPARE_REUSE | delta |
|---|---:|---:|---:|
| avg FPS | 52.091 | 52.968 | +1.68% |
| avg frame time | 19.200 ms | 18.883 ms | -1.65% |
| mean p99 | 23.636 ms | 22.790 ms | -3.58% |
| mean 1% low | 42.482 FPS | 43.900 FPS | +3.34% |

Interpretation:
- direction is positive and the generated-code reduction is real
- effect size is small enough that it is **not yet a FIX**
- user runtime impression after direct A/B was “minor or possibly no visible difference”
- do **not** promote to Release/Diagnostics yet
- keep as a preserved positive candidate while continuing hotspot discovery

## CURRENT NEXT ACTION

Read `NEXT_ACTION.md` and `DEBUG_HISTORY_20260911_ARM64_JIT_PERF.md`.

Immediate priority is **analysis before another behavior change**:
1. inspect guest hotspot `0x0420CB80` and its exact IML/native sequence; determine why the mapped block is load-heavy
2. inspect `0x02A281A0`; its mapped entry starts as a branch/thunk, so follow the branch target before interpreting trailing words as executable code
3. only after one concrete redundant ARM64 JIT pattern is proven, create one new runtime-gated experiment
4. benchmark that experiment alone against same-build BASELINE; do not silently combine it with compare-reuse
