# DEBUG HISTORY APPEND — 2026-08-29 Query Comparison

This file is an append-only shard for the latest Bayonetta 2 / XCX query-consumption experiment. The main `DEBUG_HISTORY.md` remains preserved; do not delete or overwrite earlier history.

## Build

Branch: `diag-bayo2-xcx-query-consumption`

Runtime HEAD:
`a9e731b1761d12eff97916108b11b19100e3b43d`

Workflow:
`Cemu ARM64 Bayo2 XCX Query Consumption Trace`

Run:
`33167161105` — SUCCESS

Job:
`98835203694`

Behavior:
observation only. Existing XCX workaround and query semantics unchanged.

## XCX JP

Log:
`log(20260828-120900).txt`

Title:
`00050000-10116100`, v48

Result:
- GPU occlusion query `type=2` only
- sampled query begin/end counter >= 75000
- both completed zero and nonzero results
- sampled point: `FINISH_ZERO n=41000 total=70849 nonzero=29849`
- no exported `GX2QueryGetOcclusionResult()` markers
- no exported conditional-render API markers

Conclusion:
XCX's GPU-query producer path is active, but the actual consumer is still unresolved. Instrument low-level `IT_SET_PREDICATION` before changing behavior.

## Bayonetta 2 JP

Log:
`log(20260828-121022).txt`

Title:
`00050000-1011B900`, v1

Result:
- CPU occlusion query `type=0` only
- sampled begin/end counter >= 32000
- heavy CPU `GX2QueryGetOcclusionResult()` consumption
- sampled point: `GET_READY_ZERO n=31000 calls=31211 nonzero=211`
- finish sampled point: `FINISH_ZERO n=32000 total=32211 nonzero=211`
- `GET_NOT_READY` not observed
- sampled same-pointer ordering showed FINISH before GET; no sampled premature GET-before-FINISH case

Conclusion:
The provisional `late GPU result -> default zero -> Bayonetta hides object` theory is strongly weakened for this captured CPU-query path. Do not globally force completed zero results visible without object/frame correlation.

## Comparison

XCX and Bayonetta 2 use different observed paths:
- XCX = GPU query type2, no exported CPU GET
- Bayo2 = CPU query type0, heavy ready result GET

XCX historical query workaround is not evidence that Bayonetta has the same root cause.

Full analysis:
`QUERY_COMPARE_ANALYSIS_20260829.md`

Current next action:
- XCX: observation-only `IT_SET_PREDICATION` trace
- Bayo2: query pointer/result transition correlation with frame/draw/flicker
- no behavior A/B until a concrete wrong visibility decision is observed
