# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-09-05 KST  
> 이전 대화를 추측해서 복원하지 말고 GitHub 문서를 source of truth로 사용한다.

## 0. 먼저 읽을 문서

1. `TECH_BIBLE.md`
2. `DEBUG_HISTORY.md`
3. `DEBUG_HISTORY_20260829_QUERY_COMPARE.md`
4. `DEBUG_HISTORY_20260905_BAYO2_TARGET0_RESOURCE_RUNTIME.md`
5. `DEBUG_HISTORY_20260905_BAYO2_TARGET0_PRODUCER_RESOURCE_RUNTIME.md`
6. `DEBUG_HISTORY_20260905_BAYO2_TARGET0_UNIFORM_DELTA_RUNTIME.md`
7. `DEBUG_HISTORY_20260905_BAYO2_TARGET0_DEPTH_IDENTITY_RUNTIME.md`
8. `DEBUG_HISTORY_20260905_BAYO2_TARGET0_INDEX_CONTENT_RUNTIME.md`
9. `DEBUG_HISTORY_20260905_BAYO2_TARGET0_TEXTURE_RESOURCE_RUNTIME.md`
10. `CURRENT_HANDOFF.md`

## 1. Current goal

Bayonetta 2 JP target0 CPU occlusion query `0x46a92ec8`가 동일한 six-draw producer path에서 completed ZERO/NONZERO를 반복하는 이유를 좁힌다.

현재 active experiment는 **PS unit11 GPU-updated depth-compare texture `0xf57c8000`의 bound-object write/update history observation**이다. Behavior workaround 단계가 아니다.

## 2. Repository / branch state

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Main remains untouched. Known `main` HEAD: `58954b34d147b134d7b23ee61b2057f49da2c014`.

Handoff/docs branch: `diag-bayo2-target0-resource-identity`.

CI branch: `diag-bayo2-target-query-draw-fingerprint`.

Current CI branch HEAD: `ce80d7a68dc88b90f299f9e2dfd53b8e267c92d9`.

Current staging branch: `diag-bayo2-target0-depthcompare-history`.

Run #16 sampled-texture checkpoint: `552b8d4b500bdd959b6b3b4bb5eb2fcba157b4b6`.

Depth-compare history commits after Run #16:

- `1fcb9f2cc1a9b8fd49e444e01c60469e87841635` — add unit11 depth-compare texture history trace
- `ce80d7a68dc88b90f299f9e2dfd53b8e267c92d9` — chain the new trace after sampled-texture observation

Diff from Run #16 is intentionally narrow:

- add `tools/diagnostics/Apply-Bayo2Target0DepthCompareTextureHistoryTrace.py`
- add four chaining lines to `Apply-Bayo2Target0IndexContentTrace.py`

No query/result/readiness/render/texture/draw behavior change is committed.

## 3. Protected checkpoints

- Run #10 — downstream target0 resource — `6b96fb4a...` — Run `33369558184` — SUCCESS
- Run #11 — normalization — `4f24fca...` — Run `33467898875` — SUCCESS
- Run #12 — producer resource — `4498bfe9...` — Run `33939024628` — SUCCESS
- Run #13 — producer uniform vec4 delta — `2f5d4080...` — Run `33945290442` — SUCCESS
- Run #14 — actual depth identity/history — `21b671c6...` — Run `33947749589` — SUCCESS
- Run #15 — exact index-buffer content — `8a735a58...` — Run `33951247306` — SUCCESS
- Run #16 — sampled-texture resource/content — `552b8d4b...` — Run `33958269235` — SUCCESS

Do not rerun old validation stages.

## 4. Fixed query-consumption facts

Bayonetta 2:

- CPU occlusion query type=0
- exported `GX2QueryGetOcclusionResult()` heavily consumed
- completed ready-zero is real completed/consumed data in these captures
- no GET_NOT_READY / missing-snapshot / overwritten-unconsumed explanation
- do not globally force ready-zero visible

XCX:

- GPU occlusion query type=2
- exported CPU `GX2QueryGetOcclusionResult()` consumption not observed
- no exported conditional-render marker / no raw `IT_SET_PREDICATION` in dedicated capture
- historical XCX `0x100000` seed remains XCX-only

Do not assume Bayo2 and XCX use the same consumption path.

## 5. Closed/demoted target0 producer discriminators

Completed ZERO/NONZERO is not explained by:

- different six-draw producer sequence
- pipeline/shader/draw-argument fingerprint
- primitive/clip/raster/depth-control/color-control/target-mask state
- guest VB identity / sampled VB content
- VS/PS/GS constant-buffer identity/content
- PS full uniform state
- transition-specific VS uniform vec4 delta family
- actual bound target depth surface identity (`0xf5442800`)
- observed target depth write/update bookkeeping
- exact guest index-buffer content for all six draws
- sampled-texture unit selection
- sampled-texture seven-word register identity
- sampled image/mip guest address identity
- sampler assignment / depth-compare flags
- readable 4 KiB guest-memory texture prefixes

Do not repeat these observations unless a new contradiction appears.

## 6. Run #16 runtime — `log (2)(2).zip`

Detailed source: `DEBUG_HISTORY_20260905_BAYO2_TARGET0_TEXTURE_RESOURCE_RUNTIME.md`.

Capture validity:

- `[BAYO2_TARGET_TEXTURE]`: 15,599 rows
- texture generations observed: 821
- exactly 19 rows per generation
- completed target0 GET generations: 820
- final gen 821 incomplete and excluded

Results:

- ZERO 767
- NONZERO 53
- FIRST 1
- `0->0` 717
- `0->NZ` 49
- `NZ->0` 49
- `NZ->NZ` 4
- 49 NONZERO episodes: 46 single-generation, 2 two-generation, 1 three-generation

All 820 completed generations collapse to **one identical logged sampled-texture signature** across the recurring producer shaders.

VS families use no sampled textures. The four PS families use fixed subsets of units 0/1/2/3/11.

The critical exception is PS unit11:

- all four PS shaders use it with `depthCompare=1`
- fixed resource address `0xf57c8000`
- Run #16 guest-memory hash is always 0 only because the helper rejects addresses `>=0x50000000`; this is not a content hash
- runtime lifecycle shows `0xf57c8000` is a 1024x2048 format 0x11 depth texture, used as a depth attachment and delete-time `gpuUpdated=1`

Therefore broad texture resource identity is closed, but GPU content/history of `0xf57c8000` remains unobserved.

## 7. Active experiment — PS unit11 depth-compare texture history

New marker: `[BAYO2_TARGET_DEPTHCOMPARE]`.

Once per target0 generation, using the already-bound PS unit11 view only, record:

- register physical address and bound texture physical identity
- depth/stencil/format/tile/swizzle/view geometry
- data-defined / GPU-updated / readback / dynamic-reload flags
- `lastWriteEventCounter`
- `lastUpdateEventCounter`
- update/data-update frame counters
- reload count
- last access frame
- last unflushed RT draw index
- `texDataHash2`

Constraints:

- no texture lookup or creation
- no GPU readback
- no texture mutation
- no query/result/readiness mutation
- no render-state/draw behavior change

The purpose is to determine whether NONZERO correlates with a different GPU depth-texture write/update history before considering a query-driver semantic A/B.

## 8. Current CI — Run #17

Workflow: `Cemu ARM64 Bayo2 Target Query Draw Fingerprint Trace`

Run: `#17`

Run ID: `33971629934`

Head: `ce80d7a68dc88b90f299f9e2dfd53b8e267c92d9`

Status at this handoff update: **IN PROGRESS**.

Last checked job `101321059139`: checkout in progress.

Do not start another CI run while Run #17 is active.

## 9. NEXT ACTION

1. Check Run #17 `33971629934` final status.
2. If failure, recover the exact first failing error and correct only the new depth-compare-history observation layer.
3. If success, confirm Build + Collect + Upload and artifact existence.
4. Use only the Run #17 artifact for the next severe-flicker capture.
5. Next runtime log must contain `[BAYO2_TARGET_DEPTHCOMPARE]`.
6. Join one history row per generation to target0 completed GET result.
7. Compare ZERO/NONZERO and transition directions for `writeEvent`, update/data-update frame, access frame, unflushed RT draw and all fixed identity flags.
8. If history is identical after controlling frame gap, the next step is not broader resource logging; shift toward a narrowly designed Vulkan/Adreno occlusion-query or GPU synchronization semantic A/B.
9. Do not introduce a behavior workaround before this result.

## 10. DO NOT ROLLBACK / DO NOT REPEAT

Never roll back:

- VS DEFAULT_VAL synthesize/linkage compatibility
- permanent PS DEFAULT_VAL linkage fix
- AArch64 generated-code cache/I-cache coherency fix
- known-good pre-e834 Vulkan compatibility behavior
- validated query/downstream/resource observation chain

Do not repeat:

- Bayo2 ready-zero as NOT_READY/default zero
- missing snapshot / overwritten-unconsumed explanation
- Bayo2 = XCX consumption-path assumption
- global ready-zero force-visible
- Position Invariance
- viewport depth-range clamp
- `depthBiasClamp`
- Force Maximum LOD / generic LOD
- negativeOneToOne / shader depth conversion rollback
- RT barrier variants / forced render-pass split
- depthclip
- pipeline pNext
- VS auxHash key
- f4c24000 conversions
- nested/duplicate query bookkeeping
- f544 Bayo primary-cause experiments
- XCX raw predication retry
- exact target0 index-content hashing under the same conditions
- broad target0 sampled-texture register/prefix hashing under the same conditions

## New-tab startup prompt

`Cemu Windows ARM64 / Adreno 작업 계속. GitHub의 TECH_BIBLE.md, DEBUG_HISTORY.md, DEBUG_HISTORY_20260829_QUERY_COMPARE.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_RESOURCE_RUNTIME.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_PRODUCER_RESOURCE_RUNTIME.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_UNIFORM_DELTA_RUNTIME.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_DEPTH_IDENTITY_RUNTIME.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_INDEX_CONTENT_RUNTIME.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_TEXTURE_RESOURCE_RUNTIME.md, CURRENT_HANDOFF.md를 먼저 읽고 실제 branch/HEAD/Actions 상태와 대조해. CURRENT_HANDOFF NEXT ACTION부터 시작해. 현재 active experiment는 target0 0x46a92ec8 PS unit11 0xf57c8000 depth-compare texture history trace이며 Run #17 33971629934의 최종 상태를 먼저 확인해. Bayo2/XCX query-consumption 차이를 유지하고 이미 배제된 실험을 반복하지 마. main은 건드리지 마.`
