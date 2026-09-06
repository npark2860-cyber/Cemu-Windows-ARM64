# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-09-06 KST
> GitHub branch / HEAD / Actions / debug history를 source of truth로 사용한다.

## Repository state

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Protected `main` remains untouched:

`58954b34d147b134d7b23ee61b2057f49da2c014`

Protected runtime-PASS branch:

- `exp-bayo2-query-direct-readback`
- HEAD `5d758a096ee9409e7c25372a6caa9ad9d2378575`

Docs branch:

- `diag-bayo2-target0-resource-identity`

Diagnostic development branch:

- `diag-query-mapped-direct-divergence`
- restored direct-readback HEAD `790a945780ea561518dd072d9f73c0e3e89b4700`

CI trigger branch:

- `diag-bayo2-target-query-draw-fingerprint`
- current HEAD `be3064da39e2913719de6fc800e7f417d28a0aec`

## Protected runtime PASS — never roll back

Star Fox Zero JP `00050000-101AFF00`:

- Run #25
- direct `vkGetQueryPoolResults`
- visual flicker FIXED

Bayonetta 2 JP `00050000-1011B900`:

- Run #26
- same direct `vkGetQueryPoolResults`
- visual flicker FIXED

The direct result remains selected until a replacement path reproduces both PASS results.

## Query-consumption separation

Star Fox Zero / Bayonetta 2:

- CPU occlusion query type=0
- exported CPU query consumption active

XCX:

- GPU occlusion query type=2
- exported CPU GET consumption not observed

Do not transplant Star Fox/Bayo2 behavior to XCX without evidence.

## Confirmed mapped-path failures

Run #27:

- HOST_VISIBLE/HOST_COHERENT/HOST_CACHED memory type 4
- completed queries repeatedly `direct>0 / mapped=0`

Run #28:

- exact-range `TRANSFER_WRITE -> HOST_READ` barrier
- FAIL; mapped remained zero almost always

Run #29:

- explicit `vkInvalidateMappedMemoryRanges`
- 299,255/299,255 VK_SUCCESS
- mapped nonzero only 2 times
- FAIL

Therefore missing host barrier/invalidate is closed under these captures.

## Run #30 — DEVICE_LOCAL intermediate experiment FAIL + visual regression

- Run `34021733515`
- Job `101455446048`
- Head `6532c82d1c75b983465bcac40cf36f947462e0b9`
- Runtime banner `Init Cemu 6532c82`
- Star Fox Zero JP
- Capture `log(20260906-091505).zip`

Target path:

`vkCmdCopyQueryPoolResults -> DEVICE_LOCAL intermediate -> vkCmdCopyBuffer -> HOST_VISIBLE mapped buffer`

Results:

- `[QUERY_INTERMEDIATE] allocated=1 size=8192`
- `[QUERY_DIRECT]` observations: 218,590
- direct nonzero: 218,450
- mapped nonzero: 1
- mismatch: 218,449
- first query: `direct=1192 mapped=0 selected=1192 mismatch=1`

Runtime user observation:

- small object flicker appeared
- not identical to the old large flicker, but visibly worse than the previously fully-correct direct-readback build

Conclusion:

- intermediate path did not repair mapped results
- it introduced a visual regression
- **do not continue or promote this path**
- remove it before further diagnosis

Working hypothesis strengthened, but not yet proven: the Qualcomm Windows Vulkan issue may lie in `vkCmdCopyQueryPoolResults` execution/storage itself rather than only destination host visibility.

## Current experiment — Run #31 protected baseline restoration

The CI script has been restored to the exact Run #26 direct-readback implementation. No intermediate allocation/copy/barriers/invalidate are present in the target experiment.

- CI head `be3064da39e2913719de6fc800e7f417d28a0aec`
- Run #31 `34024292927`
- Status at update: IN PROGRESS

Purpose: A/B verify that removing the Run #30 intermediate path restores the fully-correct Star Fox appearance.

## NEXT ACTION

1. Let Run #31 complete.
2. Test Star Fox Zero JP in the same scene/conditions as Run #30.
3. Primary criterion: Run #30's small object flicker disappears completely.
4. If PASS, close Run #30 as confirmed experiment-induced visual regression.
5. Keep the exact direct-readback baseline protected before the next low-level diagnostic.
6. Do not repeat the barrier/invalidate/intermediate-copy experiments under the same conditions.
7. XCX remains separate; do not globalize blocking direct readback.

## DO NOT ROLLBACK

- Star Fox Zero Run #25 direct-readback FIX
- Bayonetta 2 Run #26 direct-readback FIX
- VS DEFAULT_VAL synthesize/linkage fixes
- AArch64 generated-code cache/I-cache fix
- known-good pre-e834 Vulkan baseline
- `main` untouched state
