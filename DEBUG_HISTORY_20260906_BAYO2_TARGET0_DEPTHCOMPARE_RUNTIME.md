# DEBUG HISTORY — 2026-09-06 — Bayo2 target0 depth-compare runtime

## Scope

Run #17 observation-only trace for Bayonetta 2 JP target0 `0x46a92ec8`, focused only on the already-bound PS unit11 GPU-updated depth texture `0xf57c8000`.

## Build

- CI head: `ce80d7a68dc88b90f299f9e2dfd53b8e267c92d9`
- Run: `33971629934` / #17
- Conclusion: SUCCESS
- Artifact: `cemu-arm64-bayo2-target-query-draw-fingerprint`
- Artifact id: `9971602143`
- Artifact digest: `sha256:8c5745809a761ac27da869bc658d80c82803077475616dac05ce73dfa28d614a`

## Runtime capture

Input: `log (2)(3).zip`

- target0 completed GET generations: 666
- `[BAYO2_TARGET_DEPTHCOMPARE]`: 667 rows
- completed generations covered: 666/666
- final extra depthcompare row belongs to incomplete next generation and is excluded

Results:

- ZERO: 610
- NONZERO: 56
- FIRST: 1
- `0->0`: 556
- `0->NZ`: 53
- `NZ->0`: 53
- `NZ->NZ`: 3

## Fixed identity/history fields

All 666 completed generations, ZERO and NONZERO alike, have the same:

- register/bound phys: `f57c8000`
- mipPhys: `00000000`
- isDepth=1
- stencil=1
- format=17 (`0x11`)
- tileMode=4
- swizzle/rtSwizzle=0
- size `1024x2048`
- pitch 1024
- view mip 0/1
- view slice 0/1
- dataDefined=1
- gpuUpdated=1
- readback=0
- reloadDynamic=0
- updateEvent=1055
- updateFrame=0
- reloadCount=1
- texDataHash2=0

Dynamic bookkeeping:

- `dataUpdateFrame == producer frame`: 666/666
- `accessFrame == producer frame`: 666/666
- nonzero `unflushedDraw` occurred in both result classes; 21 total anomalies, 18 ZERO / 3 NONZERO, so not result-specific

`writeEvent` delta is explained by frame gap, not result class. Examples:

One-frame gaps:

- `0->0`: n=291, median 492, range 376..582
- `0->NZ`: n=27, median 497, range 399..572
- `NZ->0`: n=29, median 491, range 397..547

Three-frame gaps:

- `0->0`: n=265, median 1492, range 1224..2105
- `0->NZ`: n=26, median 1494.5, range 1226..1653

The ranges strongly overlap.

## Conclusion

**Observed bound-object write/update/access history of the common PS unit11 depth-compare texture `0xf57c8000` is not a ZERO/NONZERO discriminator.**

Do not repeat this bookkeeping experiment under the same conditions.

This closes the remaining obvious Bayo2 producer-resource observation gap short of GPU image-content readback. Because prior destructive/seeded depth experiments are already closed, do not reopen them without new contradictory evidence.

## New cross-title evidence

Star Fox Zero JP v16 (`00050000-101aff00`) shows the same visible flicker according to the runtime observer and independently exhibits the same structural depth path in logs:

- `f57c8000`
- format `0x11`
- GPU-updated depth texture
- reused from PS stage/unit 11
- also used as a depth attachment

Star Fox dimensions differ (`768x1536`) but preserve the same 1:2 aspect relationship seen in Bayo2 (`1024x2048`).

This does not yet prove identical query consumption. The next decisive comparison is Star Fox query type / CPU GET / ready-zero/nonzero / conditional-render behavior using the existing `[QUERY_COMPARE]` instrumentation.
