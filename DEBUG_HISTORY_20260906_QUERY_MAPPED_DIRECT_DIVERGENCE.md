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

1. Transfer-write -> host-read visibility barrier
   - diagnostic commit: `79fbf25ab8a255fe15ad8210bad21a9a5491c34e`
   - Run #28: `34017106924`
   - CI SUCCESS

2. Forced mapped-memory invalidate on target titles
   - diagnostic commit: `7a71d5405f3d438d52dce9554eb93a0ee49a2ed2`
   - Run #29: `34019347912`
   - CI SUCCESS
   - Bayonetta 2 log confirms HOST_COHERENT result memory (`flags=0x0f`, `fallback=0`); invalidate is not the root fix.

3. Device-local intermediate isolation
   - diagnostic commit: `eb04e6f370c8bbf2ae9564e19edef8b6e8c7d266`
   - trigger Run #30 head: `6532c82d1c75b983465bcac40cf36f947462e0b9`
   - Run ID: `34021733515`
   - CI SUCCESS
   - artifact ID: `9986265293`
   - artifact digest: `sha256:c7083f69433ae71029673d7ac21291a6f6b8543060eec4a794e0949eb0621b3b`
   - implementation: target titles use `vkCmdCopyQueryPoolResults` -> DEVICE_LOCAL intermediate -> `vkCmdCopyBuffer` -> existing mapped host buffer.
   - implementation contains both required dependencies:
     - intermediate `TRANSFER_WRITE -> TRANSFER_READ`
     - destination `TRANSFER_WRITE -> HOST_READ`
   - direct readback remains selected, preserving the known FIXED result selection.

### Star Fox Zero JP Run #30 runtime result — FAILED TO REPAIR MAPPED PATH

Uploaded runtime log identifies the expected build:

- `Init Cemu 6532c82`
- title `00050000101aff00`
- `[QUERY_INTERMEDIATE] allocated=1 size=8192`
- `[QUERY_MAP_META] found=1 memoryType=4 heap=0 flags=0x0000000f requested=0x0000000e fallback=0`

Parsed logged `[QUERY_DIRECT]` records:

- records: `336166`
- path: `intermediate` for all parsed records
- `vkResult=0` for all parsed records
- direct nonzero: `335995`
- mismatch: `335993`
- mapped nonzero among logged records: `2`
- equal direct/mapped logged records: `173`, of which `171` are both zero and only `2` are nonzero matches

Representative beginning:

`[QUERY_DIRECT] n=1 ... cmdFinished=1 path=intermediate vkResult=0 direct=1192 mapped=0 selected=1192 mismatch=1`

The same pattern continues through the end of the capture. Two sparse periodic records show nonzero equality (`n=284000` and `n=326000`), proving the chain can occasionally transfer a value, but the DEVICE_LOCAL intermediate does not repair the systematic failure.

Because Run #30 contains explicit transfer-write/read and transfer-write/host-read barriers, this result is not explained by a missing barrier between the two copies.

4. Protected direct-readback baseline restoration
   - diagnostic code commit: `790a945780ea561518dd072d9f73c0e3e89b4700`
   - trigger Run #31 head: `be3064da39e2913719de6fc800e7f417d28a0aec`
   - Run ID: `34024292927`
   - CI SUCCESS
   - artifact ID: `9987082611`
   - artifact digest: `sha256:74aef6d516965fc1ec93fc32d0a6ad2fe0358e36a439afdf1b9d2e6c344499bd`
   - current protected source tree is back on the Star Fox Zero + Bayonetta 2 direct-readback behavior; other titles retain the normal mapped path.

## Current technical classification

Confirmed:

- `vkGetQueryPoolResults(... WAIT_BIT)` returns the completed query result correctly on the reproduced target path.
- The normal `vkCmdCopyQueryPoolResults` -> mapped-buffer path can return zero after the owning command buffer is finished.
- The selected result memory is HOST_COHERENT; non-coherent invalidation is not the cause.
- Adding a transfer-write -> host-read barrier does not resolve the captured failure.
- Routing query-copy first into DEVICE_LOCAL memory, with a proper `TRANSFER_WRITE -> TRANSFER_READ` barrier and then a `vkCmdCopyBuffer` plus `TRANSFER_WRITE -> HOST_READ` barrier, still leaves the mapped result zero for nearly all logged nonzero direct results.

Therefore the failure boundary is now narrowed past host-visible destination selection and host cache visibility. The remaining suspect is the Adreno `vkCmdCopyQueryPoolResults` result-copy path itself (or driver behavior specifically tied to that command), not the subsequent CPU mapped read.

Do not claim a final driver bug across all titles yet: Bayonetta 2 Run #30 still needs the same runtime classification, and XCX uses a different consumption path.

## NEXT ACTION

1. Do **not** rebuild yet.
2. Reuse Run #30 artifact `9986265293`.
3. Run Bayonetta 2 JP (`00050000-1011B900`) with the same Run #30/intermediate build.
4. Capture `log.txt` from startup through the previously reproduced scene.
5. Verify:
   - `Init Cemu 6532c82`
   - `[QUERY_INTERMEDIATE] allocated=1`
   - target title `000500001011b900`
6. Parse `[QUERY_DIRECT]` and compare direct/mapped values.
7. If Bayonetta 2 reproduces the same intermediate-path divergence, close the mapped-copy line of investigation for these two titles and move to a non-blocking direct-query-result replacement experiment.
8. Preferred next one-variable experiment after both-title confirmation: call `vkGetQueryPoolResults` **without `VK_QUERY_RESULT_WAIT_BIT` after `HasCommandBufferFinished(...)` is true**. On `VK_SUCCESS`, consume direct result; on `VK_NOT_READY`, retain the fragment and retry rather than blocking or releasing the query index.
9. Do not modify `main`; do not remove the Run #25/#26 direct-readback PASS path; do not mix XCX into this experiment.
