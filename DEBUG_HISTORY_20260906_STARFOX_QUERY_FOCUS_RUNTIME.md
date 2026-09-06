# Star Fox Zero query focus runtime — 2026-09-06

## Scope

Observation-only Star Fox Zero JP query-consumption follow-up after the Bayonetta 2 CPU occlusion-query investigation.

No query value, readiness, submission, render state, draw behavior, or Vulkan synchronization behavior was changed in this experiment.

## Build / CI

Run #21:

- Workflow: `Cemu ARM64 Bayo2 Target Query Draw Fingerprint Trace`
- Run ID: `33982171927`
- Head: `cab2cee61d0d96494d6851dce9f2c877a0fa973c`
- Result: **SUCCESS**
- Step 18 targeted fingerprint / Star Fox trace application: **SUCCESS**
- Build / collect / upload: **SUCCESS**

## Run #21 runtime log

User runtime log: `log (2)(4).zip` (`log.txt`, 68,462,031 bytes).

### Generic Star Fox query classification

All observed `[QUERY_COMPARE] API_BEGIN` samples were:

- title: `00050000101aff00`
- query type: **0 / CPU occlusion**
- observed API_BEGIN marker rows: 980

No `[QUERY_COMPARE] GET_NOT_READY` marker occurred.
Because the generic trace logs the first NOT_READY event before sampling, this means the NOT_READY counter remained zero during this capture.

No `[QUERY_COMPARE] CONDITIONAL_BEGIN` or `CONDITIONAL_END` marker occurred.

Near the end of the capture, a sampled GET marker carried the exact cumulative counters:

- calls: `850915`
- READY_ZERO: `849000`
- READY_NONZERO: `1915`
- NOT_READY: `0`

Thus, at that point:

- ZERO: ~99.775%
- NONZERO: ~0.225%

A near-end FINISH marker carried:

- total FINISH: `851915`
- FINISH_ZERO: `850000`
- FINISH_NONZERO: `1915`

The capture also reached at least `API_BEGIN n=852000`.

### Focus trace miss and root cause

Run #21 contained **zero** `[STARFOX_QUERY_FOCUS]` rows.
The previous hard-coded focus MPTR `0x460f9fc8` did not occur anywhere in the new runtime log.

However, the same logical early query position was preserved:

Previous Star Fox generic runtime (`log(8).zip`):

- `API_BEGIN n=26`
- query `0x460f9fc8`
- first sampled NONZERO result `192104`

Run #21:

- `API_BEGIN n=26`
- query `0x460f9f88`
- first sampled NONZERO result `192105`

The guest MPTR shifted by exactly `-0x40`, which is one `GX2Query` object size, while the logical query ordinal and result scale remained the same.

For Run #21 logical focus pointer `0x460f9f88`, the sampled NONZERO FINISH and GET value sequences matched exactly for all 23 observed NONZERO values. Examples begin with:

- `192105`
- `192106`
- `192108`
- `192109`
- `191984`

This is consistent with the Bayonetta 2 finding that completed renderer results are actually consumed by the CPU path; it is not an unready/default-zero artifact.

## Confirmed interpretation

Star Fox Zero now independently demonstrates a Bayonetta-2-like query-consumption class:

- CPU occlusion query path (`type=0` in all observed samples)
- very large completed READY_ZERO population
- real completed NONZERO results mixed into the same workload
- no observed NOT_READY consumption
- no exported conditional-render markers in the capture

This strongly raises the priority of a shared Cemu query/visibility semantic issue exposed by PlatinumGames-family rendering patterns, but does **not** by itself prove a common engine or identical root cause.

## Focus addressing correction

Hard-coding the Star Fox query MPTR is now **rejected** because the guest query address is not stable across runs.

New strategy:

- identify the logical focus slot by Star Fox query-begin ordinal `26`
- capture its actual MPTR dynamically at runtime
- independently capture the 26th CPU query in Latte core
- trace all subsequent FINISH / GET_READY events for the captured pointer

Staging commit:

- branch: `diag-starfox-query-consumption`
- commit: `a7099527a22b539d49475b013dc9e19fe62c8f52`

CI branch commit:

- branch: `diag-bayo2-target-query-draw-fingerprint`
- commit: `828fb05af7be41e06f6c6f53d87a86df20e8f6b1`

Only `tools/diagnostics/Apply-StarFoxFocusedQueryTrace.py` changed from Run #21 CI HEAD.

## Active build

Run #22:

- Run ID: `34002755525`
- Head: `828fb05af7be41e06f6c6f53d87a86df20e8f6b1`
- Purpose: ordinal-capture Star Fox focused query trace
- State when this document was written: **in progress**

Expected new markers:

- `[STARFOX_QUERY_FOCUS] CAPTURE_API ordinal=26 ...`
- `[STARFOX_QUERY_FOCUS] CAPTURE_CORE ordinal=26 ...`
- `[STARFOX_QUERY_FOCUS] FINISH ...`
- `[STARFOX_QUERY_FOCUS] GET_READY ...`

## Do not regress

- Do not return to hard-coded Star Fox MPTR `0x460f9fc8`.
- Do not interpret READY_ZERO as NOT_READY; this capture again showed NOT_READY=0.
- Do not transplant XCX GPU-query assumptions into Star Fox or Bayonetta 2.
- Do not repeat already closed Bayonetta 2 producer-resource/hash experiments unless new cross-title evidence directly reopens one.
