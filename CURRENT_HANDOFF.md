# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-09-06 KST
> GitHub branch / HEAD / Actions / debug history를 source of truth로 사용한다.

## Repository state

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Protected `main` remains untouched:

`58954b34d147b134d7b23ee61b2057f49da2c014`

Protected runtime branch:

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

## Protected direct-readback baseline

Star Fox Zero JP `00050000-101AFF00`:

- Run #25
- direct `vkGetQueryPoolResults`
- original/large flicker FIXED
- **important correction:** user A/B recheck confirms a smaller residual object flicker was already present in this original fixed build
- therefore Run #25 is not a visually perfect baseline; it is the major-flicker-fixed baseline

Bayonetta 2 JP `00050000-1011B900`:

- Run #26
- same direct `vkGetQueryPoolResults`
- reproduced flicker FIXED

Do not remove or weaken the direct-readback path while investigating the remaining Star Fox symptom.

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

Run #30:

- DEVICE_LOCAL intermediate query copy + `vkCmdCopyBuffer` to mapped host buffer
- 218,590 observations
- direct nonzero 218,450
- mapped nonzero 1
- mismatch 218,449
- FAIL to repair mapped path

Important correction:

- Run #30 is **not** proven to have introduced the small-object flicker.
- User rechecked Run #25 and confirmed the same residual flicker was already present immediately after the original major-flicker fix.
- Retract the earlier visual-regression attribution to Run #30.

Therefore missing host barrier/invalidate/intermediate transfer are closed as mapped-path repair attempts under these captures.

## Run #31 — direct baseline restoration

- Run `34024292927`
- Job `101462397659`
- Head `be3064da39e2913719de6fc800e7f417d28a0aec`
- CI SUCCESS
- Runtime banner `Init Cemu be3064d`
- Capture `log(20260906-102908).zip`

Exact Run #26 direct-readback script restored; no intermediate allocation/copy/barriers/invalidate.

Results:

- `[QUERY_INTERMEDIATE]`: absent
- `[QUERY_DIRECT]`: 170,384
- `vkResult=0`: 170,384 / 170,384
- direct nonzero: 170,264
- mapped nonzero: 0
- `selected == direct`: 170,384 / 170,384
- `mismatch=0`: 120, all both-zero
- nonzero direct/mapped agreement: 0

The direct workaround remains functional while the mapped path remains stale/zero.

## Current problem split

Star Fox now has two distinct symptoms:

1. **Original/large flicker**
   - fixed by Run #25 direct `vkGetQueryPoolResults`
   - protected fix

2. **Small-object residual flicker**
   - present already in Run #25
   - still unresolved
   - not attributable to Run #30
   - must now be investigated separately

The broken mapped path is still a real independent bug, but it is not yet proven to be the cause of the remaining small-object flicker because direct values are selected for target accumulation.

## NEXT ACTION

1. Keep exact Run #25/Run #31 direct-readback behavior intact.
2. Use the same reproducible Star Fox scene/object where the small residual flicker is visible.
3. Correlate the remaining flicker against exact query/draw activity while direct values remain selected.
4. Do not repeat barrier/invalidate/intermediate-copy experiments without new evidence.
5. Do not describe Run #30 as the cause of the small flicker.
6. Keep Bayonetta 2 protected and XCX separate.
7. Do not globally switch every title to blocking direct reads.

## DO NOT ROLLBACK

- Star Fox Zero Run #25 direct-readback major-flicker FIX
- Bayonetta 2 Run #26 direct-readback FIX
- VS DEFAULT_VAL synthesize/linkage fixes
- AArch64 generated-code cache/I-cache fix
- known-good pre-e834 Vulkan baseline
- `main` untouched state
