# DEBUG HISTORY — Query mapped/direct divergence

Date: 2026-09-06

## Immutable runtime PASS baseline

Do not regress or remove the title-gated direct-readback path until a replacement reproduces both runtime PASS results.

- Star Fox Zero JP (`00050000-101AFF00`): Run #25 FIXED by `vkGetQueryPoolResults` direct readback.
- Bayonetta 2 JP (`00050000-1011B900`): Run #26 FIXED by the same direct-readback path.
- PASS head retained on `exp-bayo2-query-direct-readback`: `5d758a096ee9409e7c25372a6caa9ad9d2378575`.
- `main` is out of scope and must not be modified.
- XCX remains separate. Do not globalize the blocking direct-readback path.

## Diagnostic branch / current protected code checkpoint

Diagnostic branch:

- `diag-query-mapped-direct-divergence`
- base: `5d758a096ee9409e7c25372a6caa9ad9d2378575`
- initial mapped/direct instrumentation: `77c47610c3c472198f13fb399f483691411c1c8c`
- protected direct-readback baseline restored at code-changing commit: `790a945780ea561518dd072d9f73c0e3e89b4700`

The CI trigger branch used by the diagnostic workflow is:

- `diag-bayo2-target-query-draw-fingerprint`

The restored Run #31 tree is identical to the current protected code checkpoint tree.

## Confirmed runtime divergence — Run #27 instrumentation

Star Fox Zero JP runtime capture from Cemu `77c4761` proves that the Vulkan query itself is complete and readable while the persistent mapped-copy destination remains zero.

Observed repeatedly:

- `cmdFinished=1`
- `vkResult=0` (`VK_SUCCESS`)
- `direct > 0`
- `mapped=0`
- `selected=direct`
- `mismatch=1`

Representative records include direct values ranging from small sample counts to large nonzero counts while mapped remains zero. The divergence persists across many command buffers and query indices.

This rules out “the query simply was not finished when the CPU read it” as the explanation for the reproduced target failure.

## Confirmed memory type — coherent, no fallback

Bayonetta 2 JP runtime capture from Cemu `7a71d54` reports:

`[QUERY_MAP_META] found=1 memoryType=4 heap=0 flags=0x0000000f requested=0x0000000e fallback=0`

On this Vulkan device:

- actual flags `0x0f` = `DEVICE_LOCAL | HOST_VISIBLE | HOST_COHERENT | HOST_CACHED`
- requested flags `0x0e` = `HOST_VISIBLE | HOST_COHERENT | HOST_CACHED`
- `fallback=0`: the primary coherent allocation succeeded
- `nonCoherentAtomSize=1`

Therefore the reproduced mapped/direct divergence occurs on HOST_COHERENT memory. Missing `vkInvalidateMappedMemoryRanges` for a non-coherent allocation is not the cause of this captured failure.

## Experiments already built — do not repeat blindly

The following single-variable diagnostic steps were already implemented and built successfully:

1. Transfer-write -> host-read visibility barrier
   - diagnostic commit: `79fbf25ab8a255fe15ad8210bad21a9a5491c34e`
   - trigger Run #28: `34017106924`
   - result: CI SUCCESS

2. Forced mapped-memory invalidate on target titles
   - diagnostic commit: `7a71d5405f3d438d52dce9554eb93a0ee49a2ed2`
   - trigger Run #29: `34019347912`
   - result: CI SUCCESS
   - Bayonetta 2 log confirms the selected result memory is coherent (`flags=0x0f`, `fallback=0`), so invalidate is not a principled fix for this captured device path.

3. Device-local intermediate isolation
   - diagnostic commit: `eb04e6f370c8bbf2ae9564e19edef8b6e8c7d266`
   - trigger Run #30 head: `6532c82d1c75b983465bcac40cf36f947462e0b9`
   - Run ID: `34021733515`
   - result: CI SUCCESS
   - artifact ID: `9986265293`
   - artifact digest: `sha256:c7083f69433ae71029673d7ac21291a6f6b8543060eec4a794e0949eb0621b3b`
   - behavior: for Star Fox Zero JP and Bayonetta 2 JP only, `vkCmdCopyQueryPoolResults` writes first to a DEVICE_LOCAL intermediate buffer, then `vkCmdCopyBuffer` copies to the existing mapped host buffer. Direct readback remains selected so the known FIXED behavior is protected.
   - runtime result: **NOT CAPTURED / NOT VERIFIED**. No Run #30 runtime log is present in the available September 6 uploads. Do not infer PASS or FAIL.

4. Protected direct-readback baseline restoration
   - diagnostic code commit: `790a945780ea561518dd072d9f73c0e3e89b4700`
   - trigger Run #31 head: `be3064da39e2913719de6fc800e7f417d28a0aec`
   - Run ID: `34024292927`
   - result: CI SUCCESS
   - artifact ID: `9987082611`
   - artifact digest: `sha256:74aef6d516965fc1ec93fc32d0a6ad2fe0358e36a439afdf1b9d2e6c344499bd`
   - current source tree is back on the protected Star Fox Zero + Bayonetta 2 direct-readback behavior; other titles retain the normal mapped path.

## Current technical classification

Confirmed:

- `vkGetQueryPoolResults(... WAIT_BIT)` returns the correct completed query result on the two reproduced titles.
- The normal Cemu path records `vkCmdCopyQueryPoolResults` into `m_occlusionQueries.bufferQueryResults`, waits for the owning command buffer to finish, then reads `ptrQueryResults[queryIndex]`.
- On the reproduced Adreno X1-85 path, the mapped value can remain zero after command-buffer completion while direct query-pool readback is nonzero.
- The result memory selected in the captured Bayonetta 2 run is HOST_COHERENT.

Still unresolved:

- whether Qualcomm's failure is specific to `vkCmdCopyQueryPoolResults` targeting the persistently mapped host-visible buffer, or whether the query-copy result is also wrong when the immediate destination is DEVICE_LOCAL.

Run #30 exists specifically to answer that branch point.

## NEXT ACTION

1. Do **not** build again yet.
2. Reuse Run #30 artifact `9986265293` (`sha256:c7083f69433ae71029673d7ac21291a6f6b8543060eec4a794e0949eb0621b3b`).
3. Run Star Fox Zero JP first and capture `log.txt` from startup through the reproduced scene.
4. Verify the build identifies as the Run #30/intermediate code, not restored Run #31.
5. Determine whether the mapped value becomes nonzero through the DEVICE_LOCAL -> mapped-buffer copy path and whether visual flicker remains fixed.
6. Only after Star Fox classification, run Bayonetta 2 JP on the same Run #30 build.
7. If DEVICE_LOCAL intermediate makes mapped values correct, narrow the defect to direct query-copy into the host-visible mapped destination and design the smallest title/device-scoped replacement.
8. If DEVICE_LOCAL intermediate still leaves mapped values zero, treat `vkCmdCopyQueryPoolResults` itself as the failing Adreno path and retain `vkGetQueryPoolResults` as the protected workaround while investigating a non-blocking alternative.
9. Do not modify `main`; do not remove the Run #25/#26 direct-readback PASS path; do not mix XCX into this experiment.
