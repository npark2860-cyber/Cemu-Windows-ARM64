# DEBUG HISTORY — 2026-09-05 — Star Fox Zero / Bayonetta 2 common f57c8000 depth path

## Scope

Observation-only cross-title comparison using the user runtime captures:

- Bayonetta 2 JP target0 texture-resource capture (`log (2)(2).zip`)
- Star Fox Zero JP v16 capture (`log(6).zip`)

No behavior change is inferred or applied here.

## Star Fox capture identity

- Title ID: `00050000-101aff00`
- Title version: v16
- Region: JP
- Vulkan GPU: Qualcomm Adreno X1-85
- Driver: `f22d572733`, branch `pp165`
- No Vulkan error/crash marker was present in this capture.
- Existing Bayo2-only query/target markers are absent by title gating; therefore Star Fox query-consumption semantics are not yet established.

## Strong common resource-path observation

Both titles create and GPU-update a depth texture at physical address `0xf57c8000` using format `0x11`.

Bayonetta 2:

- `f57c8000`
- size `1024x2048x1`
- pitch 1024
- format `0x11`
- `isDepth=1`
- deletion summary `gpuUpdated=1`, reloads=1
- target0 producer PS repeatedly references this resource as unit 11 with `depthCompare=1`
- generic texture-cache sampling also reports stage=1, unit=11, addr=`f57c8000`
- generic attachment trace reports the same `f57c8000` as a depth attachment

Star Fox Zero:

- `f57c8000`
- size `768x1536x1`
- pitch 768
- format `0x11`
- `isDepth=1`
- deletion summary `gpuUpdated=1`, reloads=1
- generic texture-cache trace repeatedly reports stage=1, unit=11, addr=`f57c8000`
- generic attachment trace repeatedly reports the same `f57c8000` as a depth attachment

The two sizes share the same 1:2 shape and differ by a 0.75 scale factor. Do not treat this geometry alone as causal proof; the important confirmed fact is the shared GPU-written depth-resource / PS-unit-11 reuse structure.

## Interpretation

This materially strengthens the hypothesis that the visually similar flicker in Bayonetta 2 and Star Fox Zero may involve a shared Platinum-era Wii U renderer path centered on a GPU-written depth surface that is later reused by pixel shaders.

It does NOT yet prove:

- Star Fox uses the same CPU occlusion-query type/path as Bayonetta 2
- Star Fox consumes `GX2QueryGetOcclusionResult()` in the same way
- `f57c8000` content/history is the direct cause of flicker
- an attachment-feedback-loop hazard is already proven

## Current Bayonetta next step

Run #17 remains the active Bayonetta experiment. It observes only the `f57c8000` depth-compare texture bookkeeping (`lastWriteEventCounter`, update frames, GPU-updated state, reload/access/unflushed RT history) and must be completed before a behavior change.

## Star Fox next step

Use Star Fox Zero JP as an independent comparator. The first required observation is query-consumption classification using the existing `[QUERY_COMPARE]` schema:

- API BEGIN/END counts and query type
- exported CPU `GX2QueryGetOcclusionResult()` consumption
- READY_ZERO / READY_NONZERO / NOT_READY
- renderer FINISH_ZERO / FINISH_NONZERO
- conditional-render API usage

Do not assume Star Fox = Bayonetta 2 until these markers are captured.
