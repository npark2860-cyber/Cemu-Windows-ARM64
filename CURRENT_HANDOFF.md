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
8. `CURRENT_HANDOFF.md`

## 1. Repository state

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Protected main remains untouched:

`58954b34d147b134d7b23ee61b2057f49da2c014`

Docs branch:

`diag-bayo2-target0-resource-identity`

CI branch:

`diag-bayo2-target-query-draw-fingerprint`

Current CI HEAD:

`5d758a096ee9409e7c25372a6caa9ad9d2378575`

Current experiment branch:

`exp-bayo2-query-direct-readback`

Experiment HEAD:

`5d758a096ee9409e7c25372a6caa9ad9d2378575`

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
- focused query trace proved FINISH -> CPU GET exact value agreement across all observed generations

XCX JP `00050000-10116100`:

- GPU occlusion query type=2
- exported CPU GET consumption not observed
- no exported conditional-render marker
- dedicated raw capture had no `IT_SET_PREDICATION`
- historical XCX `0x100000` seed remains XCX-only

Do not transplant Bayo2/Star Fox behavior to XCX without evidence.

## 4. Major runtime breakthrough — direct Vulkan query readback

Baseline Vulkan occlusion result path:

`vkCmdCopyQueryPoolResults -> persistently mapped result buffer -> CPU read`

Controlled A/B path:

`vkGetQueryPoolResults()` after owning command buffer completion.

### Run #25 — Star Fox only

- Run ID `34007865487`
- Job ID `101418283084`
- Head `7154c20d24abc574a09ba7733f05a987b3446420`
- CI: SUCCESS
- Build / Collect / Upload: SUCCESS

Runtime result:

**Star Fox Zero flicker FIXED.**

This is a protected runtime PASS checkpoint.

### Run #26 — Star Fox + Bayonetta 2

- Run ID `34011609042`
- Job ID `101428310700`
- Head `5d758a096ee9409e7c25372a6caa9ad9d2378575`
- CI: SUCCESS
- every workflow step including Build, Collect and Upload: SUCCESS

Run #26 extends the exact same direct `vkGetQueryPoolResults()` path to Bayonetta 2 JP while leaving all other titles on the existing mapped-buffer path.

Runtime result:

**Bayonetta 2 flicker FIXED.**

Therefore Star Fox Zero + Bayonetta 2 are now both runtime PASS under the same direct-query-readback substitution.

Detailed record:

`DEBUG_HISTORY_20260906_STARFOX_BAYO2_DIRECT_QUERY_READBACK_RUNTIME.md`

## 5. Current interpretation

Strongly confirmed common failure domain:

**Vulkan occlusion-query result readback / visibility path on Windows ARM64 Adreno for these CPU type=0 query consumers.**

The previous broad Platinum/depth/visibility hypothesis is now narrowed substantially.

However the exact low-level mechanism is still OPEN.

Do NOT yet claim:

- that all Vulkan games should globally use `vkGetQueryPoolResults()`
- that HOST_NON_COHERENT memory is the cause
- that mapped-buffer data itself is always stale
- that XCX shares this path

The Adreno device exposes a HOST_VISIBLE + HOST_COHERENT + HOST_CACHED memory type, so the old non-coherent fallback hypothesis is not established.

## 6. Current task

Find the exact reason the existing mapped-buffer query-result path diverges from direct `vkGetQueryPoolResults()` on Adreno, then replace the temporary title-gated behavior A/B with the narrowest safe permanent fix.

Priority inspection area:

- occlusion result buffer allocation / selected memory properties
- `vkCmdCopyQueryPoolResults` synchronization and visibility
- command-buffer completion guarantee before mapped CPU read
- host visibility / invalidate/flush requirements for the actually selected memory type
- query pool reuse/reset/copy ordering
- any Adreno-specific driver behavior that makes the mapped-copy path unreliable

## 7. NEXT ACTION

1. Keep Run #25 and Run #26 as immutable runtime PASS references.
2. Do **not** remove the title-gated direct-readback path until a replacement fix reproduces both PASS results.
3. Instrument the existing mapped query-result path to log:
   - selected memory type index
   - actual memory property flags
   - query index
   - owning command-buffer ID / completion state
   - mapped value
   - direct `vkGetQueryPoolResults()` value side-by-side
4. Capture Star Fox first because it is the simpler reproduction.
5. Determine the first point where mapped/direct values diverge.
6. Apply one narrow synchronization/visibility fix based on that evidence.
7. Re-test Star Fox and Bayonetta 2.
8. Then regression-test unaffected titles, especially XCX and BOTW.
9. Do not globally switch every title to blocking direct query reads unless evidence proves that is the correct architecture-level fix.

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

## New-tab startup prompt

`Cemu Windows ARM64 / Adreno 작업 계속. GitHub의 TECH_BIBLE.md, DEBUG_HISTORY.md, DEBUG_HISTORY_20260829_QUERY_COMPARE.md, DEBUG_HISTORY_20260906_STARFOX_QUERY_FOCUS_RUNTIME.md, DEBUG_HISTORY_20260906_STARFOX_BAYO2_DIRECT_QUERY_READBACK_RUNTIME.md, CURRENT_HANDOFF.md를 먼저 읽고 실제 branch/HEAD/Actions와 대조해. main은 58954b34d147b134d7b23ee61b2057f49da2c014로 untouched. 현재 핵심 PASS는 Run #25에서 Star Fox Zero flicker FIXED, Run #26에서 Bayonetta 2 flicker FIXED이며 둘 다 direct vkGetQueryPoolResults 경로다. NEXT ACTION은 기존 vkCmdCopyQueryPoolResults -> mapped buffer 경로가 Adreno에서 왜 direct 결과와 달라지는지 정확히 규명하고 좁은 영구 수정을 만드는 것이다. XCX는 type=2/no exported GET 계열로 분리 유지하고, 이미 닫힌 실험은 반복하지 마.`
