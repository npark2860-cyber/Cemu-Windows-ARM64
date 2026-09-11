# NEXT ACTION — reprofile current ARM64 bottlenecks

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Branch: `runtime-experiments-arm64`

## CLOSED — `arm64-rname-ldp`

- static/correctness: PASS
- native code-size reduction: REAL
- balanced performance win: NOT CONFIRMED
- two-order condition mean: candidate `-0.6902%` FPS
- promotion: DO NOT PROMOTE
- do not combine

## CLOSED — `arm64-cyclecheck-reuse`

- exact `COUNT_CYCLES -> CYCLE_CHECK` redundancy: PROVEN
- runtime native reduction: `CYCLE_CHECK` 12B -> 8B
- BOTW correctness smoke: PASS
- balanced performance:
  - pair 1 candidate: `-2.3571%` FPS
  - pair 2 candidate: `-0.5587%` FPS
  - two-order candidate: `-1.4623%` FPS
- promotion: DO NOT PROMOTE
- do not combine

Full record:
- `DEBUG_HISTORY_20260912_ARM64_CYCLECHECK_REUSE.md`

## CLOSED — `arm64-compare-reuse`

Earlier one-order result:
- baseline `52.09095 FPS`
- candidate `52.96810 FPS`
- candidate `+1.6839%`

That result is now invalidated by balanced revalidation.

Balanced protocol:
- fixed BOTW scene
- same current Test binary
- order `BASELINE -> CANDIDATE -> CANDIDATE -> BASELINE`
- primary window `t=70..260s`
- 20 samples per run

Pair 1, BASELINE -> CANDIDATE:
- FPS: `53.68875 -> 52.78065` = **-1.6914%** candidate
- avg frame time: **+1.7179%** candidate
- p99: **+0.5777%** candidate
- 1% low: **-0.5590%** candidate
- candidate won only `5/20` aligned FPS windows

Pair 2, CANDIDATE -> BASELINE:
- FPS: `52.61120 baseline` vs `51.58485 candidate` = **-1.9508%** candidate
- avg frame time: **+2.0191%** candidate
- p99: **+3.7587%** candidate
- 1% low: **-1.7952%** candidate
- candidate won only `5/20` aligned FPS windows

Two-order condition means:
- baseline: `53.14998 FPS`
- candidate: `52.18275 FPS`
- candidate delta: **-1.8198%**
- avg frame time delta: **+1.8700%**
- p99 delta: **+2.1586%**
- 1% low delta: **-1.1764%**

Execution-position check:
- first run of each pair: `52.63680 FPS`
- second run of each pair: `52.69593 FPS`
- second-run delta: only about `+0.1123%`

Interpretation:
- this is not the strong second-run bias seen in P1
- candidate loses in both orderings
- the earlier `+1.6839%` one-order result is treated as a false positive under the strengthened protocol
- generated-code simplification remains real, but runtime benefit is absent

Decision:
- `arm64-compare-reuse` CLOSED
- DO NOT PROMOTE
- DO NOT COMBINE
- do not repeat without materially new evidence

Full record:
- `DEBUG_HISTORY_20260912_ARM64_COMPARE_REUSE_REVALIDATION.md`

## CURRENT LESSON

Three recent AArch64 JIT code-reduction directions all produced technically valid generated-code changes but failed promotion-quality balanced performance validation:
- `arm64-rname-ldp`
- `arm64-cyclecheck-reuse`
- `arm64-compare-reuse`

Therefore generated-code instruction count / byte count must not be used as a proxy for real performance.

## NEXT ACTION — REPORT-ONLY REPROFILING

Do not start another behavior-changing optimization yet.

First reprofile the current baseline/Test runtime and identify the next bottleneck from measured evidence.

Priority:
1. current JIT/native hotspot distribution under the established BOTW fixed scene
2. determine whether the previous hot guest entries remain dominant after current source composition
3. for the hottest actionable entry, capture actual native target body and correlate to IML before proposing any change
4. if no concrete JIT redundancy dominates, move to host/Vulkan CPU-side profiling

Host/Vulkan fallback targets:
- descriptor allocation/update/bind CPU cost
- command submission frequency and submit-side CPU cost
- queue/fence wait distribution
- upload/staging/memory command-path cost
- CPU-side Vulkan object/cache lookup pressure

Rules:
- report-only diagnostics first
- one behavior variable at a time only after a new redundancy/bottleneck is proven
- keep primary BOTW performance window `t=70..260s`
- use order-balanced validation for all sub-3% claims
- barriers/renderpasses are supporting metrics only
- do not touch `main`, Release, or Diagnostics
- do not reopen closed candidates without new evidence
