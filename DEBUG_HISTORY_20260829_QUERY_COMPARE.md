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

---

## 2026-08-29 — Bayonetta 2 CPU query frame/draw correlation runtime result

### Observation build

Branch:
`diag-bayo2-query-frame-draw-correlation`

Runtime HEAD:
`13c9705e99c23e30f476d3b46d21849b169b9212`

Workflow:
`Cemu ARM64 Bayo2 Query Frame Draw Correlation Trace`

Successful build run:
`33230812891`

Job:
`99043206588`

Artifact:
`cemu-arm64-bayo2-query-frame-draw-correlation`

Behavior:
- observation only
- no query result, culling, visibility, or renderer behavior change
- existing XCX workaround preserved

### Runtime capture A — graphic packs active

Log:
`log(20260829-070041).txt`

Runtime identity:
- `Init Cemu 13c9705`
- Bayonetta 2 JP `00050000-1011B900`, v1
- Adreno X1-85 / Vulkan 1.3 / driver `f22d572733`

This capture unintentionally still had Bayonetta graphic packs active, including Force Maximum LOD.

Final correlation summary:
- GET = **47,775**
- zero = **47,365**
- nonzero = **410**
- `0->NZ` = **383**
- `NZ->0` = **390**
- repeat = **0**
- missingSnapshot = **0**
- overwrittenUnconsumed = **3**
- unique finished/query slots observed = **154**
- result/finish mismatch = **0**

User visual observation:
- severe distant/background geometry flicker.

### Runtime capture B — verified all graphic packs OFF

Log:
`log(20260829-071604).txt`

Runtime identity:
- `Init Cemu 13c9705`
- Bayonetta 2 JP `00050000-1011B900`, v1
- Adreno X1-85 / Vulkan 1.3 / driver `f22d572733`

Graphic-pack verification:
- `------- Activate graphic packs -------` is present
- **zero** `Activate graphic pack:` entries follow it
- therefore this is the clean graphic-pack-OFF baseline requested for comparison

User visual observation:
- screen/flicker is **the same as the immediately preceding severe capture**.

Final correlation summary:
- frame = **2274**
- draw = **1,007,535**
- GET/newGenGET = **61,352 / 61,352**
- zero = **60,992**
- nonzero = **360**
- `0->NZ` = **328**
- `NZ->0` = **338**
- `NZ->NZ` = **22**
- `0->0` = **60,570**
- FIRST = **94**
- repeat = **0**
- missingSnapshot = **0**
- overwrittenUnconsumed = **0**
- unique query pointers = **94**
- `resultMatchesFinish=0` = **0**
- `GET_NOT_READY` = **0**
- `GET_NO_SNAPSHOT` = **0**

Lifetime/draw-span characteristics:
- every observed query BEGIN/END remained within one frame
- spanDraw median = **1**
- p90 = **5**
- p95 = **7**
- p99/max = **18 / 18**
- FINISH occurred one frame after query END for **61,129 / 61,352** observations; same frame for 223

### Cross-run comparison

The clean OFF capture has visually the same severe flicker, but aggregate zero/nonzero transition density is lower than the preceding graphic-pack-active capture:
- active-packs capture: `(383 + 390) / (47,775 - 154)` ≈ **1.62%** transitioned between zero/nonzero generations
- clean OFF capture: `(328 + 338) / (61,352 - 94)` ≈ **1.09%**

Therefore **aggregate query transition frequency does not directly track perceived flicker severity**.

However, the same small group of query pointers repeatedly ranks among the strongest zero/nonzero oscillators in both captures. Examples:
- `46a92ec8`: 62 transitions in capture A, 88 in clean capture B
- `46a936c8`: 56 -> 66
- `46a93bc8`: 49 -> 41
- `46a93a08`: 34 -> 50
- `46a93708`: 38 -> 25

For the 90 query pointers common to both captures, per-pointer zero/nonzero transition-rate correlation is strong enough to be meaningful (Pearson ≈ **0.786**). This indicates that the oscillation pattern is not random global noise; a stable subset of slots repeatedly behaves as high-oscillation visibility probes across runs.

### Confirmed interpretation

1. Bayonetta 2's CPU query results are completed, internally consistent results; this capture gives no support to a premature/default-zero explanation.
2. Query lifetimes are very narrow in draw space and remain within one frame, which is compatible with object/proxy visibility testing.
3. Turning all Bayonetta graphic packs OFF does **not** remove or visibly reduce the severe flicker.
4. Aggregate query oscillation rate is not proportional to the visual severity, so a global query workaround or global zero->visible patch remains unjustified.
5. A stable small subset of query slots repeatedly oscillates across both captures, making targeted query-to-draw correlation the next useful observation boundary.

### Next experiment proposal — not yet authorized

One observation-only targeted trace:
- focus on the persistent high-oscillation Bayo2 CPU query slots rather than all query traffic
- for frames/generations where those query results change, fingerprint the narrow associated draw range and the next-frame draw stream sufficiently to identify draw clusters that appear/disappear with a given query result
- include shader/pipeline identity and relevant RT/depth state in the fingerprint
- do not change query values, visibility, culling, or renderer behavior
- use the result to identify a concrete query -> draw/object relationship before any behavior A/B

**Do not implement/build this next trace without a fresh user `ㄱㄱ`.**
