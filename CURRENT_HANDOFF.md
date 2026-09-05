# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-09-05 KST  
> 이전 대화를 추측해서 복원하지 말고 GitHub 문서를 source of truth로 사용한다.

## 0. 먼저 읽을 문서

1. `TECH_BIBLE.md`
2. `DEBUG_HISTORY.md`
3. `DEBUG_HISTORY_20260829_QUERY_COMPARE.md`
4. `DEBUG_HISTORY_20260905_BAYO2_TARGET0_RESOURCE_RUNTIME.md`
5. `CURRENT_HANDOFF.md`

## 1. Current goal

Bayonetta 2 JP target0 CPU occlusion query `0x46a92ec8`가 동일한 six-draw producer fingerprint를 사용하면서 completed zero/nonzero 결과를 반복하는 이유를 좁힌다.

현재 단계는 behavior fix가 아니라 **target0 query-producer resource identity/content observation**이다.

## 2. Repository / branch state

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

Main remains untouched by this experiment.

Known `main` HEAD from prior verification:
`58954b34d147b134d7b23ee61b2057f49da2c014`

Handoff/docs branch:
`diag-bayo2-target0-resource-identity`

CI branch:
`diag-bayo2-target-query-draw-fingerprint`

Current CI branch HEAD:
`4498bfe9c80c54ea1ac4df48355f27a1bf676e95`

Staging branch:
`diag-bayo2-target0-producer-resource`

Staging/CI code commits added after the validated Run #11 code:

- `44483ae5519e7aebec2e8c41ea9289c9cc903897` — add target0 producer resource trace
- `4498bfe9c80c54ea1ac4df48355f27a1bf676e95` — chain producer resource trace

Diff from previous CI HEAD `4f24fca...` is intentionally narrow:

- add `tools/diagnostics/Apply-Bayo2Target0ProducerResourceTrace.py`
- add four chaining lines to `Apply-Bayo2TargetQueryDrawFingerprintTrace.py`

No committed baseline renderer/query behavior change is included.

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

Do not rerun these old validation stages.

## 4. 2026-09-05 runtime capture — confirmed

Input:
user-supplied `log (2).zip` generated with the correct Run #10 target0-resource artifact.

Detailed result:
`DEBUG_HISTORY_20260905_BAYO2_TARGET0_RESOURCE_RUNTIME.md`

Key confirmed facts:

### Target0 GET

- 932 completed generations
- `FIRST`: 1
- `0->0`: 810
- `0->NZ`: 58
- `NZ->NZ`: 5
- `NZ->0`: 58

### Downstream resource trace

- `[BAYO2_RESOURCE]`: 12,949 rows
- 58 `0->NZ` watches and 58 `NZ->0` watches
- fixed pipeline `0x4addb8b25c8fc2bf`

Vertex buffers:

- `vbCount=1` always
- 20 unique VB identity/content/address tuples
- both transition directions contain exactly the same 20-tuple set
- first post-transition frame also contains the same 20-tuple set on both sides
- no direction-exclusive VB resource family found

Uniforms for this downstream pipeline:

- VS/PS/GS constant-buffer counts are all zero
- PS/GS variable size/hash are zero
- VS variable size is always 4096 bytes
- aggregate VS hash is frame-sensitive: every one of 4,736 observed hashes belongs to one actual frame only

Therefore the current aggregate VS hash cannot separate transition direction from ordinary frame-to-frame data changes.

### Overlapping watch control

- 87 actual frames were covered by opposite-direction watch windows simultaneously
- 3,172 unique draws were duplicated under opposite watch labels
- all captured state/resource fields for the same actual draw matched exactly
- inconsistencies: 0

Do not treat these duplicates as independent samples.

## 5. Strongest new narrowing — target0 query producer itself

The same runtime log contains all target0 `[BAYO2_TARGET] DRAW` producer fingerprints.

- zero-result generations: 869
- nonzero-result generations: 63
- every generation contains exactly six target0 producer draws
- total producer draws: 5,592

Across zero and nonzero generations:

- same four pipeline hashes
- same shader sets
- same draw arguments/index addresses
- same primitive/clip/raster/depth/color/target-mask states
- both color0 identities occur in both result classes

Ignoring the rotating color0 address, all 932 generations collapse to **one identical six-draw producer sequence**, shared by zero and nonzero results.

Therefore:

**completed zero/nonzero is not explained by a different target0 producer draw sequence or a different recorded producer pipeline/shader/render-state fingerprint.**

The next discriminator is resource content used by those six producer draws.

## 6. Active experiment — target0 producer resource trace

New marker:
`[BAYO2_TARGET_RESOURCE] DRAW`

For every draw while target0 `0x46a92ec8` is actively bracketing the producer query, record:

- query generation / frame / draw sequence
- pipeline / draw arguments
- VB identity/content/address-size-stride
- VS/PS/GS CB identity/content
- VS/PS/GS variable size/hash

The trace reuses the already compiled Run #10/11 resource-summary helpers.

Observation-only constraints remain unchanged:

- do not alter query value/result/readiness
- do not alter visibility/culling
- do not alter pipeline/render state
- do not alter resource contents
- do not alter draw execution
- do not transplant XCX behavior

## 7. Current CI — Run #12

Workflow:
`Cemu ARM64 Bayo2 Target Query Draw Fingerprint Trace`

Run:
`#12`

Run ID:
`33939024628`

Head:
`4498bfe9c80c54ea1ac4df48355f27a1bf676e95`

Status at this handoff update:
**IN PROGRESS**

Job:
`101232598569`

At last check:
- job started successfully
- checkout was in progress
- no failure had occurred yet

**Do not start another CI run while Run #12 is active.**

## 8. NEXT ACTION

1. Check Run #12 `33939024628` final status.
2. If failure:
   - recover the exact first failing step/error
   - make only the minimum compile/apply correction inside the new producer-resource observation layer
   - do not change behavior semantics
3. If success:
   - confirm Collect + Upload succeeded
   - confirm an artifact actually exists
   - use only that artifact for the next Bayo2 capture
4. Next runtime capture must contain `[BAYO2_TARGET_RESOURCE] DRAW`.
5. Join producer-resource rows by `gen` to `[BAYO2_TARGET] GET` result and compare completed ZERO vs NZ generations draw-by-draw.
6. Primary questions:
   - do producer VB identity/content hashes differ between ZERO and NZ?
   - do producer VS/PS/GS CB identities/content differ?
   - do producer uniform-variable hashes differ for the same one-of-six draw position?
7. Do not add another instrumentation layer until this producer-resource result is analyzed.

## 9. DO NOT ROLLBACK / DO NOT REPEAT

Never roll back:

- VS DEFAULT_VAL synthesize/linkage compatibility
- permanent PS DEFAULT_VAL linkage fix
- AArch64 generated-code cache/I-cache coherency fix
- known-good pre-e834 Vulkan compatibility behavior
- validated query/downstream/resource observation chain

Do not repeat:

- Bayo2 ready-zero as NOT_READY/default zero
- missing snapshot / overwritten-unconsumed explanation for this capture
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

`Cemu Windows ARM64 / Adreno 작업 계속. GitHub의 TECH_BIBLE.md, DEBUG_HISTORY.md, DEBUG_HISTORY_20260905_BAYO2_TARGET0_RESOURCE_RUNTIME.md, CURRENT_HANDOFF.md를 먼저 읽고 실제 branch/HEAD/Actions 상태와 대조해. CURRENT_HANDOFF NEXT ACTION부터 시작해. 현재 active experiment는 target0 0x46a92ec8 query-producer resource trace이며 Run #12 33939024628의 최종 상태를 먼저 확인해. Bayo2/XCX query-consumption 차이를 유지하고 이미 배제된 실험을 반복하지 마. main은 건드리지 마.`
