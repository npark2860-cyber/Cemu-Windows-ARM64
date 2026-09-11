# DEBUG HISTORY — 2026-09-12 ARM64 cycle-check TEMP_GPR1 reuse

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Branch: `runtime-experiments-arm64`

## Scope

Validate the evidence-derived AArch64 JIT experiment `arm64-cyclecheck-reuse`.

The hypothesis was narrow: when `PPCREC_IML_MACRO_COUNT_CYCLES` is immediately followed by `PPCREC_IML_TYPE_CJUMP_CYCLE_CHECK` in the same segment, the cycle check can reuse the decremented `remainingCycles` value already held in `TEMP_GPR1.WReg` instead of reloading it from `PPCInterpreter_t`.

## Structural/runtime proof

Implementation/composition commit:
- `f311e5e2644f71dea03e680819e3399ad96a37f3`

Validated Test CI:
- run `34618642312`
- job `103326770490`
- SUCCESS
- artifact `cemu-arm64-test`
- artifact ID `10273002162`
- digest `sha256:9378dbac17b2457aa2f1e0f76bdf301c4c6fb4ae65f3785af9a52a3eb2284da9`

Runtime VERIFY confirmed both targeted hot blocks:
- `0x0420CB80`: `COUNT_CYCLES` 12 bytes, reuse marker present, `CYCLE_CHECK` 8 bytes
- `0x02A281A0`: `COUNT_CYCLES` 12 bytes, reuse marker present, `CYCLE_CHECK` 8 bytes

Therefore the candidate removes exactly one 4-byte AArch64 `LDR` per qualifying pair while preserving the existing branch test.

Static/runtime correctness result:
- adjacency/liveness proof: PASS
- generated-code reduction: REAL
- BOTW gameplay smoke: PASS

## Order-balanced BOTW performance test

Protocol:
- same fixed BOTW scene/settings/weather
- restart Cemu per preset
- 10-second samples
- primary window `t=70..260s`
- order `BASELINE -> CANDIDATE -> CANDIDATE -> BASELINE`
- 20 samples per measured run

### Pair 1 — BASELINE -> CANDIDATE

| metric | BASELINE | CANDIDATE | candidate delta |
|---|---:|---:|---:|
| avg FPS | 53.48815 | 52.22740 | **-2.3571%** |
| avg frame time | 18.69960 ms | 19.14780 ms | **+2.3968%** |
| mean p99 | 23.26915 ms | 23.16470 ms | -0.4489% |
| mean 1% low | 42.98695 FPS | 43.21690 FPS | +0.5349% |
| barriers/frame | 203.11070 | 203.12110 | +0.0051% |
| renderpasses/frame | 286.07515 | 286.18075 | +0.0369% |

Aligned FPS windows:
- candidate wins: 1/20
- candidate loses: 19/20

### Pair 2 — CANDIDATE -> BASELINE

| metric | BASELINE | CANDIDATE | candidate delta |
|---|---:|---:|---:|
| avg FPS | 52.96495 | 52.66905 | **-0.5587%** |
| avg frame time | 18.88255 ms | 18.98710 ms | **+0.5537%** |
| mean p99 | 23.67365 ms | 24.29035 ms | **+2.6050%** |
| mean 1% low | 42.37405 FPS | 41.79210 FPS | **-1.3734%** |
| barriers/frame | 202.80020 | 202.34185 | -0.2260% |
| renderpasses/frame | 285.89835 | 285.28900 | -0.2131% |

Aligned FPS windows:
- candidate wins: 7/20
- candidate loses: 13/20

## Two-order condition means

| metric | BASELINE mean | CANDIDATE mean | candidate delta |
|---|---:|---:|---:|
| avg FPS | 53.22655 | 52.44823 | **-1.4623%** |
| avg frame time | 18.79108 ms | 19.06745 ms | **+1.4708%** |
| mean p99 | 23.47140 ms | 23.72753 ms | **+1.0912%** |
| mean 1% low | 42.68050 FPS | 42.50450 FPS | **-0.4124%** |
| barriers/frame | 202.95545 | 202.73148 | -0.1104% |
| renderpasses/frame | 285.98675 | 285.73488 | -0.0881% |

Execution-position means:
- first run of each pair: `53.07860 FPS`
- second run of each pair: `52.59618 FPS`
- second-run delta: `-0.9089%`

Unlike the earlier R_NAME LDP crossover, there is no pattern where the candidate merely loses because it occupied one unfavorable execution position. The candidate is slower in both orderings.

Supporting counters are essentially unchanged and do not explain a positive performance effect.

## Final decision

`arm64-cyclecheck-reuse` is **CLOSED as a non-winning performance optimization** for the current BOTW harness.

Keep the distinction:
- semantic safety / structural validity: PASS
- native code-size reduction: REAL
- runtime correctness smoke: PASS
- repeatable performance gain: NO
- two-order FPS mean: candidate **-1.4623%**
- promotion: DO NOT PROMOTE
- combination with other candidates: DO NOT COMBINE
- further repetitions: not justified without new evidence or a materially different benchmark protocol

The optimization is technically valid but not performance-useful on the measured workload.

## Next action

Return to the preserved `arm64-compare-reuse` candidate and perform the missing order-balanced validation before considering any promotion. Its earlier +1.6839% result was one-order only and predates the strengthened benchmark protocol.

Do not reopen `arm64-rname-ldp` or `arm64-cyclecheck-reuse` without new evidence.
Do not touch `main`, Release, or Diagnostics.
