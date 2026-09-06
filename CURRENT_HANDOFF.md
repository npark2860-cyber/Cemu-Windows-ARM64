# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-09-06 KST
> GitHub branch / HEAD / Actions / debug history를 source of truth로 사용한다. 이전 대화를 추측해서 복원하지 않는다.

## 0. 먼저 읽을 문서

1. `TECH_BIBLE.md`
2. `DEBUG_HISTORY.md`
3. `DEBUG_HISTORY_20260829_QUERY_COMPARE.md`
4. `DEBUG_HISTORY_20260906_STARFOX_QUERY_FOCUS_RUNTIME.md`
5. `DEBUG_HISTORY_20260906_STARFOX_BAYO2_DIRECT_QUERY_READBACK_RUNTIME.md`
6. `DEBUG_HISTORY_20260906_QUERY_MAPPED_DIRECT_DIVERGENCE.md`
7. `CURRENT_HANDOFF.md`

## 1. Repository state

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Protected main remains untouched:

`58954b34d147b134d7b23ee61b2057f49da2c014`

Docs branch:

`diag-bayo2-target0-resource-identity`

CI branch:

`diag-bayo2-target-query-draw-fingerprint`

Current CI HEAD:

`7a71d5405f3d438d52dce9554eb93a0ee49a2ed2`

Protected runtime-PASS experiment branch:

`exp-bayo2-query-direct-readback`

Protected runtime-PASS experiment HEAD:

`5d758a096ee9409e7c25372a6caa9ad9d2378575`

Current mapped/direct diagnostic branch:

`diag-query-mapped-direct-divergence`

Current diagnostic HEAD:

`7a71d5405f3d438d52dce9554eb93a0ee49a2ed2`

## 2. Permanent baseline — do not roll back

Never roll back:

- VS producer-side `DEFAULT_VAL` synthesize/linkage fix
- permanent PS DEFAULT_VAL linkage compatibility
- AArch64 generated-code cache / I-cache coherency fix
- known-good pre-e834 Vulkan behavior
- Runtime Diagnostics coverage
- Star Fox Zero / Bayonetta 2 title-gated direct `vkGetQueryPoolResults()` PASS path until a replacement reproduces both runtime PASS results

## 3. Query-consumption facts

Bayonetta 2 JP `00050000-1011B900`:

- CPU occlusion query type=0
- exported `GX2QueryGetOcclusionResult()` heavily consumed
- completed ready-zero is real
- direct Vulkan query readback fixes flicker

Star Fox Zero JP `00050000-101AFF00` v16:

- CPU occlusion query type=0
- exported CPU GET active
- `GET_NOT_READY = 0`
- direct Vulkan query readback fixes flicker

XCX JP `00050000-10116100`:

- GPU occlusion query type=2
- exported CPU GET consumption not observed
- keep separate; do not transplant Star Fox/Bayo2 behavior without evidence

## 4. Protected runtime PASS references

### Run #25 — Star Fox

- Run ID `34007865487`
- Job ID `101418283084`
- Head `7154c20d24abc574a09ba7733f05a987b3446420`
- Runtime: **Star Fox Zero flicker FIXED**

### Run #26 — Star Fox + Bayonetta 2

- Run ID `34011609042`
- Job ID `101428310700`
- Head `5d758a096ee9409e7c25372a6caa9ad9d2378575`
- Runtime: **Bayonetta 2 flicker FIXED**

Do not remove this direct-readback path yet.

## 5. Run #27 — mapped/direct divergence confirmed

- Run ID `34013912085`
- Job ID `101434315915`
- Head `77c47610c3c472198f13fb399f483691411c1c8c`
- CI: SUCCESS

Selected persistent query-result memory:

`memoryType=4 flags=0x0000000f fallback=0`

Actual flags:

- DEVICE_LOCAL
- HOST_VISIBLE
- HOST_COHERENT
- HOST_CACHED

First completed divergence:

`cmdFinished=1 vkResult=0 direct=1192 mapped=0 selected=1192 mismatch=1`

The same pattern persists throughout the capture.

## 6. Run #28 — TRANSFER_WRITE -> HOST_READ barrier

- Run ID `34017106924`
- Job ID `101442707298`
- Head `79fbf25ab8a255fe15ad8210bad21a9a5491c34e`
- CI: SUCCESS
- Runtime: Star Fox graphics remained normal because direct result stayed selected

Single changed variable:

`vkCmdCopyQueryPoolResults` exact 8-byte destination range gets:

`TRANSFER_WRITE -> HOST_READ`

### Runtime result: mapped-path repair FAILED

Full-log parse:

- parsed `[QUERY_DIRECT]`: 230,184
- `cmdFinished=1`: 230,184 / 230,184
- `vkGetQueryPoolResults` success: 230,184 / 230,184
- direct nonzero: 230,032
- mapped nonzero: 2
- mismatches: 230,030 (~99.9331%)

Only two mapped nonzero reads appeared, and both exactly matched direct:

- `n=120`: `488207 == 488207`
- `n=225000`: `189539 == 189539`

Therefore:

- buffer memory binding/map offsets are not universally wrong
- missing transfer->host barrier alone is not the fix
- host-visible value becomes correct only extremely sporadically

## 7. Current experiment — Run #29 explicit invalidate

Single new variable relative to Run #28:

After owning command-buffer completion and before reading the mapped pointer, call:

`vkInvalidateMappedMemoryRanges`

for the exact query-result 8-byte range on Star Fox Zero / Bayonetta 2 target titles.

Run #28 barrier remains in place.

The direct result still remains selected, preserving the known FIXED graphics path.

Commit:

`7a71d5405f3d438d52dce9554eb93a0ee49a2ed2`

Run #29:

- Run ID `34019347912`
- Job ID `101448913796`
- Current status: **IN PROGRESS**

New log field:

`invalidate=<VkResult>`

## 8. NEXT ACTION

1. Complete Run #29 build.
2. Run Star Fox Zero JP first.
3. Verify `invalidate=0`.
4. Primary success criterion:
   - `direct=N mapped=N mismatch=0` for nonzero results.
5. If explicit invalidate restores mapped agreement, treat this as a Qualcomm Windows Vulkan coherent-host-cache visibility quirk and test Bayonetta 2.
6. If invalidate succeeds but mapped remains zero, stop spending time on simple host-cache synchronization. Next experiment: `vkCmdCopyQueryPoolResults` into a device-local intermediate buffer, then ordinary `vkCmdCopyBuffer` into the mapped host-visible result buffer.
7. Keep direct readback as protected fallback until a replacement reproduces both Star Fox and Bayonetta 2 PASS.
8. XCX remains separate.

## 9. Closed / do not repeat

Do not repeat:

- HOST_NON_COHERENT as Run #27 cause
- command buffer simply unfinished
- query-pool result itself being zero/wrong
- transfer->host barrier alone as the mapped-path repair
- previously closed Bayo2 depth/resource/pipeline experiments

## New-tab startup prompt

`Cemu Windows ARM64 / Adreno 작업 계속. GitHub의 CURRENT_HANDOFF.md와 DEBUG_HISTORY_20260906_QUERY_MAPPED_DIRECT_DIVERGENCE.md를 먼저 읽고 실제 branch/HEAD/Actions와 대조해. main은 58954b34d147b134d7b23ee61b2057f49da2c014로 untouched. Star Fox Zero와 Bayonetta 2의 direct vkGetQueryPoolResults FIXED 상태는 절대 되돌리지 마. Run #28에서 TRANSFER_WRITE -> HOST_READ barrier를 넣어도 230,184 records 중 mapped nonzero는 2개뿐이라 barrier 단독은 FAIL로 닫혔다. 현재 Run #29는 barrier 유지 + host read 직전 vkInvalidateMappedMemoryRanges 한 변수 실험이다. NEXT ACTION부터 진행하고 XCX는 별도 유지해.`
