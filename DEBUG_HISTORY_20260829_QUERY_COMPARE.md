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
XCX's GPU-query producer path is active, but the actual consumer remained unresolved after this first capture. Low-level `IT_SET_PREDICATION` was selected as the next observation boundary before any behavior change.

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

---

## 2026-08-29 — XCX raw `IT_SET_PREDICATION` observation

### Static source fact before runtime test

`LatteCP_itSetPredication()` currently:
- parses `physQueryInfo` and `flags`
- toggles only the global `conditionalRenderActive` boolean
- does not read query result memory
- does not evaluate zero/nonzero visibility
- does not call a renderer conditional-render/predication implementation
- computes `pixelsMustPassFlag` and `dontWaitFlag` but does not use them

Also noted:
- producer encodes `dontWait` at bit 19
- current consumer-side local decode uses `(flags >> 1) & 19`, which is not a bit-19 extraction
- this decode is currently unused, therefore it was not changed in the observation build

### Observation build

Branch:
`diag-xcx-predication-consumption`

Base:
`a9e731b1761d12eff97916108b11b19100e3b43d`

Runtime HEAD:
`e6fac132fff290ee3d54a58d4e8e7c03f391f25e`

Workflow:
`Cemu ARM64 XCX Predication Consumption Trace`

Run:
`33227559831` — SUCCESS

Behavior:
- observation only
- existing `[QUERY_COMPARE]` instrumentation preserved
- XCX `0x100000` GPU-query seed/workaround preserved
- no query result, lifetime, bookkeeping, renderer visibility, or return behavior changed

New marker:
`[XCX_PREDICATION]`

Trace was designed to record:
- packet source (`toplevel` vs `indirect`)
- physical and virtual-correlated query address
- raw flags
- `queryTypeFlag`
- `pixelsMustPass`
- correct log-only bit-19 `dontWait`
- existing local decode value
- raw query start/end values and derived delta/high-bit state when safe

### Runtime input

Uploaded archive:
`log.zip` containing `log.txt`

Runtime identity:
- first line: `Init Cemu e6fac13`
- XCX JP title `00050000-10116100`
- version `v48`
- Adreno X1-85
- Vulkan 1.3
- driver build `f22d572733`

This confirms the new predication observation binary was actually used.

### Runtime result

Marker counts:
- `[XCX_PREDICATION]` = **0**
- `[QUERY_COMPARE] CONDITIONAL_BEGIN` = **0**
- `[QUERY_COMPARE] CONDITIONAL_END` = **0**
- `[QUERY_COMPARE] GET_*` = **0**

At the same time GPU query traffic remained extremely active:
- sampled `API_BEGIN` / `API_END` reached at least `n=89000`
- observed query type = **2 only**
- title on query records = XCX JP only
- latest sampled zero counter point: `FINISH_ZERO n=61000 total=85597 nonzero=24597`
  - at that sampled instant: about 71.3% completed zero / 28.7% completed nonzero

Therefore the absence of predication markers is not because the query producer path was inactive.

### Query-slot reuse observation

The first 128 completed query records are unsampled/full due to the logger's initial window.

Within those records:
- 16 query pointers form a contiguous pool
- range begins at `27998b80`
- each slot is exactly `0x40` bytes apart, matching `sizeof(GX2Query) == 0x40`
- 13 of the 16 sampled slots produced both zero and nonzero results across reuse

Examples:
- `27998bc0`: repeated zero, later nonzero `2449511`, then zero again
- `27998f00`: zero -> nonzero `2461251` -> zero -> nonzero again
- `27998e40`: zero -> `52565` -> zero -> later nonzero

Thus XCX GPU query slots are actively reused and their completed visibility sample values genuinely change over time. A zero value cannot be classified globally as merely an uninitialized default.

### Confirmed conclusion

For this captured XCX gameplay session:

1. XCX emits very heavy GPU occlusion query traffic.
2. It does not consume results through exported `GX2QueryGetOcclusionResult()`.
3. It does not call exported conditional-render APIs.
4. **No raw `IT_SET_PREDICATION` packet reached `LatteCP_itSetPredication()` at all**, including top-level and indirect/display-list dispatch paths instrumented by the observation build.
5. Therefore the previously open hypothesis that XCX bypasses the exported API and consumes its visibility queries through low-level PM4 `IT_SET_PREDICATION` is **closed for this capture**.

Remaining XCX possibilities:
- direct guest-code reads of the GX2Query memory/result fields
- query traffic whose consumer is elsewhere/not visibility-driving in the captured path

Do not implement predication behavior or change the `0x100000` workaround based on this negative result.

## Updated next action

No behavior-changing A/B yet.

Next high-value target for the Bayonetta primary investigation:
- correlate Bayo2 CPU query pointer/result generations with GPU frame/draw ranges
- preserve pointer reuse by assigning/querying generations rather than treating a pointer as one permanent object
- classify completed result transitions (`0→0`, `0→nonzero`, `nonzero→0`, `nonzero→nonzero`)
- use an actual command-stream frame boundary rather than `LatteGPUState.flipCounter`
- only after concrete wrong visibility correlation consider one behavior A/B

Do not repeat:
- nested/duplicate query bookkeeping experiment
- f544 coherence experiments
- XCX `IT_SET_PREDICATION` trace
- global Bayo2 ready-zero force-visible
