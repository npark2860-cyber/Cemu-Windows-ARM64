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

Runtime capture `log(20260906-081927).zip`:

- `[QUERY_DIRECT]` observations: 299,255
- `cmdFinished=1`: 299,255 / 299,255
- `invalidate=VK_SUCCESS(0)`: 299,255 / 299,255
- `vkGetQueryPoolResults=VK_SUCCESS(0)`: 299,255 / 299,255
- direct nonzero: 299,094
- mapped nonzero: 2
- mismatch: 299,092

Runtime result: **FAIL to repair mapped path**.

Conclusion: HOST_COHERENT + explicit invalidate still leaves mapped stale/zero almost always. Missing invalidate is closed as the explanation.

## Run #30 — DEVICE_LOCAL intermediate query copy

- Run `34021733515`
- Job `101455446048`
- Head `6532c82d1c75b983465bcac40cf36f947462e0b9`
- Runtime build banner `Init Cemu 6532c82`
- Star Fox Zero JP
- Capture `log(20260906-091505).zip`

Path for target titles:

`vkCmdCopyQueryPoolResults -> DEVICE_LOCAL intermediate -> vkCmdCopyBuffer -> HOST_VISIBLE mapped buffer -> CPU mapped read`

Runtime observations:

- `[QUERY_INTERMEDIATE] allocated=1 size=8192`
- `[QUERY_DIRECT]` observations: 218,590
- direct nonzero: 218,450
- mapped nonzero: 1
- mismatch: 218,449
- first completed query: `direct=1192 mapped=0 selected=1192 mismatch=1`
- protected direct result remained selected

User runtime observation: **small object flicker/regression appeared**. It was not the original large flicker pattern, but the build was visibly worse than the previous fully-correct direct-readback build.

Conclusion: **FAIL**.

- DEVICE_LOCAL intermediate + `vkCmdCopyBuffer` did not repair the mapped result path.
- It also introduced a visual regression despite direct still being selected.
- Do not continue tuning or promote this intermediate-copy path.
- The new GPU copy/barrier path must be removed before further diagnosis.

The Run #30 result increases suspicion that `vkCmdCopyQueryPoolResults` itself is unreliable on this Qualcomm Windows Vulkan path, rather than the problem being only HOST_VISIBLE destination visibility. This is still a working hypothesis, not yet a final proof.

## Run #31 — protected direct-readback A/B restoration

CI branch has been restored to the exact Run #26 direct-readback experiment script, with no intermediate buffer/copy/barrier additions.

- CI head: `be3064da39e2913719de6fc800e7f417d28a0aec`
- Run `34024292927`
- Status at update: IN PROGRESS
- Diagnostic branch restore commit: `790a945780ea561518dd072d9f73c0e3e89b4700`

Purpose: reproduce the known visual PASS and prove the small Run #30 flicker was caused by the intermediate experiment rather than a new external/runtime change.

## NEXT ACTION

1. Let Run #31 complete.
2. Run Star Fox Zero JP in the same scene/conditions used for Run #30.
3. Primary criterion: the small object flicker must disappear and return to the Run #25/#26 fully-correct appearance.
4. If visual PASS returns, close Run #30 as a confirmed experiment-induced regression.
5. Preserve the direct-readback path unchanged before any next low-level query-copy diagnostic.
6. Do not repeat barrier/invalidate/intermediate-copy experiments under the same conditions.
7. XCX remains separate; do not globalize blocking direct readback.
