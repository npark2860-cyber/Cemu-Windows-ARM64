# NEXT ACTION — ARM64 R_NAME LDP build recovery

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Branch: `runtime-experiments-arm64`

## 0. SOURCE-OF-TRUTH CHECK

Before any write/build:
1. fetch actual `runtime-experiments-arm64` HEAD
2. read `CURRENT_HANDOFF.md`
3. read `HANDOFF_PROMPT.md`
4. read `DEBUG_HISTORY_20260911_ARM64_JIT_PERF.md`
5. read `PERFORMANCE_OPTIMIZATION_PLAN.md`
6. confirm `.github/workflows/runtime-experiments-arm64.yml`
7. confirm no requested change touches `main`, Release, or Diagnostics

Last validated non-documentation checkpoint:
- `04b5626c77503aceed1fb712e45563bf620262fc`
- CI run `34558962681` — SUCCESS

Current behavior-changing P1 code commit:
- `f929fa8007d6ef17f90a3c166b5d248d2ee30e3d`
- `jit: pair adjacent ARM64 state loads`

Handoff documentation commits may advance branch HEAD beyond this code commit.

## 1. BUILD-FAILURE RECOVERY GATE — DO THIS FIRST

Current experiment:
- `arm64-rname-ldp`

Failed CI:
- workflow: `ARM64 Windows Test Build`
- run ID: `34576700718`
- job ID: `103190682420`
- conclusion: **FAILURE**
- failed step: **Build Cemu**
- earlier checkout/configure/vcpkg steps succeeded
- no build artifact was produced

The exact compiler diagnostic was not recovered before handoff. Do **not** guess the compiler error from the diff.

Required next sequence:
1. retrieve the actual compiler error from the failed job log, or reproduce the same Test build locally
2. map the error to `f929fa8...`
3. if the failure is caused by the P1 patch, make the smallest compile-only correction
4. do not change the optimization scope while repairing compilation
5. inspect the corrected diff before pushing
6. rerun Test CI
7. stop if the failure is unrelated and document the actual cause before changing anything else

Until CI is green:
- no BOTW A/B
- no promotion
- no second optimization
- no combination with `arm64-compare-reuse`

## 2. WHY `arm64-rname-ldp` EXISTS

P0 analysis of hotspot `0x0420CB80` showed adjacent non-GPR `R_NAME` state loads surviving RA and lowering as independent `LDR`s.

Observed examples:
- `SPR::LR + SPR::CTR`
  - `F940A546  ldr x6, [x10,#328]`
  - `F940A942  ldr x2, [x10,#336]`
- `SPR::XER + temporaryFPR`
  - `F9410146  ldr x6, [x10,#512]`
  - `F9410542  ldr x2, [x10,#520]`

Classification:
- contiguous 64-bit fields in `PPCInterpreter_t`
- not guest-memory loads
- RA does not merge them
- backend currently emits individual loads

P1 therefore attempts only this evidence-derived transformation:
- two consecutive `ImlOperation::R_NAME` operations
- both non-GPR
- distinct destination registers
- second state offset exactly first offset + 8
- legal/aligned positive AArch64 `LDP` scaled immediate
- emit one `LDP`
- otherwise use existing lowering unchanged

## 3. AFTER CI TURNS GREEN — STATIC/NATIVE ACCEPTANCE

Before runtime performance testing, verify at the target hotspot that:
- expected adjacent state-load pair becomes `LDP`
- the relevant pair no longer emits two separate `LDR`s
- branch/control-flow structure is unchanged
- unrelated `R_NAME` operations still use existing lowering
- GPR special-load behavior remains untouched
- protected query/Vulkan paths are untouched

If the expected `LDP` is not present, do not benchmark; diagnose why first.

## 4. RUNTIME ACCEPTANCE

Only after green CI + static/native acceptance:
- benchmark same-build BASELINE vs `arm64-rname-ldp`
- BOTW fixed save/location/camera/weather/settings
- restart Cemu for each preset
- ignore warmup
- compare established `t=70..260s`
- record average FPS, average frame time, p99 and 1% low
- ideally test both ordering directions

Decision:
- repeatably positive + no correctness regression → preserve candidate, reprofile, then decide promotion
- neutral/negative/unstable → reject and restore the experiment
- any correctness regression → reject immediately

## 5. PRESERVED CANDIDATE — DO NOT MIX YET

`arm64-compare-reuse` remains a separate candidate, not a FIX.

Previous same-build BOTW A/B:
- baseline 52.091 FPS
- compare-reuse 52.968 FPS
- approximately +1.68%

Do not silently enable it while measuring `arm64-rname-ldp`.

## 6. SECOND HOTSPOT AFTER THIS EXPERIMENT IS RESOLVED

`0x02A281A0` begins at a branch/thunk-like native entry (`17ffff66`, `d503201f`). Follow the initial AArch64 branch target before interpreting later words as executable straight-line code.

Do not start this work until the current P1 experiment is either validated or rejected.

## 7. CLOSED DIRECTIONS

Do not re-run without new evidence:
- timer UDIV64
- no-extra-fence
- ARM64 timer serialize
- skip WAW barrier
- skip RT load barrier
- force render-pass reuse
- ARM64 NEON texture hash
- historical compare/branch fusion
- historical direct dispatch
