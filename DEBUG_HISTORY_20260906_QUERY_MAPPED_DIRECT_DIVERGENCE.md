# DEBUG HISTORY — Query mapped/direct divergence

Date: 2026-09-06

## Protected runtime PASS baseline

Do not remove or weaken the title-gated direct-readback path until a replacement reproduces both runtime PASS results.

- Star Fox Zero JP (`00050000-101AFF00`): Run #25 FIXED by `vkGetQueryPoolResults` direct readback.
- Bayonetta 2 JP (`00050000-1011B900`): Run #26 FIXED by the same direct-readback path.
- PASS experiment HEAD: `5d758a096ee9409e7c25372a6caa9ad9d2378575` on `exp-bayo2-query-direct-readback`.
- `main` remains untouched at `58954b34d147b134d7b23ee61b2057f49da2c014`.

## Run #27 — mapped/direct side-by-side capture

- Workflow run: `34013912085`
- Job: `101434315915`
- CI head: `77c47610c3c472198f13fb399f483691411c1c8c`
- CI result: SUCCESS
- Runtime title: Star Fox Zero JP v16
- Runtime build banner: `Init Cemu 77c4761`

### Selected query-result memory

Runtime log:

`[QUERY_MAP_META] found=1 memoryType=4 heap=0 flags=0x0000000f requested=0x0000000e fallback=0`

Therefore the persistent query-result buffer selected memory type 4 with actual flags `0x0f`:

- DEVICE_LOCAL
- HOST_VISIBLE
- HOST_COHERENT
- HOST_CACHED

The primary allocation path succeeded (`fallback=0`).

This excludes a missing `vkInvalidateMappedMemoryRanges` operation as the explanation for this capture because the selected memory is HOST_COHERENT.

### First mapped/direct divergence

First completed fragment observed:

`[QUERY_DIRECT] n=1 title=00050000101aff00 queryIndex=1023 cmdBuffer=2813 cmdFinished=1 vkResult=0 direct=1192 mapped=0 selected=1192 mismatch=1`

Immediately following fragments repeat the same pattern:

- owning command buffer reported finished
- `vkGetQueryPoolResults` returned `VK_SUCCESS`
- direct result was nonzero
- mapped result remained zero

The pattern persists far into the capture (well above 100,000 direct-readback observations), so this is not a single early stale read.

### Confirmed interpretation

The failure is now narrowed further:

`vkCmdCopyQueryPoolResults -> persistent mapped buffer -> host read`

On the tested Adreno driver, command-buffer completion alone is not making these transfer writes visible to the host-mapped read path.

The direct query-pool readback remains correct and continues to drive the FIXED runtime behavior.

## Vulkan synchronization requirement relevant to this result

Fence completion / fence-status observation provides completion ordering but does not by itself guarantee device writes are made visible to host reads. A device-to-host memory dependency is required. For this path the narrow dependency is:

- source stage: TRANSFER
- source access: TRANSFER_WRITE
- destination stage: HOST
- destination access: HOST_READ

Because the selected memory is HOST_COHERENT, no invalidate call is needed after that dependency for this capture.

## Run #28 experiment

Diagnostic experiment branch:

- `diag-query-mapped-direct-divergence`
- barrier commit: `79fbf25ab8a255fe15ad8210bad21a9a5491c34e`

CI trigger branch:

- `diag-bayo2-target-query-draw-fingerprint`
- Run #28: `34017106924`
- Job: `101442707298`

Single changed variable:

After each title-gated `vkCmdCopyQueryPoolResults`, insert a buffer memory barrier for the exact 8-byte query-result range:

`TRANSFER_WRITE -> HOST_READ`

The direct `vkGetQueryPoolResults` result remains the selected runtime value for Star Fox Zero and Bayonetta 2. Therefore Run #25 / #26 FIXED behavior is not intentionally removed by this experiment.

## NEXT ACTION

1. Complete Run #28 build.
2. Run Star Fox Zero JP first.
3. Check whether `[QUERY_DIRECT]` changes from `direct=N mapped=0 mismatch=1` to `direct=N mapped=N mismatch=0` for nonzero results.
4. If mapped/direct agreement is restored, retain direct-readback as the protected fallback while testing the synchronization fix on Bayonetta 2.
5. Only after both titles reproduce PASS with mapped visibility repaired should broader regression testing begin.
6. XCX remains separate; do not globalize blocking direct readback.
