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
7. `CURRENT_HANDOFF.md`

## 1. Current goal

Bayonetta 2 JP target0 CPU occlusion query `0x46a92ec8`가 동일한 six-draw producer path에서 completed ZERO/NONZERO를 반복하는 이유를 좁힌다.

현재 단계는 behavior fix가 아니라 **실제 depth surface identity/history observation**이다.

## 2. Repository / branch state

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

Main remains untouched.

Known `main` HEAD:
`58954b34d147b134d7b23ee61b2057f49da2c014`

Handoff/docs branch:
`diag-bayo2-target0-resource-identity`

CI branch:
`diag-bayo2-target-query-draw-fingerprint`

Current CI branch HEAD:
`21b671c62c6e723bd83c74434e752de8955031c4`

Current staging branch:
`diag-bayo2-target0-depth-identity`

Depth-observation commits after Run #13:

- `280f1303f5a82ccfd26dd440abb723102b6c2b7d` — add target0 depth identity/history trace
- `21b671c62c6e723bd83c74434e752de8955031c4` — chain depth trace from producer-resource layer

Diff from Run #13 is intentionally narrow:

- add `tools/diagnostics/Apply-Bayo2Target0DepthIdentityTrace.py`
- add four chaining lines to `Apply-Bayo2Target0ProducerResourceTrace.py`

No query/result/readiness/render/resource/draw behavior change is committed.

## 3. Protected validated checkpoints

Run #10 — downstream target0-resource:

- commit `6b96fb4a0fceb6f1285ea6a39db82852d4ad8972`
- Run ID `33369558184`
- SUCCESS
- artifact ID `9750570882`

Run #11 — redundant normalization:

- commit `4f24fca6e0cc49d64bd14bca0b5ce1e586d2b59f`
- Run ID `33467898875`
- SUCCESS

Run #12 — producer-resource:

- commit `4498bfe9c80c54ea1ac4df48355f27a1bf676e95`
- Run ID `33939024628`
- SUCCESS
- artifact ID `9961710613`

Run #13 — producer uniform vec4 delta:

- commit `2f5d4080082219e096bfbf593d711c69fed807ce`
- Run ID `33945290442`
- SUCCESS

Do not rerun these old validation stages.

## 4. Query-consumption facts that remain fixed

Bayonetta 2:

- CPU occlusion query type=0 only in these captures
- exported `GX2QueryGetOcclusionResult()` heavily consumed
- completed ready-zero is real completed/consumed data under the captured conditions
- no `GET_NOT_READY`, missing-snapshot, repeat-generation, or overwritten-unconsumed explanation
- do not globally force ready-zero visible

XCX:

- GPU occlusion query type=2
- exported CPU `GX2QueryGetOcclusionResult()` consumption was not observed
- no exported conditional-render markers / no raw `IT_SET_PREDICATION` in dedicated capture
- historical XCX `0x100000` seed remains XCX-only

Do not assume Bayo2 and XCX use the same consumption path.

## 5. Closed/demoted Bayo2 target0 producer discriminators

Across the validated capture chain, completed ZERO/NONZERO is not explained by:

- a different six-draw producer sequence
- pipeline/shader/draw-argument fingerprint
- primitive/clip/raster/depth-control/color-control/target-mask state
- guest VB identity
- sampled guest VB content
- VS/PS/GS constant-buffer identity/content
- PS full uniform-variable state
- a transition-specific VS uniform vec4 delta family

Do not repeat these observations unless a new contradiction appears.

## 6. Run #13 runtime — `log(3).zip`

Detailed source:
`DEBUG_HISTORY_20260905_BAYO2_TARGET0_UNIFORM_DELTA_RUNTIME.md`

Capture validity:

- `[BAYO2_TARGET_UNIFORM]`: 140,860 rows
- `[BAYO2_TARGET_RESOURCE]`: 2,742 rows
- target0 producer draws: 2,742
- completed target0 generations: 457
- exactly 6 producer draws per completed generation

Results:

- ZERO: 431
- NONZERO: 26
- `0->0`: 406
- `0->NZ`: 24
- `NZ->0`: 24
- `NZ->NZ`: 2
- 22 of 26 NONZERO generations are isolated single-generation spikes
- only two two-generation NZ episodes: `152-153`, `398-399`
- nonzero sample sums: 8,418..15,993

Uniform result:

- recurring VS changed-slot counts are essentially the same for `0->0`, `0->NZ`, and `NZ->0`
- 127 VS slots change in every `0->NZ` and every `NZ->0`
- isolated NZ generation vs immediate following ZERO changed-slot set: VS mean Jaccard 0.995, median 1.0
- no repeated exact `A->B->A` VS vec4 transient; any slot appears at most 2/22 isolated NZ events
- exact complete PS uniform states occur in both ZERO and NONZERO classes
  - `e2b9...`: 10/26 NZ generations share a state also seen on ZERO
  - each of `5199...`, `902c...`, `3626...`: 7/26 NZ generations share a ZERO state

Conclusion:

**uniform data changes continuously, but this trace did not find an NZ-specific uniform discriminator. Do not keep drilling the same uniform layer.**

## 7. Critical depth blind spot discovered

The old target draw trace recorded `DB_DEPTH_BASE/SIZE/INFO/VIEW` and showed `DB_DEPTH_BASE=0`.

This did **not** identify the real depth surface.

Cemu `GX2SetDepthBuffer()` currently writes:

- `DB_DEPTH_BASE = 0`
- `DB_HTILE_DATA_BASE = physical(imagePtr) >> 8`

`LatteRenderTarget.cpp` reconstructs:

`depthBufferPhysMem = DB_HTILE_DATA_BASE << 8`

Therefore previous `depth=00000000/...` stability must not be interpreted as proof that the actual depth surface identity was stable.

This is a newly identified observation gap. It is not a restart of the closed f544 Bayo experiments.

## 8. Active experiment — actual depth identity/history

New marker:
`[BAYO2_TARGET_DEPTH]`

Log once per target0 generation:

- `DB_HTILE_DATA_BASE`
- reconstructed raw physical address
- depth size/info/view/control
- current `LatteMRT::GetDepthAttachment()` presence
- bound depth texture physical address / format / tile mode / swizzle / dimensions / pitch / view
- `isUpdatedOnGPU`
- readback flag
- `lastWriteEventCounter`
- `lastUpdateEventCounter`
- update/data-update frame counters
- reload/access/unflushed-draw bookkeeping

Constraints:

- no depth readback
- no depth content hash yet
- no depth mutation
- no query/result mutation
- no behavior workaround
- do not mix index-buffer or sampled-texture experiments into this build

## 9. Current CI — Run #14

Workflow:
`Cemu ARM64 Bayo2 Target Query Draw Fingerprint Trace`

Run:
`#14`

Run ID:
`33947749589`

Head:
`21b671c62c6e723bd83c74434e752de8955031c4`

Status at this handoff update:
**IN PROGRESS**

Do not start another CI run while Run #14 is active.

## 10. NEXT ACTION

1. Check Run #14 `33947749589` final status.
2. If failure, recover exact first failing error and correct only the new depth observation layer.
3. If success, confirm Build + Collect + Upload and artifact existence.
4. Next runtime log must contain `[BAYO2_TARGET_DEPTH]`.
5. Join depth rows to target0 GET by `gen`.
6. Compare ZERO/NONZERO and transition directions for:
   - actual `htile`/depth physical identity
   - bound depth texture identity
   - write/update event counters and frame bookkeeping
7. If actual depth identity/history is identical across result classes, only then choose the next missing producer input (index content or sampled texture identity) or a query-driver semantic A/B.
8. Do not introduce a behavior workaround before this depth result.

## 11. DO NOT ROLLBACK / DO NOT REPEAT

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

`Cemu Windows ARM64 / Adreno 작업 계속. GitHub의 TECH_BIBLE.md, DEBUG_HISTORY.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_RESOURCE_RUNTIME.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_PRODUCER_RESOURCE_RUNTIME.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_UNIFORM_DELTA_RUNTIME.md, CURRENT_HANDOFF.md를 먼저 읽고 실제 branch/HEAD/Actions 상태와 대조해. CURRENT_HANDOFF NEXT ACTION부터 시작해. 현재 active experiment는 target0 0x46a92ec8 actual depth identity/history trace이며 Run #14 33947749589의 최종 상태를 먼저 확인해. Bayo2/XCX query-consumption 차이를 유지하고 이미 배제된 실험을 반복하지 마. main은 건드리지 마.`
