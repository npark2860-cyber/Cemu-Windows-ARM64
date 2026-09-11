# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> Canonical policy: `BRANCH_POLICY.md`
> Active-role manifest: `ACTIVE_BRANCH_ROLES.md`
> Do **not** trust a hardcoded HEAD. Before every write/build, fetch the actual Test branch HEAD/workflow/source from GitHub.

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

## P1 — ARM64 R_NAME GPR LDP

Experiment token:
- `arm64-rname-ldp`

Implementation:
- `f929fa8007d6ef17f90a3c166b5d248d2ee30e3d`
- actual message: `perf: add ARM64 R_NAME LDP experiment`
- installer: `tools/diagnostics/Apply-ARM64RNameLdp.py`

Compile-only repair:
- `fc330d1c7c29e68042208337ac6e46eb21c69421`
- fixed literal `\t` produced by a Python raw triple-quoted helper string
- optimization scope unchanged

Validated Test CI:
- run `34591462835`
- job `103237476096`
- **SUCCESS**
- artifact `cemu-arm64-test`
- artifact ID `10262500252`
- digest `sha256:7fb8e3f213818d4f0cc46067bd02ff6cd1fd4be37553564e9105a111f037d8fe`

## P1 SEMANTICS — CORRECT DEFINITION

Ignore the stale post-failure handoff text that described non-GPR 64-bit/+8-byte pairs such as LR+CTR or XER+temporaryFPR. That was a documentation error.

Actual implementation:
- only `PPCREC_IML_TYPE_R_NAME`
- IML base format `I64`
- only guest GPR names `R0..R31`
- scan a contiguous `R_NAME` run
- pair guest GPR `n` with `n+1` if each occurs exactly once and host destinations differ
- replace two individual `ldr W...` loads from adjacent `PPCInterpreter_t::gpr[]` uint32 fields with one `ldp W...,W...`
- unmatched GPR and all non-GPR `R_NAME` lowering remain unchanged

## STATIC/RUNTIME VERIFY — PASS

Target entry:
- `0x0420CB80`

Enterable state-restore segment:
- `ppc=0x00000000`
- `enter=0x0420CB80`

Observed pairs:
- `r3+r4`
- `r5+r6`
- `r24+r25`
- `r26+r27`
- `r28+r29`
- `r30+r31`

Runtime diagnostic:
- `pairs=6`
- `native_bytes_saved=24`

Acceptance:
- runtime gate active: PASS
- six pair loads emitted: PASS
- native code-size reduction 24 bytes: PASS
- unrelated non-GPR lowering preserved: PASS
- final JUMP retained: PASS
- BOTW stable-gameplay smoke: PASS

## CONTROLLED PERFORMANCE RESULT — NOT REPEATABLE

Primary comparison window for all runs:
- `t=70..260s`
- 20 ten-second windows per run

### Pair 1 — BASELINE -> CANDIDATE

| metric | BASELINE | CANDIDATE | delta |
|---|---:|---:|---:|
| avg FPS | 49.66745 | 50.76435 | **+2.2085%** |
| avg frame time | 20.13760 ms | 19.70055 ms | **-2.1703%** |
| mean p99 | 22.25870 ms | 21.52095 ms | **-3.3144%** |
| mean 1% low | 45.10415 FPS | 46.49985 FPS | **+3.0944%** |
| barriers/frame | 203.99550 | 200.17105 | -1.8748% |
| renderpasses/frame | 287.09810 | 283.18290 | -1.3637% |

Candidate won 19/20 aligned FPS windows. This initially looked positive.

### Pair 2 — CANDIDATE -> BASELINE

| metric | BASELINE | CANDIDATE | delta |
|---|---:|---:|---:|
| avg FPS | 49.90825 | 48.12405 | **-3.5750%** |
| avg frame time | 20.03850 ms | 20.78095 ms | **+3.7051%** |
| mean p99 | 21.87960 ms | 23.03175 ms | **+5.2659%** |
| mean 1% low | 45.71635 FPS | 43.58540 FPS | **-4.6612%** |
| barriers/frame | 207.02825 | 200.50005 | -3.1533% |
| renderpasses/frame | 290.03925 | 283.49895 | -2.2550% |

Candidate lost all 20/20 aligned FPS windows. Trimming early/late windows does not remove the negative direction; for example `t=90..260s` is still about `-3.38%` FPS.

### Two-order crossover interpretation

Condition means across the two complete pairs:
- BASELINE avg FPS: `49.78785`
- CANDIDATE avg FPS: `49.44420`
- candidate delta: **-0.6902%**
- avg frame time: **+0.7602%** candidate regression
- mean p99: **+0.9389%** candidate regression
- mean 1% low: **-0.8096%** candidate regression

Execution-period means:
- first run of each pair: `48.89575 FPS`
- second run of each pair: `50.33630 FPS`
- second-run advantage: about **+2.9462%**

This order/period effect is larger than the apparent optimization effect and reverses which preset wins.

## P1 FINAL STATUS

`arm64-rname-ldp` is **NOT a repeatable performance winner** under the current controlled BOTW harness.

Classification:
- correctness/static codegen experiment: PASS
- code-size reduction: REAL
- repeatable FPS improvement: NOT CONFIRMED
- promotion: **DO NOT PROMOTE**
- combination with `arm64-compare-reuse`: **DO NOT COMBINE**
- further P1 reruns: not justified without new evidence or a materially improved benchmark method

Treat P1 as a closed/non-winning performance direction, while preserving the diagnostic evidence that AArch64 pair-load formation itself works.

## BENCHMARK METHOD FINDING

The two-order crossover exposed a strong second-run advantage. Future small-effect experiments must not rely on one BASELINE->CANDIDATE pair.

For future sub-3% candidates, prefer one of:
- a sacrificial preconditioning launch before measured runs, then AB/BA
- an ABBA-style sequence
- at minimum both orderings before calling a result positive

Continue to compare the established `t=70..260s` window unless a documented reason changes it.

## PRESERVED SEPARATE CANDIDATE — ARM64 COMPARE REUSE

`arm64-compare-reuse` remains a separate candidate, not a FIX.

Previous one-order result:
- baseline `52.09095 FPS`
- candidate `52.96810 FPS`
- `+1.6839%`

Because P1 exposed a strong order effect, compare-reuse also requires a fresh order-balanced revalidation before any promotion.

## CURRENT NEXT ACTION

P1 is resolved as non-winning for performance. Do not spend another run on it now.

Return to the next evidence-backed hotspot:
- guest `0x02A281A0`
- mapped native entry starts with branch/thunk-like words `17ffff66 d503201f`

Next task:
1. fetch actual Test branch HEAD/source
2. use the existing report-only JIT diagnostics
3. decode/follow the first AArch64 `B imm26`
4. dump the actual branch target body
5. correlate that body to guest block/IML
6. identify one concrete redundant code-generation pattern before writing any new optimization

Do not start by writing a behavior-changing patch. Do not touch `main`, Release, or Diagnostics.
