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

### First mapped/direct divergence

First completed fragment observed:

`[QUERY_DIRECT] n=1 title=00050000101aff00 queryIndex=1023 cmdBuffer=2813 cmdFinished=1 vkResult=0 direct=1192 mapped=0 selected=1192 mismatch=1`

Immediately following fragments repeat the same pattern:

- owning command buffer reported finished
- `vkGetQueryPoolResults` returned `VK_SUCCESS`
- direct result was nonzero
- mapped result remained zero

The direct query-pool readback remained correct and continued to drive the FIXED runtime behavior.

## Run #28 — transfer-to-host barrier experiment

Diagnostic commit:

`79fbf25ab8a255fe15ad8210bad21a9a5491c34e`

Workflow:

- Run #28: `34017106924`
- Job: `101442707298`
- CI result: SUCCESS
- Runtime build banner: `Init Cemu 79fbf25`
- Runtime title: Star Fox Zero JP v16

Single changed variable:

After each target-title `vkCmdCopyQueryPoolResults`, insert a buffer memory barrier for the exact 8-byte query-result range:

`TRANSFER_WRITE -> HOST_READ`

The direct `vkGetQueryPoolResults` result remained the selected runtime value, preserving the Star Fox FIXED graphics behavior.

### Runtime result: FAIL for mapped-path repair

The barrier did not restore the mapped result path.

The first results still showed:

`direct=1192 mapped=0 selected=1192 mismatch=1`

Full-log parse summary:

- `[QUERY_DIRECT]` records parsed: 230,184
- command-buffer finished records: 230,184 / 230,184
- `vkGetQueryPoolResults` success: 230,184 / 230,184
- direct nonzero: 230,032
- mapped nonzero: 2
- mismatches: 230,030
- mismatch rate: ~99.9331%
- both zero: 152
- exact equal nonzero mapped/direct: only 2

The two nonzero mapped reads were both exact matches with direct:

- `n=120 queryIndex=1015 cmdBuffer=2233 direct=488207 mapped=488207`
- `n=225000 queryIndex=987 cmdBuffer=38086 direct=189539 mapped=189539`

Therefore the mapped pointer/offset is not universally wrong. The destination occasionally becomes visible correctly, but almost all device-written query results remain stale from the host view.

### Interpretation after Run #28

Closed explanation:

- missing `TRANSFER_WRITE -> HOST_READ` barrier alone is not sufficient to explain or repair the Adreno behavior.

Still live:

- Qualcomm Windows Vulkan host-cache/coherency quirk despite the memory type advertising `HOST_COHERENT | HOST_CACHED`
- `vkCmdCopyQueryPoolResults` writes becoming available only sporadically to the persistent mapping
- driver-specific behavior on the direct-to-host-visible query-copy path

The source allocation and map offsets remain structurally consistent: the query-result buffer is bound at memory offset 0 and the same `VkDeviceMemory` is mapped from offset 0.

## Run #29 — explicit mapped-memory invalidate experiment

Diagnostic branch:

`diag-query-mapped-direct-divergence`

Commit:

`7a71d5405f3d438d52dce9554eb93a0ee49a2ed2`

CI branch:

`diag-bayo2-target-query-draw-fingerprint`

Workflow:

- Run #29: `34019347912`
- state at creation: queued

Single new variable relative to Run #28:

After owning command-buffer completion and before reading `ptrQueryResults[it.queryIndex]`, issue `vkInvalidateMappedMemoryRanges` for the exact query-result range on Star Fox Zero JP / Bayonetta 2 JP.

The Run #28 `TRANSFER_WRITE -> HOST_READ` barrier remains in place.

The direct `vkGetQueryPoolResults` result remains the selected runtime value, so the protected Star Fox / Bayonetta 2 FIXED behavior is preserved during this diagnostic.

`[QUERY_DIRECT]` now also records `invalidate=<VkResult>`.

## NEXT ACTION

1. Complete Run #29 CI.
2. Run Star Fox Zero JP first.
3. Verify `invalidate=0`.
4. Check whether nonzero results change to `direct=N mapped=N mismatch=0`.
5. If explicit invalidate restores mapped agreement, classify this as an Adreno/Windows coherent-host-cache visibility quirk and test Bayonetta 2 with the same narrow path.
6. If mapped remains zero despite successful invalidate, move away from host-cache synchronization and test a device-local intermediate query-copy buffer followed by ordinary `vkCmdCopyBuffer` into the mapped host-visible buffer.
7. Keep XCX separate and do not globalize blocking direct readback.
