# DEBUG HISTORY — 2026-09-12 ARM64 compare-reuse balanced revalidation

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Branch: `runtime-experiments-arm64`

Experiment: `arm64-compare-reuse`

## Background

A previous single-order controlled run reported:
- baseline: `52.09095 FPS`
- candidate: `52.96810 FPS`
- candidate: `+1.6839%`

Later P1 work exposed significant run-order / period bias, so the prior result could not be treated as a promotion-quality result.

This revalidation used the same current Test binary for baseline and candidate and changed only the experiment token.

## Protocol

Order:
1. BASELINE — run `20260912-021452`
2. CANDIDATE — run `20260912-021948`
3. CANDIDATE — run `20260912-022444`
4. BASELINE — run `20260912-022927`

Primary window:
- `t=70..260s`
- 20 samples per run

Baseline token set:
- `perf-log`

Candidate token set:
- `arm64-compare-reuse,perf-log`

## Pair 1 — BASELINE -> CANDIDATE

| metric | BASELINE | CANDIDATE | candidate delta |
|---|---:|---:|---:|
| avg FPS | 53.68875 | 52.78065 | **-1.6914%** |
| avg frame time | 18.63005 ms | 18.95010 ms | **+1.7179%** |
| mean p99 | 24.07160 ms | 24.21065 ms | **+0.5777%** |
| mean 1% low | 42.20925 FPS | 41.97330 FPS | **-0.5590%** |
| barriers/frame | 203.26165 | 201.60050 | -0.8172% |
| renderpasses/frame | 286.31150 | 284.47955 | -0.6398% |

Candidate won only `5/20` aligned FPS windows.

## Pair 2 — CANDIDATE -> BASELINE

| metric | BASELINE | CANDIDATE | candidate delta |
|---|---:|---:|---:|
| avg FPS | 52.61120 | 51.58485 | **-1.9508%** |
| avg frame time | 19.00880 ms | 19.39260 ms | **+2.0191%** |
| mean p99 | 23.78335 ms | 24.67730 ms | **+3.7587%** |
| mean 1% low | 42.11415 FPS | 41.35810 FPS | **-1.7952%** |
| barriers/frame | 203.14795 | 211.63055 | +4.1756% |
| renderpasses/frame | 286.25480 | 294.88135 | +3.0136% |

Candidate again won only `5/20` aligned FPS windows.

Pair 2 contains a visible candidate-side disturbance around `t=160..200s`, but it does not determine the verdict by itself:
- excluding `t=160..200s`, candidate remains about `-0.88%` FPS
- using `t=90..260s`, candidate remains about `-1.91%` FPS
- pair 1 independently remains negative over the same benchmark window

## Two-order condition means

| metric | BASELINE mean | CANDIDATE mean | candidate delta |
|---|---:|---:|---:|
| avg FPS | 53.14998 | 52.18275 | **-1.8198%** |
| avg frame time | 18.81943 ms | 19.17135 ms | **+1.8700%** |
| mean p99 | 23.92748 ms | 24.44398 ms | **+2.1586%** |
| mean 1% low | 42.16170 FPS | 41.66570 FPS | **-1.1764%** |
| barriers/frame | 203.20480 | 206.61553 | +1.6785% |
| renderpasses/frame | 286.28315 | 289.68045 | +1.1867% |

## Execution-position check

First run of each pair:
- BASELINE pair 1 + CANDIDATE pair 2 = `52.63680 FPS`

Second run of each pair:
- CANDIDATE pair 1 + BASELINE pair 2 = `52.69593 FPS`

Second-run delta:
- about `+0.1123%`

Therefore this result is not explained by the strong second-run effect that invalidated P1. The execution-position effect is near zero here while the candidate loses in both orderings.

## Final decision

`arm64-compare-reuse` is CLOSED as a non-winning performance optimization for the current BOTW harness.

Keep the distinction:
- generated-code simplification: REAL
- earlier one-order `+1.6839%`: treated as a false positive under the stronger protocol
- balanced runtime result: candidate slower in both orderings
- two-order FPS delta: **-1.8198%**
- promotion: DO NOT PROMOTE
- combination with other closed candidates: DO NOT COMBINE

No further compare-reuse performance repetitions are justified without materially new evidence or a materially improved benchmark method.

## Next direction

The three recent AArch64 JIT code-reduction experiments (`arm64-rname-ldp`, `arm64-cyclecheck-reuse`, `arm64-compare-reuse`) all produced real code-generation changes but failed promotion-quality balanced performance validation.

Next work should return to measurement before another behavior change:
1. reprofile current JIT / host hotspots using report-only diagnostics, or
2. move to host/Vulkan CPU-side profiling if no concrete JIT redundancy dominates.

Do not infer performance benefit from instruction-count or code-size reduction alone.
