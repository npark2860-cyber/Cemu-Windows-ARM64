# DEBUG HISTORY — Query mapped/direct divergence

Date: 2026-09-06

## Immutable runtime PASS baseline

Do not regress or remove the title-gated direct-readback path until a replacement reproduces both runtime PASS results.

- Star Fox Zero JP (`00050000-101AFF00`): Run #25 FIXED by `vkGetQueryPoolResults` direct readback.
- Bayonetta 2 JP (`00050000-1011B900`): Run #26 FIXED by the same direct-readback path.
- PASS head retained on `exp-bayo2-query-direct-readback`: `5d758a096ee9409e7c25372a6caa9ad9d2378575`.
- `main` is out of scope and must not be modified.

## Current experiment

Goal: find the first point where the persistent mapped query-result buffer differs from the successful direct query-pool readback, without changing the successful result selection.

Diagnostic branch:

- `diag-query-mapped-direct-divergence`
- base: `5d758a096ee9409e7c25372a6caa9ad9d2378575`
- instrumentation commit: `77c47610c3c472198f13fb399f483691411c1c8c`

CI trigger branch was fast-forwarded only for the diagnostic workflow:

- `diag-bayo2-target-query-draw-fingerprint`
- Run #27: `34013912085`
- Job: `101434315915`
- head: `77c47610c3c472198f13fb399f483691411c1c8c`

Run #27 pre-build patch/verification steps 11–19 have passed. At the time of this record the run is still executing the normal Configure step; no build result is claimed yet.

## Instrumentation added

The existing Star Fox Zero JP + Bayonetta 2 JP direct-readback result selection is preserved exactly. Other titles remain on the normal mapped path.

One startup record now reports persistent query-result buffer memory selection:

`[QUERY_MAP_META] found=... memoryType=... heap=... flags=... requested=... fallback=...`

Direct-readback records now include the side-by-side state needed by CURRENT_HANDOFF NEXT ACTION:

`[QUERY_DIRECT] ... queryIndex=... cmdBuffer=... cmdFinished=... vkResult=... direct=... mapped=... selected=... mismatch=...`

This provides:

- selected memory type index
- actual memory-property flags
- primary/fallback allocation path
- query index
- owning command-buffer ID
- command-buffer completion state
- mapped value
- direct value
- selected value
- mismatch flag

## Static synchronization finding — not yet applied

The current mapped path records `vkCmdCopyQueryPoolResults` into the persistent host-visible result buffer and later reads the mapped pointer after command-buffer fence completion.

Vulkan requires query-copy buffer writes to be synchronized as transfer writes before those results are used. A device-to-host memory dependency targeting host reads is therefore the narrow synchronization candidate to test if runtime capture confirms a mapped/direct divergence after command-buffer completion. If the selected memory type is not HOST_COHERENT, `vkInvalidateMappedMemoryRanges` is additionally required before host access.

No synchronization fix has been applied yet. Runtime evidence comes first.

## NEXT ACTION

1. Complete Run #27 and obtain its artifact.
2. Run Star Fox Zero JP first with the Run #27 build.
3. Preserve the existing direct-readback FIXED behavior while capturing the log.
4. Extract `[QUERY_MAP_META]` and the first `[QUERY_DIRECT] ... mismatch=1` records.
5. Classify the selected memory type as coherent/non-coherent.
6. Only from that evidence, apply one narrow mapped-path visibility fix.
7. Re-test Star Fox Zero JP and Bayonetta 2 JP before any broader rollout.
8. XCX remains separate; do not globalize the blocking direct readback.
