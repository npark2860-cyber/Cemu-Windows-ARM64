# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-09-05 KST  
> 이전 대화를 추측해서 복원하지 말고 GitHub 문서를 source of truth로 사용한다.

## 0. 먼저 읽을 문서

1. `TECH_BIBLE.md`
2. `DEBUG_HISTORY.md`
3. `DEBUG_HISTORY_20260829_QUERY_COMPARE.md`
4. `DEBUG_HISTORY_20260905_BAYO2_TARGET0_RESOURCE_RUNTIME.md`
5. `DEBUG_HISTORY_20260905_BAYO2_TARGET0_PRODUCER_RESOURCE_RUNTIME.md`
6. `CURRENT_HANDOFF.md`

## 1. Current goal

Bayonetta 2 JP target0 CPU occlusion query `0x46a92ec8`가 동일한 six-draw producer fingerprint를 사용하면서 completed zero/nonzero 결과를 반복하는 이유를 좁힌다.

현재 단계는 behavior fix가 아니라 **target0 producer uniform vec4 delta observation**이다.

## 2. Repository / branch state

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

Main remains untouched by this experiment.

Known `main` HEAD:
`58954b34d147b134d7b23ee61b2057f49da2c014`

Handoff/docs branch:
`diag-bayo2-target0-resource-identity`

CI branch:
`diag-bayo2-target-query-draw-fingerprint`

Current CI branch HEAD:
`2f5d4080082219e096bfbf593d711c69fed807ce`

Current staging branch:
`diag-bayo2-target0-uniform-delta`

Run #12 producer-resource code checkpoint:
`4498bfe9c80c54ea1ac4df48355f27a1bf676e95`

Uniform-delta code commits after Run #12:

- `f4cfacf99a93336ac3a149117684d0580494371b` — add target0 producer uniform delta trace
- `2f5d4080082219e096bfbf593d711c69fed807ce` — chain uniform delta trace from producer-resource layer

Diff from Run #12 code is intentionally narrow:

- add `tools/diagnostics/Apply-Bayo2Target0UniformDeltaTrace.py`
- add four chaining lines to `Apply-Bayo2Target0ProducerResourceTrace.py`

No committed query/result/render/resource/draw behavior change is included.

## 3. Protected validated checkpoints

Run #10 — first validated downstream target0-resource build:

- commit `6b96fb4a0fceb6f1285ea6a39db82852d4ad8972`
- Run ID `33369558184`
- SUCCESS
- artifact ID `9750570882`
- artifact SHA-256 `9951398732e1185d0874c2d530e14b91829922d05791aae52498deeddd052127`

Run #11 — redundant normalization, also successful:

- commit `4f24fca6e0cc49d64bd14bca0b5ce1e586d2b59f`
- Run ID `33467898875`
- SUCCESS

Run #12 — target0 producer-resource build:

- commit `4498bfe9c80c54ea1ac4df48355f27a1bf676e95`
- Run ID `33939024628`
- SUCCESS
- artifact ID `9961710613`
- artifact SHA-256 `00ae9f6208ba2b592606778e980cc31e37ea7e0a25aad82a062c395bcfd1095d`

Do not rerun old validation stages.

## 4. Confirmed prior runtime — downstream target0 resource

Input:
`log (2).zip` from Run #10 artifact.

Key facts:

- target0 completed generations: 932
- completed zero dominates
- downstream `[BAYO2_RESOURCE]`: 12,949 rows
- fixed downstream pipeline `0x4addb8b25c8fc2bf`
- opposite-direction watch windows often overlap; duplicated labels for the same actual draw are not independent samples
- downstream VB resource families are identical for `0->NZ` and `NZ->0`
- downstream VS whole-block hash is frame-sensitive and cannot by itself separate transition direction

Also confirmed in the same capture:

- every target0 generation has exactly six producer draws
- zero and nonzero generations use the same six-draw producer pipeline/shader/state sequence

Therefore a different producer draw sequence/state fingerprint is not the cause.

## 5. 2026-09-05 Run #12 runtime — producer resource result

Input:
user-supplied `log (2)(1).zip` generated with Run #12 artifact.

Detailed source:
`DEBUG_HISTORY_20260905_BAYO2_TARGET0_PRODUCER_RESOURCE_RUNTIME.md`

Capture validity:

- `[BAYO2_TARGET_RESOURCE]`: 3,444 rows
- target0 completed GET generations: 573
- every completed generation has exactly six producer-resource rows
- final `gen=574` has producer rows but no completed GET before capture end; excluded from result-class comparison

Result classes:

- ZERO: 518 generations
- NONZERO: 55 generations

### Producer six-draw sequence

The same recurring pipeline order exists in both classes:

1. `7e005ef7a0ebc3c5`
2. `bb71fa356a5b48ce`
3. `bb71fa356a5b48ce`
4. `000909ced0b17a78`
5. `ead20dc8febd5234`
6. `bb71fa356a5b48ce`

Recurring VS:

- `e6fc4f385f9b0034`
- `93a12f899ed56598`

Recurring PS:

- `e2b9a6e6c2a4a0f8`
- `519954498085e510`
- `902ca3422dccc182`
- `362608e302d3de4c`

### Vertex resources

Across all six draw positions and both result classes:

- `vbCount=1`
- fixed `vbIdentity=ac3ef01be7bb148a`
- fixed sampled `vbContent=32e7595ae3520075`
- same guest VB address/size/stride family

Therefore completed ZERO/NONZERO is not explained by a different guest VB identity or the sampled VB content captured here.

### Constant buffers

Across both result classes:

- `vsCbCount=0`
- `psCbCount=0`
- `gsCbCount=0`

No CB identity/content discriminator exists in this path.

### Uniform-variable blocks

VS:

- both recurring VS families expose `vsVarSize=4096`
- whole-block VS hash changes generation-to-generation
- draws sharing the same VS family inside one generation share the same VS hash
- whole-block hash is therefore too coarse to identify the responsible field/value

PS:

- variable size 304 or 320 bytes depending on shader
- hashes change frequently
- some exact PS whole-block hashes occur in both ZERO and NONZERO classes

GS:

- no active GS variable block

Current narrowing:

**producer draw/state/VB/CB paths are no longer the discriminator. The remaining observed changing input class is VS/PS uniform-variable data. This is not yet proof that the changing uniforms are the cause.**

## 6. Active experiment — target0 producer uniform vec4 delta trace

New marker:
`[BAYO2_TARGET_UNIFORM]`

Scope:

- target0 only: `0x46a92ec8`
- only the two recurring VS and four recurring PS shader hashes above
- suppress repeated draws using the same shader in one target generation
- split each uniform-variable block into 16-byte vec4 slots
- compare each slot against the previous target generation for that shader
- log only changed slots
- include the actual four float values plus previous/current slot hash
- preserve `gen`, frame, draw, stage and shader correlation

Purpose:

At `0->NZ`, `NZ->0`, `0->0`, and `NZ->NZ` generations, identify which concrete uniform slots/values change and whether any transition-specific numeric pattern exists.

Observation-only constraints:

- do not alter query values/results/readiness
- do not alter visibility/culling
- do not alter pipeline/render state
- do not alter resource contents
- do not alter draw execution
- do not transplant XCX behavior

## 7. Current CI — Run #13

Workflow:
`Cemu ARM64 Bayo2 Target Query Draw Fingerprint Trace`

Run:
`#13`

Run ID:
`33945290442`

Head:
`2f5d4080082219e096bfbf593d711c69fed807ce`

Status at this handoff update:
**IN PROGRESS**

Do not start another CI run while Run #13 is active.

## 8. NEXT ACTION

1. Check Run #13 `33945290442` final status.
2. If failure:
   - recover exact first failing step/error
   - correct only the uniform-delta observation layer
   - do not change behavior semantics
3. If success:
   - confirm Build + Collect + Upload all succeed
   - confirm artifact exists
   - use only that artifact for the next Bayonetta 2 capture
4. Next runtime log must contain `[BAYO2_TARGET_UNIFORM]`.
5. Join uniform rows to target0 `[BAYO2_TARGET] GET` by `gen`.
6. Compare changed slot/value patterns around:
   - `0->NZ`
   - `NZ->0`
   - neighboring `0->0`
   - `NZ->NZ` where available
7. Prioritize transition-specific uniform slots that are not merely changing every frame in the same manner.
8. Do not introduce a behavior workaround before this numeric uniform result.

## 9. DO NOT ROLLBACK / DO NOT REPEAT

Never roll back:

- VS DEFAULT_VAL synthesize/linkage compatibility
- permanent PS DEFAULT_VAL linkage fix
- AArch64 generated-code cache/I-cache coherency fix
- known-good pre-e834 Vulkan compatibility behavior
- validated query/downstream/resource observation chain

Do not repeat:

- Bayo2 ready-zero as NOT_READY/default zero
- missing snapshot / overwritten-unconsumed explanation for these captures
- Bayo2 = XCX consumption-path assumption
- global ready-zero force-visible
- Position Invariance
- viewport depth-range clamp
- depthBiasClamp
- Force Maximum LOD / generic LOD experiments
- negativeOneToOne / shader depth conversion rollback
- RT barrier variants / forced render-pass split
- depthclip
- pipeline pNext
- VS auxHash key experiment
- f4c24000 conversions
- nested/duplicate query bookkeeping
- f544 Bayo primary-cause experiments
- XCX raw predication retry

## New-tab startup prompt

`Cemu Windows ARM64 / Adreno 작업 계속. GitHub의 TECH_BIBLE.md, DEBUG_HISTORY.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_RESOURCE_RUNTIME.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_PRODUCER_RESOURCE_RUNTIME.md, CURRENT_HANDOFF.md를 먼저 읽고 실제 branch/HEAD/Actions 상태와 대조해. CURRENT_HANDOFF NEXT ACTION부터 시작해. 현재 active experiment는 target0 0x46a92ec8 producer uniform vec4 delta trace이며 Run #13 33945290442의 최종 상태를 먼저 확인해. Bayo2/XCX query-consumption 차이를 유지하고 이미 배제된 실험을 반복하지 마. main은 건드리지 마.`
