# DEBUG HISTORY — 2026-09-06 — Star Fox Zero + Bayonetta 2 direct Vulkan query readback runtime

## Scope

Cross-title behavior A/B for the reproduced object-flicker issue on Windows ARM64 / Adreno.

Titles:

- Star Fox Zero JP `00050000-101AFF00` v16
- Bayonetta 2 JP `00050000-1011B900` v1

Protected `main` remains untouched at `58954b34d147b134d7b23ee61b2057f49da2c014`.

## Baseline / prior facts

Both titles use CPU occlusion query type=0 and exported `GX2QueryGetOcclusionResult()` consumption. Prior focused Star Fox tracing proved completed FINISH values and CPU GET values match exactly, so the problem was narrowed to the Vulkan occlusion-query result path before CPU consumption.

The normal Vulkan path is:

`vkCmdCopyQueryPoolResults -> persistently mapped result buffer -> CPU read`

The behavior A/B replaces only the result-consumption step for selected titles with:

`vkGetQueryPoolResults()`

after the owning command buffer is known complete.

## Run #25 — Star Fox only

- Run ID `34007865487`
- Job ID `101418283084`
- Head `7154c20d24abc574a09ba7733f05a987b3446420`
- CI conclusion: SUCCESS
- Build / Collect / Upload: SUCCESS

Behavior gate: Star Fox Zero JP only.

Runtime observation supplied by user:

- Star Fox Zero flicker: **FIXED**
- This is the first runtime PASS showing that direct `vkGetQueryPoolResults()` eliminates the reproduced Star Fox flicker.

Important interpretation:

- This strongly implicates the existing mapped-buffer query-result consumption/read-visibility path.
- It does **not yet prove** the exact low-level mechanism (memory coherence vs synchronization/visibility vs driver behavior).
- Preserve this Star Fox PASS as a non-regression checkpoint.

## Run #26 — Star Fox + Bayonetta 2

Experiment branch: `exp-bayo2-query-direct-readback`

Head:

`5d758a096ee9409e7c25372a6caa9ad9d2378575`

Change from Run #25:

- Extend the same direct `vkGetQueryPoolResults()` path to Bayonetta 2 JP.
- Other titles retain the existing mapped-buffer path.
- Runtime log marker generalized to `[QUERY_DIRECT]` and includes title ID.

Run #26:

- Run ID `34011609042`
- Job ID `101428310700`
- CI conclusion: SUCCESS
- All steps including Configure, Build Cemu once, Collect executable, Upload diagnostic artifact: SUCCESS

Runtime observation supplied by user:

- Bayonetta 2 flicker: **FIXED**
- Star Fox remains the prior confirmed PASS under the same direct-readback mechanism.

## Cross-title conclusion

This is a **strong common-cause confirmation**:

1. Star Fox Zero and Bayonetta 2 both reproduce the severe flicker on the baseline mapped-buffer query-result path.
2. The same direct `vkGetQueryPoolResults()` substitution removes the flicker in both titles.
3. Therefore the primary shared failure domain is no longer merely a generic Platinum rendering-path hypothesis; it is specifically the Vulkan occlusion-query result readback/visibility path used by these CPU type=0 query consumers on this Adreno Windows ARM64 environment.

Do not overstate the mechanism:

- The exact root cause inside the mapped-buffer path is still OPEN.
- Do not yet conclude that all Vulkan titles should globally use `vkGetQueryPoolResults()`.
- Do not yet conclude that non-coherent memory is the cause; the device exposes a HOST_VISIBLE + HOST_COHERENT + HOST_CACHED memory type.

## Next action

1. Preserve Run #25/#26 as runtime PASS baselines.
2. Instrument/inspect the existing mapped-result buffer allocation and result-visibility path to identify why it diverges from direct `vkGetQueryPoolResults()` on Adreno.
3. Determine whether the correct permanent fix is:
   - a missing synchronization/visibility step,
   - an allocation/memory-property selection issue,
   - a driver-specific workaround,
   - or a narrower query-result handling correction.
4. Before any global change, validate against unaffected titles, especially XCX and BOTW.
5. Do not remove the title-gated direct-readback PASS path until a replacement fix reproduces both Star Fox and Bayonetta 2 PASS.
