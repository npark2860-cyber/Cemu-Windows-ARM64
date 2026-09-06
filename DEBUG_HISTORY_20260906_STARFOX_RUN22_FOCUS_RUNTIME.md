# Star Fox Zero Run #22 focused query runtime — 2026-09-06

## Build

- Workflow: `Cemu ARM64 Bayo2 Target Query Draw Fingerprint Trace`
- Run: #22
- Run ID: `34002755525`
- CI head: `828fb05af7be41e06f6c6f53d87a86df20e8f6b1`
- Result: **SUCCESS**
- Artifact ID: `9980480912`
- Artifact digest: `sha256:979a38cdd0af3f9dd46d96eb161843e146c6fe3e4289de5002896f1d9c41675f`

## Runtime capture

User log: `log(9).zip`, Star Fox Zero JP v16, title `00050000-101AFF00`.
GPU: Qualcomm Adreno X1-85, driver build `f22d572733`, compiler `E031.50.36.00`.

Dynamic ordinal capture worked:

- `[STARFOX_QUERY_FOCUS] CAPTURE_API ordinal=26 query=460f9fc8 type=0`
- `[STARFOX_QUERY_FOCUS] CAPTURE_CORE ordinal=26 query=460f9fc8`

The focus address is therefore captured at runtime and must not be treated as a stable hard-coded MPTR across executions.

## Focus sequence

Complete focused generations:

- FINISH rows: 4067
- GET_READY rows: 4067
- FINISH/GET value or class mismatches: **0**
- ZERO: 3914
- NONZERO: 153

Transitions:

- ZERO -> ZERO: 3776
- ZERO -> NONZERO: 137
- NONZERO -> ZERO: 137
- NONZERO -> NONZERO: 16

NONZERO run lengths:

- 1 generation: 123 runs
- 2 generations: 12 runs
- 3 generations: 2 runs
- total NONZERO runs: 137

NONZERO values:

- min: 50380
- median: 188895
- max: 322853

All observed raw query starts for this focus slot were zero. For NONZERO generations the raw end value equaled the completed result.

Renderer FINISH to guest CPU GET latency was approximately:

- median: 13 ms
- mean: 13.0 ms
- max: 23 ms

## Interpretation

The CPU-visible result propagation layer is not producing a separate ZERO/NONZERO corruption for this focus slot: every one of 4067 renderer FINISH sample sums exactly matched the corresponding guest GET result.

This localizes any incorrect visibility result to the Vulkan occlusion-query result production/readback path or earlier rendering state/data, not to the final GX2 `GX2QueryGetOcclusionResult()` subtraction/copy step.

The sequence shape is strongly reminiscent of Bayonetta 2 target0: a dominant completed ZERO population with mostly isolated NONZERO spikes. This is cross-title evidence, not proof that the same individual query represents the same scene object.

## Vulkan memory note

Runtime Vulkan memory types include a memory type with flags `0x0000000f`, i.e. DEVICE_LOCAL + HOST_VISIBLE + HOST_COHERENT + HOST_CACHED. Therefore the prior concern that Adreno necessarily falls back to a non-coherent query-result allocation is deprioritized; the required coherent/cached property combination is advertised by the device.

## Next A/B

One-variable Star Fox-only experiment:

- bypass the existing `vkCmdCopyQueryPoolResults -> mapped buffer` consumption in `VulkanQuery.cpp`
- after command-buffer completion, obtain each Star Fox Vulkan query fragment with `vkGetQueryPoolResults()`
- keep every other title on the existing path
- retain exact 64-bit query-result semantics

Experiment branch: `exp-starfox-query-direct-readback`
CI experiment head: `c73471052149da3a59431259c4ee9a976d638f63`
Run #23 ID: `34005068971`

If Star Fox flicker changes materially, isolate the query-result copy/readback path. If it does not, demote query readback and move upstream to the visibility draw / buffer-cache / synchronization path feeding the occlusion query.

## Do not regress

- Do not reinterpret completed READY_ZERO as NOT_READY.
- Do not return to a hard-coded Star Fox query MPTR.
- Do not change Bayonetta 2 behavior in the Star Fox-only direct-readback A/B.
- Do not repeat broad render-pass/barrier experiments already closed for Bayonetta 2 without a new precise dependency.
