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
9. `CURRENT_HANDOFF.md`

## 1. Current goal

Bayonetta 2 JP target0 CPU occlusion query `0x46a92ec8`가 동일한 six-draw producer path에서 completed ZERO/NONZERO를 반복하는 이유를 좁힌다.

현재 단계는 behavior fix가 아니라 **target0 producer sampled-texture resource identity/content observation**이다.

## 2. Repository / branch state

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Main remains untouched. Known `main` HEAD: `58954b34d147b134d7b23ee61b2057f49da2c014`.

Handoff/docs branch: `diag-bayo2-target0-resource-identity`.

CI branch: `diag-bayo2-target-query-draw-fingerprint`.

Current CI branch HEAD: `552b8d4b500bdd959b6b3b4bb5eb2fcba157b4b6`.

Current staging branch: `diag-bayo2-target0-texture-resource`.

Run #15 exact-index code checkpoint:
`8a735a583410f28d6b4c72770b120f39c001f41f`.

Texture-resource commits after Run #15:

- `4684c251706e16acfc2277909fd0e5fd6c8b42a0` — add target0 sampled-texture resource trace
- `552b8d4b500bdd959b6b3b4bb5eb2fcba157b4b6` — chain texture trace after exact index trace

Diff from Run #15 is intentionally narrow:

- add `tools/diagnostics/Apply-Bayo2Target0TextureResourceTrace.py`
- add four chaining lines to `Apply-Bayo2Target0IndexContentTrace.py`

No query/result/readiness/render/resource/draw behavior change is committed.

## 3. Protected checkpoints

- Run #10 — downstream target0 resource — `6b96fb4a...` — Run `33369558184` — SUCCESS
- Run #11 — normalization — `4f24fca...` — Run `33467898875` — SUCCESS
- Run #12 — producer resource — `4498bfe9...` — Run `33939024628` — SUCCESS
- Run #13 — producer uniform vec4 delta — `2f5d4080...` — Run `33945290442` — SUCCESS
- Run #14 — actual depth identity/history — `21b671c6...` — Run `33947749589` — SUCCESS
- Run #15 — exact index-buffer content — `8a735a58...` — Run `33951247306` — SUCCESS

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
- guest VB identity
- sampled guest VB content
- VS/PS/GS constant-buffer identity/content
- PS full uniform state
- transition-specific VS uniform vec4 delta family
- actual bound depth surface identity
- observed depth write/update bookkeeping
- exact guest index-buffer content for all six producer draws

Do not repeat these observations unless a new contradiction appears.

## 6. Run #15 runtime — `log(5).zip`

Detailed source: `DEBUG_HISTORY_20260905_BAYO2_TARGET0_INDEX_CONTENT_RUNTIME.md`.

Capture validity:

- `[BAYO2_TARGET_INDEX]`: 2,916 rows
- index generations observed: 486
- exactly six rows for every observed generation
- completed target0 GET generations: 485
- 485/485 completed generations have exactly six index rows
- final gen 486 incomplete and excluded

Results:

- ZERO 459
- NONZERO 26
- `FIRST` 1
- `0->0` 432
- `0->NZ` 26
- `NZ->0` 26
- `NZ->NZ` 0

Every completed generation has the exact same six-draw full-byte index signature:

1. `1314dac0`, 8394 U16_BE, 16788 bytes, hash `499385a99b630874`
2. `13151d00`, 129 U16_BE, 258 bytes, hash `18db65c38bfd4da1`
3. `13151ec0`, 483 U16_BE, 966 bytes, hash `dc23544499f56815`
4. `13152340`, 6 U16_BE, 12 bytes, hash `067eea34dcd244c9`
5. `13152400`, 1560 U16_BE, 3120 bytes, hash `e085dfaa370d1269`
6. `131530c0`, 504 U16_BE, 1008 bytes, hash `9642728cfc61ecf2`

Full-signature result:

- all completed generations unique signature count: 1
- ZERO signature count: 1
- NONZERO signature count: 1
- intersection: 1

Conclusion:

**exact guest index-buffer content is not the ZERO/NONZERO discriminator.**

## 7. Active experiment — sampled texture resource/content

New marker: `[BAYO2_TARGET_TEXTURE]`.

Scope is limited to the recurring target0 producer shader families already observed:

VS:

- `e6fc4f385f9b0034`
- `93a12f899ed56598`

PS:

- `e2b9a6e6c2a4a0f8`
- `519954498085e510`
- `902ca3422dccc182`
- `362608e302d3de4c`

For each shader, once per target0 generation, log only texture units actually referenced by `textureUnitList`:

- stage / shader / generation / frame / draw
- texture count and unit
- all seven guest texture resource register words
- raw guest image/mip addresses from resource words 2/3
- 4 KiB guest-memory prefix hash for image and mip address
- sampler assignment index
- depth-compare usage

If a shader references no texture units, emit an explicit `textureCount=0` row.

Constraints:

- no texture lookup/creation from the diagnostic helper
- no GPU readback
- no texture mutation
- no descriptor mutation
- no query/result/readiness mutation
- no render-state/draw behavior change

The 4 KiB hashes are sampled guest-memory prefixes, not proof of full texture byte equality and not a GPU image readback. Interpret accordingly.

## 8. Current CI — Run #16

Workflow: `Cemu ARM64 Bayo2 Target Query Draw Fingerprint Trace`

Run: `#16`

Run ID: `33958269235`

Head: `552b8d4b500bdd959b6b3b4bb5eb2fcba157b4b6`

Status at this handoff update: **QUEUED**.

Do not start another CI run while Run #16 is active.

## 9. NEXT ACTION

1. Check Run #16 `33958269235` final status.
2. If failure, recover the exact first failing error and correct only the sampled-texture observation layer.
3. If success, confirm Build + Collect + Upload and artifact existence.
4. Use only the Run #16 artifact for the next Bayo2 severe-flicker capture.
5. Next runtime log must contain `[BAYO2_TARGET_TEXTURE]`.
6. Join texture rows to target0 completed GET by `gen` and compare ZERO/NONZERO shader-by-shader/unit-by-unit.
7. First compare complete seven-word resource identity and raw image/mip addresses.
8. Then compare image/mip 4 KiB guest prefix hashes, remembering these are sampled guest RAM and not GPU readback.
9. If texture resource identity/content also fails to discriminate, do not blindly add more broad resource logging; reassess host/GPU texture state versus occlusion-query backend semantics.
10. Do not introduce a behavior workaround before this result.

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

## New-tab startup prompt

`Cemu Windows ARM64 / Adreno 작업 계속. GitHub의 TECH_BIBLE.md, DEBUG_HISTORY.md, DEBUG_HISTORY_20260829_QUERY_COMPARE.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_RESOURCE_RUNTIME.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_PRODUCER_RESOURCE_RUNTIME.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_UNIFORM_DELTA_RUNTIME.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_DEPTH_IDENTITY_RUNTIME.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_INDEX_CONTENT_RUNTIME.md, CURRENT_HANDOFF.md를 먼저 읽고 실제 branch/HEAD/Actions 상태와 대조해. CURRENT_HANDOFF NEXT ACTION부터 시작해. 현재 active experiment는 target0 0x46a92ec8 sampled-texture resource/content trace이며 Run #16 33958269235의 최종 상태를 먼저 확인해. Bayo2/XCX query-consumption 차이를 유지하고 이미 배제된 실험을 반복하지 마. main은 건드리지 마.`