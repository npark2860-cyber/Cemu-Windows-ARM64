# XCX vs Bayonetta 2 Query Consumption Analysis — 2026-08-29

## Purpose

This file preserves the two-title comparison from the observation-only query-consumption build so the next chat can continue without re-reading the full logs from scratch.

Build / branch:
- branch: `diag-bayo2-xcx-query-consumption`
- runtime HEAD: `a9e731b1761d12eff97916108b11b19100e3b43d`
- workflow: `Cemu ARM64 Bayo2 XCX Query Consumption Trace`
- Run: `33167161105` — SUCCESS
- Job: `98835203694`
- behavior: observation only; existing query values, result return, lifetime, XCX workaround unchanged

Trace markers:
- `[QUERY_COMPARE] API_BEGIN / API_END`
- `[QUERY_COMPARE] GET_NOT_READY`
- `[QUERY_COMPARE] GET_READY_ZERO / GET_READY_NONZERO`
- `[QUERY_COMPARE] FINISH_ZERO / FINISH_NONZERO`
- `[QUERY_COMPARE] CONDITIONAL_BEGIN / CONDITIONAL_END`

## Input logs

### Xenoblade Chronicles X JP
- file: `log(20260828-120900).txt`
- runtime title: `00050000-10116100`
- version: v48
- Cemu: `a9e731b`
- Adreno X1-85 / Vulkan 1.3 / driver `f22d572733`

### Bayonetta 2 JP
- file: `log(20260828-121022).txt`
- runtime title: `00050000-1011B900`
- version: v1
- Cemu: `a9e731b`
- same GPU/driver environment

## 1. XCX — confirmed query behavior

Observed API query type:
- `API_BEGIN`: type `2` only = GPU occlusion query
- `API_END`: type `2` only
- sampled counters reached at least `n=75000`

Observed finish results:
- both `FINISH_ZERO` and `FINISH_NONZERO` occur heavily
- one sampled point: `FINISH_ZERO n=41000 total=70849 nonzero=29849`
- therefore completed GPU queries frequently produce both real zero and nonzero sample sums

Not observed in this trace:
- `GET_NOT_READY` = 0 markers
- `GET_READY_ZERO` = 0 markers
- `GET_READY_NONZERO` = 0 markers
- `CONDITIONAL_BEGIN` = 0 markers
- `CONDITIONAL_END` = 0 markers

Interpretation boundary:
- XCX is definitely issuing large numbers of GPU occlusion queries.
- The captured title does not consume them through exported `GX2QueryGetOcclusionResult()`.
- The captured title also did not call the exported `GX2QueryBeginConditionalRender()/EndConditionalRender()` path caught by this trace.
- This does **not** prove query results are unused. A low-level PM4/display-list `IT_SET_PREDICATION` path or direct guest-memory consumption remains possible and was not instrumented by this build.
- Therefore the current XCX flicker cannot be explained or dismissed from this trace alone.

Existing source workaround remains relevant historical context:
- XCX GPU query begin preloads `endValue=0x100000` because old Cemu behavior could leave GPU query results at default zero long enough to hide objects and cause flicker.
- The current log also proves many **completed** XCX GPU queries legitimately finish with `sampleSum=0`; the workaround only addresses the initial/default-zero window, not completed zero results.

## 2. Bayonetta 2 — confirmed query behavior

Observed API query type:
- `API_BEGIN`: type `0` only = CPU occlusion query
- `API_END`: type `0` only
- sampled counters reached at least `n=32000`

CPU result consumption is heavy:
- `GET_READY_ZERO` sampled counter reached at least `n=31000`, with `calls=31211`, `nonzero=211` at that sample
- `GET_READY_NONZERO` also exists
- `GET_NOT_READY` was not observed

Finish results:
- `FINISH_ZERO` sampled counter reached `n=32000`, `total=32211`, `nonzero=211`
- `FINISH_NONZERO` exists and matches nonzero GET results for sampled query pointers

Strong sampled pointer-order result:
- for sampled query pointers where both FINISH and GET markers were present, no `GET_READY_*` was observed before the corresponding FINISH marker
- sampled zero queries matched `FINISH_ZERO -> GET_READY_ZERO`
- sampled nonzero queries matched `FINISH_NONZERO -> GET_READY_NONZERO`

Therefore the earlier provisional hypothesis:
`GPU result is late -> guest still default zero -> Bayonetta consumes premature ready-zero`

is **strongly weakened for the captured Bayo2 CPU-query path**.

In particular:
- CPU query initialization uses `OCPU` not-ready magic.
- `GX2QueryGetOcclusionResult()` returns FALSE while that magic remains.
- the trace observed no `GET_NOT_READY` and many ready-zero reads after actual zero finishes.
- so these zero results should not currently be treated as a simple latency/default-zero artifact.

Important consequence:
- do **not** immediately apply a Bayo2 `force-visible on ready-zero` A/B and call it a timing fix.
- that would overwrite large numbers of apparently legitimate completed zero occlusion results.
- any force-visible experiment must first correlate zero results with the exact flickering object/scene or identify a narrower semantic error.

## 3. XCX vs Bayo2 comparison

The two titles use materially different observed query paths:

### XCX
- GPU occlusion query type 2
- >=75k begin/end in capture
- both completed zero and nonzero results
- no exported CPU GET calls captured
- no exported conditional-render API calls captured
- next missing boundary: low-level `IT_SET_PREDICATION` / direct query-memory consumer

### Bayonetta 2
- CPU occlusion query type 0
- >=32k begin/end in capture
- heavy `GX2QueryGetOcclusionResult()` consumption
- ready-zero dominates captured reads
- no not-ready reads captured
- sampled ready-zero values follow completed FINISH_ZERO, not obvious premature default zero

Conclusion:
- XCX and Bayonetta 2 can both visibly flicker while using different observed query-consumption paths.
- XCX's historical workaround is proof that query timing can produce object flicker in Cemu, but it is **not evidence that Bayonetta 2 has the same mechanism**.
- current data does not justify transplanting the XCX workaround to Bayonetta 2.

## 4. NEXT ANALYSIS — no behavior change yet

1. For XCX, instrument low-level `LatteCP_itSetPredication()` / `IT_SET_PREDICATION`:
   - enable/disable count
   - `physQueryInfo`
   - flags / query type / pixelsMustPass / dontWait
   - raw query memory at predication time if safely readable
   - correlate with XCX GPU query pointers and FINISH_ZERO/NONZERO

2. For Bayonetta 2, do not repeat nested/duplicate query bookkeeping trace. That path was already negative.

3. For Bayonetta 2, determine whether the dominant completed-zero CPU queries are actually visibility/culling decisions for the flickering distant geometry. Prefer observation:
   - query pointer lifecycle
   - result zero/nonzero transition frequency for the same pointer/object slot
   - frame/draw correlation around the visible flicker

4. Only after correlation, design one narrow behavior A/B. Do not globally force all completed zero queries visible.

5. Keep f544 multi-pitch D24 coherence downgraded: seeded correction executed correctly and produced 0 visual improvement.

## 5. Do not repeat

- XCX historical initial-zero workaround is already present; do not add the same workaround again.
- Bayo2 nested/overlapping resume/duplicate bookkeeping experiment is already negative.
- Bayo2 f544 seeded coherence correction is a valid negative A/B.
- Do not use the old destructive unseeded f544 roundtrip.
- Do not call Bayo2 ready-zero a latency bug without new direct evidence.
