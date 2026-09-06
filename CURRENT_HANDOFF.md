# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-09-06 KST
> GitHub branch / HEAD / Actions / debug history를 source of truth로 사용한다. 이전 대화를 추측해서 복원하지 않는다.

## 0. 먼저 읽을 문서

1. `TECH_BIBLE.md`
2. `DEBUG_HISTORY.md`
3. `DEBUG_HISTORY_20260829_QUERY_COMPARE.md`
4. `DEBUG_HISTORY_20260906_BAYO2_TARGET0_DEPTHCOMPARE_RUNTIME.md`
5. `DEBUG_HISTORY_20260905_STARFOX_BAYO2_F57C8000_COMMON_DEPTH_PATH.md`
6. `DEBUG_HISTORY_20260906_STARFOX_QUERY_FOCUS_RUNTIME.md`
7. `DEBUG_HISTORY_20260906_STARFOX_BAYO2_DIRECT_QUERY_READBACK_RUNTIME.md`
8. `DEBUG_HISTORY_20260906_QUERY_MAPPED_DIRECT_DIVERGENCE.md`
9. `CURRENT_HANDOFF.md`

## 1. Repository state

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Protected main remains untouched:

`58954b34d147b134d7b23ee61b2057f49da2c014`

Docs branch:

`diag-bayo2-target0-resource-identity`

CI branch:

`diag-bayo2-target-query-draw-fingerprint`

Current CI HEAD:

`79fbf25ab8a255fe15ad8210bad21a9a5491c34e`

Protected runtime-PASS experiment branch:

`exp-bayo2-query-direct-readback`

Protected runtime-PASS experiment HEAD:

`5d758a096ee9409e7c25372a6caa9ad9d2378575`

Current mapped/direct diagnostic branch:

`diag-query-mapped-direct-divergence`

Current diagnostic HEAD:

`79fbf25ab8a255fe15ad8210bad21a9a5491c34e`

## 2. Permanent baseline — do not roll back

Never roll back:

- VS producer-side `DEFAULT_VAL` synthesize/linkage fix
- permanent PS DEFAULT_VAL linkage compatibility
- AArch64 generated-code cache / I-cache coherency fix
- known-good pre-e834 Vulkan behavior:
  - swapchain loadOp LOAD
  - SIMULTANEOUS_USE command buffers
  - DrawBackbufferQuad clear restore
  - no in-renderpass clear attachments
- Runtime Diagnostics coverage

## 3. Query-consumption facts

Bayonetta 2 JP `00050000-1011B900`:

- CPU occlusion query type=0
- exported `GX2QueryGetOcclusionResult()` heavily consumed
- completed ready-zero is a real completed result
- `GET_NOT_READY` absent in clean captures
- FINISH sample sums match CPU GET values

Star Fox Zero JP `00050000-101AFF00` v16:

- CPU occlusion query type=0
- exported `GX2QueryGetOcclusionResult()` active
- `GET_NOT_READY = 0`
- focused query trace proved FINISH -> CPU GET exact value agreement across observed generations

XCX JP `00050000-10116100`:

- GPU occlusion query type=2
- exported CPU GET consumption not observed
- no exported conditional-render marker
- dedicated raw capture had no `IT_SET_PREDICATION`
- historical XCX `0x100000` seed remains XCX-only

Do not transplant Bayo2/Star Fox behavior to XCX without evidence.

## 4. Protected runtime breakthrough — direct Vulkan query readback

Baseline Vulkan occlusion result path:

`vkCmdCopyQueryPoolResults -> persistently mapped result buffer -> CPU read`

Controlled A/B path:

`vkGetQueryPoolResults()` after owning command buffer completion.

### Run #25 — Star Fox only

- Run ID `34007865487`
- Job ID `101418283084`
- Head `7154c20d24abc574a09ba7733f05a987b3446420`
- CI: SUCCESS
- Runtime: **Star Fox Zero flicker FIXED**

This is an immutable runtime PASS checkpoint.

### Run #26 — Star Fox + Bayonetta 2

- Run ID `34011609042`
- Job ID `101428310700`
- Head `5d758a096ee9409e7c25372a6caa9ad9d2378575`
- CI: SUCCESS
- Runtime: **Bayonetta 2 flicker FIXED**

Run #26 keeps Star Fox Zero FIXED and extends the exact same title-gated direct `vkGetQueryPoolResults()` path to Bayonetta 2 JP. Other titles remain on the mapped-buffer path.

Do not remove or weaken this direct-readback path until a replacement reproduces both runtime PASS results.

## 5. Run #27 — mapped/direct divergence confirmed

- Run ID `34013912085`
- Job ID `101434315915`
- Head `77c47610c3c472198f13fb399f483691411c1c8c`
- CI: SUCCESS
- Runtime title: Star Fox Zero JP v16

Selected persistent query-result memory:

`[QUERY_MAP_META] found=1 memoryType=4 heap=0 flags=0x0000000f requested=0x0000000e fallback=0`

Actual memory flags `0x0f`:

- DEVICE_LOCAL
- HOST_VISIBLE
- HOST_COHERENT
- HOST_CACHED

Therefore non-coherent invalidate is not the cause in this capture.

First completed divergence:

`queryIndex=1023 cmdBuffer=2813 cmdFinished=1 vkResult=0 direct=1192 mapped=0 selected=1192 mismatch=1`

The same `direct>0 / mapped=0 / cmdFinished=1` pattern persists far into the capture. This is not a single early stale read.

Current confirmed failure domain:

**device query result is correct, but the `vkCmdCopyQueryPoolResults -> persistent mapped buffer -> host read` path lacks the required device-to-host visibility guarantee on this Adreno path.**

Fence/command-buffer completion alone is insufficient to guarantee host visibility of device writes. The narrow Vulkan dependency under test is:

`TRANSFER_WRITE -> HOST_READ`

Detailed record:

`DEBUG_HISTORY_20260906_QUERY_MAPPED_DIRECT_DIVERGENCE.md`

## 6. Current experiment — Run #28

Single changed variable:

After the title-gated `vkCmdCopyQueryPoolResults`, add a `VkBufferMemoryBarrier` for the exact 8-byte query-result range:

- source stage: `VK_PIPELINE_STAGE_TRANSFER_BIT`
- source access: `VK_ACCESS_TRANSFER_WRITE_BIT`
- destination stage: `VK_PIPELINE_STAGE_HOST_BIT`
- destination access: `VK_ACCESS_HOST_READ_BIT`

The successful direct `vkGetQueryPoolResults()` value remains the selected runtime result for Star Fox Zero and Bayonetta 2. FIXED behavior is intentionally preserved during this A/B.

Run #28:

- Run ID `34017106924`
- Job ID `101442707298`
- Head `79fbf25ab8a255fe15ad8210bad21a9a5491c34e`
- Status at this handoff update: **IN PROGRESS**

## 7. NEXT ACTION

1. Complete Run #28 build and obtain its artifact.
2. Run Star Fox Zero JP first.
3. Inspect `[QUERY_MAP_META]` and `[QUERY_DIRECT]`.
4. Primary success criterion for nonzero results:
   - before: `direct=N mapped=0 mismatch=1`
   - expected after barrier: `direct=N mapped=N mismatch=0`
5. Keep direct readback as the selected protected result during this test.
6. If mapped/direct agreement is restored, run Bayonetta 2 with the same barrier build.
7. Only after both titles retain visual PASS and mapped/direct agreement is proven should the barrier be considered for the narrow permanent mapped path.
8. Then regression-test unaffected titles, especially XCX and BOTW.
9. Do not globally switch every title to blocking direct query reads.
10. XCX remains separate because it is type=2/no exported CPU GET in captures.

## 8. Closed / do not repeat

Do not repeat already closed Bayo2 experiments under the same conditions:

- Position Invariance
- viewport depth clamp
- depthBiasClamp
- generic LOD / Force Maximum LOD
- negativeOneToOne / shader Z conversion experiments
- broad RT barriers / forced render-pass split
- depthclip / pipeline pNext / VS auxHash key
- f544 depth-surface identity/history experiments
- exact index-buffer content
- producer VB/CB/uniform fingerprints
- sampled texture register/prefix identity
- `f57c8000` obvious texture-object bookkeeping
- global ready-zero force-visible

Do not repeat as live hypotheses:

- HOST_NON_COHERENT as the Run #27 cause: selected memory is HOST_COHERENT.
- command buffer simply not finished: divergence occurs with `cmdFinished=1`.
- query pool result itself is zero/wrong: direct `vkGetQueryPoolResults()` returns the correct nonzero values and fixes both games.

## New-tab startup prompt

`Cemu Windows ARM64 / Adreno 작업 계속. GitHub의 CURRENT_HANDOFF.md와 연결된 DEBUG_HISTORY 문서를 읽고 실제 branch/HEAD/Actions와 대조해. main은 58954b34d147b134d7b23ee61b2057f49da2c014로 untouched. Star Fox Zero와 Bayonetta 2의 direct vkGetQueryPoolResults FIXED 상태는 절대 되돌리지 마. Run #27에서 HOST_COHERENT memoryType=4 flags=0x0f인데 cmdFinished=1 상태에서도 direct>0 / mapped=0 divergence가 지속됨을 확정했다. 현재 Run #28은 vkCmdCopyQueryPoolResults 뒤 TRANSFER_WRITE -> HOST_READ barrier 한 변수만 추가한 테스트다. NEXT ACTION부터 진행하고 XCX는 type=2/no exported GET 계열로 분리 유지해.`
