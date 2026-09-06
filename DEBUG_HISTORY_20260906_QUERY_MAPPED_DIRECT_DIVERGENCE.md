# DEBUG HISTORY — Query mapped/direct divergence

Date: 2026-09-06

## Protected runtime PASS baseline

Do not remove or weaken the title-gated direct-readback path until a replacement reproduces both runtime PASS results.

- Star Fox Zero JP (`00050000-101AFF00`): Run #25 FIXED by `vkGetQueryPoolResults` direct readback.
- Bayonetta 2 JP (`00050000-1011B900`): Run #26 FIXED by the same direct-readback path.
- PASS experiment HEAD: `5d758a096ee9409e7c25372a6caa9ad9d2378575` on `exp-bayo2-query-direct-readback`.
- `main` remains untouched at `58954b34d147b134d7b23ee61b2057f49da2c014`.

## Run #27 — mapped/direct side-by-side capture

- Run `34013912085`
- Job `101434315915`
- Head `77c47610c3c472198f13fb399f483691411c1c8c`
- CI SUCCESS
- Star Fox Zero JP v16

Selected mapped query-result memory:

`[QUERY_MAP_META] found=1 memoryType=4 heap=0 flags=0x0000000f requested=0x0000000e fallback=0`

Actual flags `0x0f` = DEVICE_LOCAL | HOST_VISIBLE | HOST_COHERENT | HOST_CACHED.

First completed divergence:

`direct=1192 mapped=0 selected=1192 mismatch=1`

The pattern persisted far beyond 100,000 completed query observations. The direct query-pool value remained correct and preserved the visual FIX.

## Run #28 — TRANSFER_WRITE -> HOST_READ barrier

- Run `34017106924`
- Job `101442707298`
- Head `79fbf25ab8a255fe15ad8210bad21a9a5491c34e`
- CI SUCCESS
- Runtime Star Fox Zero JP

Single variable: exact 8-byte buffer barrier after `vkCmdCopyQueryPoolResults`:

- TRANSFER / TRANSFER_WRITE
- HOST / HOST_READ

Runtime result: **FAIL to repair mapped path**.

The mapped result remained zero for essentially all nonzero direct results. Two rare mapped nonzero values exactly matched direct, proving the mapped pointer/offset is not globally unrelated to the target memory.

Conclusion: a missing transfer-to-host barrier alone is not the cause.

## Run #29 — explicit mapped-memory invalidate

- Run `34019347912`
- Job `101448913796`
- Head `7a71d5405f3d438d52dce9554eb93a0ee49a2ed2`
- CI SUCCESS
- Runtime build banner `Init Cemu 7a71d54`
- Star Fox Zero JP

Single added variable over the barrier experiment: call `vkInvalidateMappedMemoryRanges` on the exact 8-byte query slot before reading the mapped pointer.

Runtime capture `log(20260906-081927).zip`:

- `[QUERY_DIRECT]` observations: 299,255
- `cmdFinished=1`: 299,255 / 299,255
- `invalidate=VK_SUCCESS(0)`: 299,255 / 299,255
- `vkGetQueryPoolResults=VK_SUCCESS(0)`: 299,255 / 299,255
- direct nonzero: 299,094
- mapped nonzero: 2
- mismatch: 299,092
- exact direct/mapped agreement: 163 total, of which 161 were both zero and 2 were nonzero exact matches

The two nonzero mapped matches were:

- n=4000, queryIndex=870: direct=838 mapped=838
- n=248000, queryIndex=1001: direct=32 mapped=32

Runtime result: **FAIL to repair mapped path**.

Conclusion:

- HOST_COHERENT + explicit invalidate still leaves the mapped value stale/zero almost always.
- Therefore this is not explained by a missing host invalidate operation.
- Because rare values do arrive at the correct mapped location, a completely wrong bind/map offset is also unlikely.
- Direct `vkGetQueryPoolResults` remains the protected correct runtime result.

## Run #30 experiment — DEVICE_LOCAL intermediate query copy

Diagnostic commit:

`eb04e6f370c8bbf2ae9564e19edef8b6e8c7d266`

Single conceptual variable relative to Run #28:

For Star Fox Zero JP and Bayonetta 2 JP only:

`vkCmdCopyQueryPoolResults -> DEVICE_LOCAL intermediate buffer -> TRANSFER_WRITE/TRANSFER_READ barrier -> vkCmdCopyBuffer -> existing HOST_VISIBLE mapped buffer -> TRANSFER_WRITE/HOST_READ barrier -> CPU mapped read`

The failed explicit invalidate from Run #29 is removed. The direct `vkGetQueryPoolResults` value remains selected during the experiment, so the known visual FIX remains protected.

Purpose:

Determine whether Adreno specifically fails when `vkCmdCopyQueryPoolResults` writes directly into HOST_VISIBLE/HOST_CACHED memory, while ordinary `vkCmdCopyBuffer` device-local-to-host transfer remains functional.

## NEXT ACTION

1. Build Run #30 from `eb04e6f370c8bbf2ae9564e19edef8b6e8c7d266`.
2. Run Star Fox Zero JP first.
3. Confirm `[QUERY_INTERMEDIATE] allocated=1`.
4. Inspect `[QUERY_DIRECT] ... path=intermediate`.
5. Success criterion: nonzero `direct=N mapped=N mismatch=0` consistently.
6. If restored, test Bayonetta 2 with the same build and then consider the intermediate copy as the narrow Adreno-compatible permanent mapped readback path.
7. If still `mapped=0`, stop host-cache/barrier experiments and investigate `vkCmdCopyQueryPoolResults` execution/storage semantics on this driver more directly.
8. XCX remains separate; do not globalize blocking direct readback.
