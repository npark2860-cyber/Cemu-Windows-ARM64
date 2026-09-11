# DEBUG HISTORY — 2026-09-10~11 ARM64 JIT performance work

## Scope

Windows ARM64 / Snapdragon X Elite / Adreno X1-85에서 BOTW의 host/JIT 병목을 실제 측정으로 좁히고, 한 변수씩 성능 최적화 가능성을 검증한다.

Branch:
- `runtime-experiments-arm64`

## Benchmark harness

`perf-log` records 10-second windows:
- average FPS
- average frame time
- p99 frame time
- approximate 1% low
- Vulkan barriers/frame
- renderpasses/frame

Primary scene protocol:
- same save/location/camera
- static scene
- same graphics/FPS++ settings
- fixed weather
- restart Cemu per preset
- compare `t=70..260s`

## Closed / non-winning historical directions

Do not repeat without new evidence:
- timer UDIV64
- no-extra-fence
- ARM64 serialize
- skip WAW barrier
- skip RT-load barrier
- force render-pass reuse
- ARM64 NEON texture hash
- historical compare/branch fusion
- historical direct dispatch

Barrier/render-pass reductions alone are not performance proof.

## Host/PPC profiling

Important guest samples from the established RUNNING-only profile:
- `0x0420CB80` — 5.56%
- `0x02A281A0` — 4.12%
- `0x03B84854` — 3.68%
- `0x0399B4DC` — 1.77%

The PPC profiler outer sampling cadence is 10 ms. The earlier 1 ms cadence materially perturbed FPS and must not be restored casually.

## ARM64 consecutive compare reuse

Experiment:
- `arm64-compare-reuse`

Validated CI:
- run `34558962681` — SUCCESS

Static evidence:
- repeated identical compares at `0x03B84854` were reduced so one compare feeds multiple condition-result materializations

One-order controlled result:

| metric | BASELINE | CANDIDATE | delta |
|---|---:|---:|---:|
| avg FPS | 52.09095 | 52.96810 | +1.6839% |
| avg frame time | 19.1998 ms | 18.8834 ms | -1.6479% |
| mean p99 | 23.6361 ms | 22.7896 ms | -3.5814% |
| mean 1% low | 42.4818 FPS | 43.8995 FPS | +3.3372% |

Status:
- code reduction confirmed
- preserve as candidate
- **not a FIX**
- because later P1 work exposed a strong run-order effect, compare-reuse also requires order-balanced revalidation before promotion

## `0x0420CB80` targeted diagnostics

Relevant diagnostics correlated IML/RA/native offsets at the hot entry path.

Important correction:
- pre-P1 repository history did **not** establish the later stale handoff claim about non-GPR 64-bit LR+CTR / XER+temporaryFPR pairs
- those claims were documentation error and must not be resurrected as captured evidence

## P1 — ARM64 R_NAME GPR LDP

Experiment:
- `arm64-rname-ldp`

Implementation:
- `f929fa8007d6ef17f90a3c166b5d248d2ee30e3d`
- `perf: add ARM64 R_NAME LDP experiment`

Actual semantics:
- only `PPCREC_IML_TYPE_R_NAME`
- IML base format `I64`
- only guest GPR names `R0..R31`
- contiguous `R_NAME` run
- pair guest GPR `n` with `n+1` when each appears exactly once and host destinations differ
- emit one `LDP Wreg,Wreg` from adjacent `PPCInterpreter_t::gpr[]` uint32 fields
- unmatched GPR/non-GPR operations retain existing lowering

### Initial CI failure

Failed run:
- `34576700718`
- job `103190682420`

Compiler diagnostic:
- generated C++ contained literal `\t`
- repeated `expected expression` errors in `BackendAArch64.cpp`

Root cause:
- Python raw triple-quoted helper string preserved `\t`

Compile-only repair:
- `fc330d1c7c29e68042208337ac6e46eb21c69421`
- removed raw-string prefix only
- optimization scope unchanged

Green Test CI:
- run `34591462835`
- job `103237476096`
- SUCCESS
- artifact `cemu-arm64-test`
- artifact ID `10262500252`
- digest `sha256:7fb8e3f213818d4f0cc46067bd02ff6cd1fd4be37553564e9105a111f037d8fe`

## P1 runtime VERIFY

Target entry:
- `0x0420CB80`

Enterable state-restore segment:
- `ppc=0x00000000`
- `enter=0x0420CB80`

Observed pairs:
- r3+r4
- r5+r6
- r24+r25
- r26+r27
- r28+r29
- r30+r31

Diagnostic:

```text
[ARM64_RNAME_LDP] ppc=0x00000000 enter=0x0420cb80 pairs=6 native_bytes_saved=24
```

Acceptance:
- runtime gate active: PASS
- six pair emissions: PASS
- 24-byte native size saving: PASS
- unrelated CR/XER.SO loads preserved: PASS
- final JUMP retained: PASS
- BOTW stable-gameplay smoke: PASS

So pair-load generation is technically valid and does reduce generated code size.

## P1 performance pair 1 — BASELINE -> CANDIDATE

Primary window:
- `t=70..260s`
- 20 samples each

| metric | BASELINE | CANDIDATE | delta |
|---|---:|---:|---:|
| avg FPS | 49.66745 | 50.76435 | **+2.2085%** |
| avg frame time | 20.13760 ms | 19.70055 ms | **-2.1703%** |
| mean p99 | 22.25870 ms | 21.52095 ms | **-3.3144%** |
| mean 1% low | 45.10415 FPS | 46.49985 FPS | **+3.0944%** |
| barriers/frame | 203.99550 | 200.17105 | -1.8748% |
| renderpasses/frame | 287.09810 | 283.18290 | -1.3637% |

Candidate won 19/20 aligned FPS windows. Trimming the baseline drop at `t=250..260s` still left about +1.7~1.8% candidate advantage.

At this point P1 was provisionally classified positive and a reverse-order confirmation was required.

## P1 performance pair 2 — CANDIDATE -> BASELINE

Primary window:
- `t=70..260s`
- 20 samples each

| metric | BASELINE | CANDIDATE | delta |
|---|---:|---:|---:|
| avg FPS | 49.90825 | 48.12405 | **-3.5750%** |
| avg frame time | 20.03850 ms | 20.78095 ms | **+3.7051%** |
| mean p99 | 21.87960 ms | 23.03175 ms | **+5.2659%** |
| mean 1% low | 45.71635 FPS | 43.58540 FPS | **-4.6612%** |
| barriers/frame | 207.02825 | 200.50005 | -3.1533% |
| renderpasses/frame | 290.03925 | 283.49895 | -2.2550% |

Candidate lost 20/20 aligned FPS windows.

This is not an edge-window artifact:
- `t=90..260s`: candidate remains about **-3.38%**
- `t=100..260s`: about **-3.40%**
- `t=120..260s`: about **-3.44%**
- `t=160..260s`: about **-3.76%**

## P1 two-order crossover interpretation

Condition means across both complete pairs:

| metric | BASELINE mean | CANDIDATE mean | candidate delta |
|---|---:|---:|---:|
| avg FPS | 49.78785 | 49.44420 | **-0.6902%** |
| avg frame time | 20.08805 ms | 20.24075 ms | **+0.7602%** |
| mean p99 | 22.06915 ms | 22.27635 ms | **+0.9389%** |
| mean 1% low | 45.41025 FPS | 45.04263 FPS | **-0.8096%** |
| barriers/frame | 205.51188 | 200.33555 | -2.5187% |
| renderpasses/frame | 288.56868 | 283.34092 | -1.8116% |

Execution-period means:
- first run of each pair: `48.89575 FPS`
- second run of each pair: `50.33630 FPS`
- second-run advantage: **+2.9462%**

Interpretation:
- whichever preset ran second won strongly
- the period/order effect is larger than the alleged LDP performance effect
- two-order condition mean is slightly negative for candidate
- lower barriers/renderpasses on candidate do not translate into a repeatable FPS win and must not be treated as proof

## P1 final decision

`arm64-rname-ldp` is **closed as a non-winning performance optimization** for the current BOTW harness.

Keep the following distinction:
- static/correctness validity: PASS
- generated-code reduction: REAL
- repeatable runtime performance gain: NOT CONFIRMED
- promotion: DO NOT PROMOTE
- combination with compare-reuse: DO NOT COMBINE
- further P1 runtime repetitions: not justified without new evidence or a materially improved benchmark protocol

## Benchmark protocol finding

The crossover exposed a significant period bias that can create false positives for small effects.

For future sub-3% candidates:
- never classify from one A->B pair alone
- prefer a sacrificial preconditioning launch before measured runs plus AB/BA
- or use ABBA
- at minimum collect both orderings
- continue the established `t=70..260s` comparison unless a documented reason changes it

## Next target — `0x02A281A0`

Mapped entry begins with:

```text
17ffff66 d503201f
```

Treat it as branch/thunk-like. The next task is report-only analysis:
1. decode/follow the first AArch64 `B imm26`
2. dump at least 128 bytes from the actual branch target
3. correlate the target body to guest block/IML
4. identify one concrete redundant code-generation pattern before any behavior-changing experiment

Do not start by writing optimization code.
