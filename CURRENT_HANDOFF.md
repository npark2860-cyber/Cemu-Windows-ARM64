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
8. `CURRENT_HANDOFF.md`

## 1. Current goal

Bayonetta 2 JP target0 CPU occlusion query `0x46a92ec8`가 동일한 six-draw producer path에서 completed ZERO/NONZERO를 반복하는 이유를 좁힌다.

현재 단계는 behavior fix가 아니라 **target0 producer index-buffer content observation**이다.

## 2. Repository / branch state

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Main remains untouched. Known `main` HEAD: `58954b34d147b134d7b23ee61b2057f49da2c014`.

Handoff/docs branch: `diag-bayo2-target0-resource-identity`.

CI branch: `diag-bayo2-target-query-draw-fingerprint`.

Current validated CI code checkpoint before index-content work: `21b671c62c6e723bd83c74434e752de8955031c4`.

Current staging branch before next instrumentation: `diag-bayo2-target0-depth-identity`.

## 3. Protected checkpoints

- Run #10 — downstream target0 resource — `6b96fb4a...` — Run `33369558184` — SUCCESS
- Run #11 — normalization — `4f24fca...` — Run `33467898875` — SUCCESS
- Run #12 — producer resource — `4498bfe9...` — Run `33939024628` — SUCCESS
- Run #13 — producer uniform vec4 delta — `2f5d4080...` — Run `33945290442` — SUCCESS
- Run #14 — actual depth identity/history — `21b671c6...` — Run `33947749589` — SUCCESS

Do not rerun old validation stages.

## 4. Query-consumption facts that remain fixed

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
- guest VB identity
- sampled guest VB content
- VS/PS/GS constant-buffer identity/content
- PS full uniform state
- transition-specific VS uniform vec4 delta family
- actual bound depth surface identity
- observed depth write/update bookkeeping

Do not repeat these observations unless a new contradiction appears.

## 6. Run #13 runtime — uniform delta

Source: `DEBUG_HISTORY_20260905_BAYO2_TARGET0_UNIFORM_DELTA_RUNTIME.md`.

Key result:

- 457 completed target0 generations
- ZERO 431 / NONZERO 26
- 22/26 NONZERO generations are isolated one-generation spikes
- isolated NZ vs following ZERO VS changed-slot-set mean Jaccard 0.995, median 1.0
- no repeated NZ-specific A->B->A vec4 transient
- exact complete PS uniform states occur in both ZERO and NONZERO classes

Conclusion: do not keep drilling the same uniform layer.

## 7. Run #14 runtime — actual depth identity/history

Input: user-supplied `log(4).zip`.

Detailed source: `DEBUG_HISTORY_20260905_BAYO2_TARGET0_DEPTH_IDENTITY_RUNTIME.md`.

Capture validity:

- `[BAYO2_TARGET_DEPTH]`: 381 rows
- completed target0 generations: 380
- 380/380 completed generations have a depth row
- final gen 381 is incomplete and excluded

Result classes:

- ZERO 354
- NONZERO 26
- `0->0` 329
- `0->NZ` 24
- `NZ->0` 24
- `NZ->NZ` 2

Actual depth identity is identical across all completed ZERO/NONZERO generations:

- `DB_HTILE_DATA_BASE = 0x00f54428`
- actual/reconstructed depth phys = `0xf5442800`
- bound texture phys = `0xf5442800`
- same size/info/view/control
- same format/tile/swizzle/1280x720/pitch/view
- bound on every generation
- GPU-updated on every generation
- `lastUpdateEventCounter=8`, `lastUpdateFrameCounter=0`, `reloadCount=1` fixed

Dynamic history:

- `dataUpdateFrame == current frame` on 380/380
- `accessFrame == current frame` on 380/380
- `lastUnflushedRTDrawcallIndex == query begin draw` on 377/380; three -9 anomalies are not NZ-specific
- `lastWriteEventCounter` delta is explained by elapsed frame/draw work; conditioned on frame gap, ZERO and NZ transition distributions overlap strongly

Conclusion:

**actual depth identity/history is not the ZERO/NONZERO discriminator.**

Do not reopen the already closed f544 destructive/seeded behavior experiments.

## 8. NEXT ACTION — index-buffer content only

The six target0 producer draw index identities are fixed in every observed generation and all use index type 4 = U16_BE:

1. `0x1314dac0`, count 8394
2. `0x13151d00`, count 129
3. `0x13151ec0`, count 483
4. `0x13152340`, count 6
5. `0x13152400`, count 1560
6. `0x131530c0`, count 504

Next observation:

- exact-hash guest index bytes for each producer draw (`count * 2` bytes)
- correlate six hashes by target generation to completed ZERO/NONZERO GET
- record only target0 producer draws
- no index mutation
- no query/result/readiness mutation
- no render-state mutation
- do not add sampled-texture observation in the same experiment

If index content is also identical across result classes, sampled texture identity/content becomes the next missing producer input before any query-driver semantic A/B.

## 9. DO NOT ROLLBACK / DO NOT REPEAT

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

## New-tab startup prompt

`Cemu Windows ARM64 / Adreno 작업 계속. GitHub의 TECH_BIBLE.md, DEBUG_HISTORY.md, DEBUG_HISTORY_20260829_QUERY_COMPARE.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_RESOURCE_RUNTIME.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_PRODUCER_RESOURCE_RUNTIME.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_UNIFORM_DELTA_RUNTIME.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_DEPTH_IDENTITY_RUNTIME.md, CURRENT_HANDOFF.md를 먼저 읽고 실제 branch/HEAD/Actions 상태와 대조해. CURRENT_HANDOFF NEXT ACTION부터 시작해. 현재 next experiment는 target0 0x46a92ec8 producer index-buffer exact content hash다. Bayo2/XCX query-consumption 차이를 유지하고 이미 배제된 실험을 반복하지 마. main은 건드리지 마.`