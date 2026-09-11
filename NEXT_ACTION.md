# NEXT ACTION — revalidate `arm64-compare-reuse`

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Branch: `runtime-experiments-arm64`

## CLOSED — `arm64-rname-ldp`

Status remains unchanged:
- static/correctness: PASS
- native code-size reduction: REAL
- repeatable performance gain: NOT CONFIRMED
- promotion: DO NOT PROMOTE
- do not combine with other candidates

## CLOSED — `arm64-cyclecheck-reuse`

Implementation/composition:
- `f311e5e2644f71dea03e680819e3399ad96a37f3`

Validated Test CI:
- run `34618642312`
- job `103326770490`
- SUCCESS
- artifact ID `10273002162`

Runtime VERIFY:
- `0x0420CB80`: `COUNT_CYCLES` 12B, reuse marker present, `CYCLE_CHECK` 8B
- `0x02A281A0`: `COUNT_CYCLES` 12B, reuse marker present, `CYCLE_CHECK` 8B
- structural safety: PASS
- BOTW gameplay smoke: PASS
- static saving: one 4-byte AArch64 `LDR` removed per qualifying pair

Order-balanced performance protocol:
- fixed BOTW scene
- primary window `t=70..260s`
- order `BASELINE -> CANDIDATE -> CANDIDATE -> BASELINE`
- 20 samples per run

Pair 1, BASELINE -> CANDIDATE:
- FPS: `53.48815 -> 52.22740` = **-2.3571%**
- avg frame time: `18.69960 -> 19.14780 ms` = **+2.3968%**
- p99: `23.26915 -> 23.16470 ms` = `-0.4489%`
- 1% low: `42.98695 -> 43.21690 FPS` = `+0.5349%`
- candidate lost 19/20 aligned FPS windows

Pair 2, CANDIDATE -> BASELINE:
- FPS: `52.96495 baseline` vs `52.66905 candidate` = **-0.5587%** candidate
- avg frame time: `18.88255 baseline` vs `18.98710 ms candidate` = **+0.5537%** candidate
- p99: `23.67365 baseline` vs `24.29035 ms candidate` = **+2.6050%** candidate
- 1% low: `42.37405 baseline` vs `41.79210 FPS candidate` = **-1.3734%** candidate
- candidate lost 13/20 aligned FPS windows

Two-order condition means:
- baseline: `53.22655 FPS`
- candidate: `52.44823 FPS`
- candidate delta: **-1.4623%**
- avg frame time delta: **+1.4708%**
- p99 delta: **+1.0912%**
- 1% low delta: **-0.4124%**

Execution-position check:
- first run of each pair: `53.07860 FPS`
- second run of each pair: `52.59618 FPS`
- second-run delta: `-0.9089%`

Conclusion:
- the generated-code reduction is real
- the candidate is slower in both orderings
- this is not a promotion candidate
- `arm64-cyclecheck-reuse` is CLOSED / DO NOT PROMOTE / DO NOT COMBINE

Full record:
- `DEBUG_HISTORY_20260912_ARM64_CYCLECHECK_REUSE.md`

## PRESERVED CANDIDATE — `arm64-compare-reuse`

Previous one-order result:
- baseline `52.09095 FPS`
- candidate `52.96810 FPS`
- candidate `+1.6839%`

Generated-code simplification was confirmed, but this result predates the strengthened order-bias protocol. It is still only a candidate.

## NEXT ACTION

Perform the missing order-balanced revalidation of `arm64-compare-reuse` before starting another JIT behavior experiment.

Protocol:
1. use the same fixed BOTW scene/settings/weather
2. restart Cemu for every run
3. primary comparison window remains `t=70..260s`
4. measure `BASELINE -> COMPARE_REUSE -> COMPARE_REUSE -> BASELINE`
5. keep `arm64-compare-reuse` as the only behavior-changing token
6. record FPS, avg frame time, p99, 1% low; barriers/renderpasses remain supporting only

Promotion requirement:
- candidate must retain a consistent advantage across both orderings
- a sub-3% gain is not sufficient if direction crosses over
- correctness must remain clean

If compare-reuse also fails balanced validation, move to the next evidence-based JIT hotspot or host/Vulkan profiling rather than combining failed/neutral candidates.

Do not reopen `arm64-rname-ldp` or `arm64-cyclecheck-reuse` without new evidence.
Do not touch `main`, Release, or Diagnostics.
