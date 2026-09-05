# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-09-06 KST  
> GitHub 문서/branch/Actions를 source of truth로 사용한다. 이전 대화를 추측해서 복원하지 않는다.

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
10. `DEBUG_HISTORY_20260906_BAYO2_TARGET0_DEPTHCOMPARE_RUNTIME.md`
11. `DEBUG_HISTORY_20260905_STARFOX_BAYO2_F57C8000_COMMON_DEPTH_PATH.md`
12. `CURRENT_HANDOFF.md`

## 1. Repository state

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Main remains untouched. Known main HEAD: `58954b34d147b134d7b23ee61b2057f49da2c014`.

Docs branch: `diag-bayo2-target0-resource-identity`

CI branch: `diag-bayo2-target-query-draw-fingerprint`

Current CI HEAD: `0e78994bfa41614f2631ca84e34dff2a7979c645`

Current staging branch: `diag-starfox-query-consumption`

Staging diff from Run #17 is intentionally narrow:

- add `tools/diagnostics/Apply-StarFoxQueryConsumptionTrace.py`
- add four chaining lines to `Apply-Bayo2Target0DepthCompareTextureHistoryTrace.py`

No query/result/readiness/render/texture/draw behavior change.

## 2. Fixed query-consumption facts

Bayonetta 2 JP `00050000-1011B900`:

- CPU occlusion query type=0
- exported `GX2QueryGetOcclusionResult()` heavily consumed
- completed ready-zero is real completed/consumed result
- no GET_NOT_READY / missing snapshot / overwritten-unconsumed explanation
- do not globally force ready-zero visible

XCX JP `00050000-10116100`:

- GPU occlusion query type=2
- exported CPU `GX2QueryGetOcclusionResult()` consumption not observed
- no exported conditional-render marker
- dedicated raw capture had no `IT_SET_PREDICATION`
- historical XCX `0x100000` seed remains XCX-only

Do not assume Bayo2/XCX/Star Fox use the same query path until measured.

## 3. Closed Bayo2 target0 producer discriminators

Target0 `0x46a92ec8` completed ZERO/NONZERO is not explained by:

- six-draw sequence
- pipeline/shader/draw arguments and recorded render state
- guest VB identity/content
- VS/PS/GS CB identity/content
- PS full uniform state
- transition-specific VS uniform vec4 delta family
- actual target depth identity `0xf5442800`
- target depth write/update bookkeeping
- exact six-draw index-buffer content
- sampled texture unit selection
- seven-word texture resource identity
- image/mip guest addresses
- sampler assignment / depth-compare flags
- readable 4 KiB texture prefixes
- PS unit11 `0xf57c8000` bound-object write/update/access history

Do not repeat these experiments under the same conditions.

## 4. Run #17 — Bayo2 depth-compare history — CLOSED

Run #17:

- Run ID `33971629934`
- head `ce80d7a68dc88b90f299f9e2dfd53b8e267c92d9`
- conclusion SUCCESS
- artifact id `9971602143`
- digest `sha256:8c5745809a761ac27da869bc658d80c82803077475616dac05ce73dfa28d614a`

Runtime `log (2)(3).zip`:

- completed target0 generations: 666
- ZERO 610 / NONZERO 56
- `[BAYO2_TARGET_DEPTHCOMPARE]`: 667 rows, 666/666 completed gens covered
- `0->0` 556 / `0->NZ` 53 / `NZ->0` 53 / `NZ->NZ` 3

All completed generations have identical `f57c8000` identity and fixed bookkeeping fields. `dataUpdateFrame` and `accessFrame` equal producer frame for 666/666. `writeEvent` deltas overlap strongly after controlling frame gap. Nonzero `unflushedDraw` anomalies occur in both result classes.

Conclusion: **observed `f57c8000` history is not the ZERO/NONZERO discriminator.**

Detailed source: `DEBUG_HISTORY_20260906_BAYO2_TARGET0_DEPTHCOMPARE_RUNTIME.md`.

## 5. Star Fox Zero independent reproduction

Star Fox Zero JP v16 title ID: `00050000-101aff00`.

User reports the visible symptom is the same as Bayo2: severe object flicker/disappear-reappear behavior.

Runtime logs independently show a structurally matching path:

Bayo2:

- `f57c8000`
- `1024x2048`, pitch 1024
- format `0x11`, depth, GPU-updated
- producer PS unit11 depth-compare sampling
- also used as depth attachment

Star Fox:

- `f57c8000`
- `768x1536`, pitch 768
- format `0x11`, depth, GPU-updated
- PS stage/unit11 repeated reuse
- also used as depth attachment

This is strong cross-title evidence for a common Platinum-style depth/visibility path, but **query-consumption equivalence is not yet proven**.

## 6. Active experiment — Star Fox query-consumption comparison

Use the existing observation-only `[QUERY_COMPARE]` instrumentation and add only Star Fox Zero JP to the title gates.

Markers to compare:

- `API_BEGIN` / `API_END` and query type
- `FINISH_ZERO` / `FINISH_NONZERO`
- `GET_READY_ZERO`
- `GET_READY_NONZERO`
- `GET_NOT_READY`
- `CONDITIONAL_BEGIN` / `CONDITIONAL_END`

No behavior change.

Staging commits after Run #17:

- `c6eaa131c25e6ca2466b3b32d55b24b2a83c41eb` — add Star Fox query-consumption title-gate extension
- `0e78994bfa41614f2631ca84e34dff2a7979c645` — chain extension into existing diagnostic build

Diff from Run #17: 2 files only, +51 lines total.

## 7. Current CI — Run #18

Workflow: `Cemu ARM64 Bayo2 Target Query Draw Fingerprint Trace`

Run #18

Run ID: `33977750768`

Head: `0e78994bfa41614f2631ca84e34dff2a7979c645`

Last checked status: **QUEUED**.

Do not start another CI run while #18 is active.

## 8. NEXT ACTION

1. Check Run #18 `33977750768` final status.
2. If failure, recover exact first failing diagnostic and fix only the Star Fox gate/chain layer.
3. If success, verify Build + Collect + Upload and artifact metadata.
4. Use that artifact for Star Fox Zero JP v16 in the known flicker scene for ~10–15 seconds.
5. Upload full `log.txt`.
6. Parse `[QUERY_COMPARE]` and classify Star Fox against Bayo2/XCX:
   - query type
   - CPU GET consumption yes/no
   - ready zero/nonzero distribution
   - not-ready behavior
   - conditional render use
   - renderer FINISH behavior
7. If Star Fox matches Bayo2 type=0 + CPU GET + ready-zero/nonzero oscillation, promote a shared Platinum visibility/depth path × Vulkan/Adreno hypothesis.
8. If Star Fox does not use the same query path, do not force the query explanation; instead compare the common GPU-written depth -> PS unit11 reuse / synchronization path.
9. Do not introduce a broad workaround before this cross-title classification.

## 9. DO NOT ROLLBACK / DO NOT REPEAT

Never roll back:

- VS DEFAULT_VAL synthesize/linkage compatibility
- permanent PS DEFAULT_VAL linkage fix
- AArch64 generated-code cache/I-cache coherency fix
- known-good pre-e834 Vulkan behavior
- validated observation chain

Do not repeat closed experiments listed in section 3 or old XCX/Bayo2 query assumptions.

## New-tab startup prompt

`Cemu Windows ARM64 / Adreno 작업 계속. GitHub의 TECH_BIBLE.md, DEBUG_HISTORY.md, DEBUG_HISTORY_20260829_QUERY_COMPARE.md, DEBUG_HISTORY_20260906_BAYO2_TARGET0_DEPTHCOMPARE_RUNTIME.md, DEBUG_HISTORY_20260905_STARFOX_BAYO2_F57C8000_COMMON_DEPTH_PATH.md, CURRENT_HANDOFF.md를 먼저 읽고 실제 branch/HEAD/Actions 상태와 대조해. CURRENT_HANDOFF NEXT ACTION부터 시작해. 현재 active experiment는 Star Fox Zero JP query-consumption comparison이며 Run #18 33977750768의 최종 상태를 먼저 확인해. Bayo2/XCX query-consumption 차이를 유지하고 이미 배제된 실험을 반복하지 마. main은 건드리지 마.`
