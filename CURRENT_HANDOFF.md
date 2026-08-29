# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-08-29 KST  
> 새 탭은 `TECH_BIBLE.md` → `DEBUG_HISTORY.md` → `DEBUG_HISTORY_20260829_QUERY_COMPARE.md` → 이 문서 → `QUERY_COMPARE_ANALYSIS_20260829.md` 순서로 읽는다.  
> 이전 대화를 추측해서 복원하지 말고 GitHub 문서를 기준 상태로 삼는다.

## 1. 현재 최우선 목표

**Bayonetta 2 JP Vulkan 원거리/배경 폴리곤 플리커링 원인 규명**

동시에 XCX의 현재 심한 object/character flicker를 control title로 사용해 occlusion/query 경로를 비교한다.

환경:
- Windows 11 ARM64
- Snapdragon X Elite / Adreno X1-85
- Vulkan 1.3
- driver `f22d572733`
- compiler `E031.50.36.00`
- driver branch `pp165`

Bayonetta 2 JP:
- title `00050000-1011B900`, v1
- 멀리 있는 배경/폴리곤이 깜빡이고 가까워지면 상대적으로 안정

XCX JP:
- title `00050000-10116100`, v48
- 현재 주인공/오브젝트 flicker가 심함
- 거리 의존성이 Bayonetta와 동일하다고 전제하지 않는다

## 2. 저장소 / 보호 기준점

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

주 문서 브랜치:
`runtime-experiments-arm64`

일반 code-changing baseline:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

보호 기준:
- clean ARM64 `windows-arm64` = `6129066e8bfa3ad89556756712c11d003e0ad31f`
- known-good Adreno compat `final-adreno-compat-arm64` = `e14b764b55bf6a5d6f561e7bf1bde8dc17d1b600`
- VS producer-side `DEFAULT_VAL` synthesize/linkage fix rollback 금지
- AArch64 generated-code cache / I-cache coherency fix rollback 금지
- known-good pre-e834 Vulkan compatibility behavior rollback 금지
- Runtime Diagnostics 77/77 구조 유지

## 3. 이미 닫힌/강하게 하향한 Bayonetta 실험 — 반복 금지

- Position Invariance
- Vulkan viewport depth-range clamp
- Vulkan `depthBiasClamp`
- Force Maximum LOD / LOD 일반 설정
- native `negativeOneToOne` / shader `(z+w)/2` removal
- RT simple/strong/pre-begin barriers
- forced render-pass split
- depthclip
- pipeline pNext
- VS auxHash pipeline key
- `f4c24000` 0x11↔0x1a actual conversion
- `f4c24000` depth↔color conversion
- nested/overlapping GX2 query resume / duplicate bookkeeping
- `f5442800` stale-main cross-pitch D24 coherence as Bayonetta flicker primary cause

### f544 final status

Confirmed correctness gap:
- same guest address `f5442800`
- D24/S8 tile4
- separate 1280/p1280, 256/p256, 64/p64 host depth images
- newer small depth writes can coexist while main is stale
- main first draw loads and reads stale prior depth with LEQUAL

But seeded correction A/B:
- branch `exp/bayo2-f544-seeded-roundtrip`
- runtime HEAD `a2e4e70ccba4052890d8e06b06d227d41e019878`
- Run `33160442364` SUCCESS
- 940 complete `seed-main → 256 overlay → 64 overlay → main-reload` cycles
- user visual result: **0 improvement**

Therefore f544 coherence remains a real Cemu correctness issue but is strongly downgraded as this Bayonetta flicker's primary cause.

Never repeat old destructive unseeded roundtrip `001df98...`.

## 4. Query-comparison observation baseline

Branch:
`diag-bayo2-xcx-query-consumption`

Runtime HEAD:
`a9e731b1761d12eff97916108b11b19100e3b43d`

Workflow:
`Cemu ARM64 Bayo2 XCX Query Consumption Trace`

Run:
`33167161105` — **SUCCESS**

Job:
`98835203694`

Behavior:
- observation only
- query result/lifetime/bookkeeping unchanged
- existing XCX `0x100000` workaround unchanged

Detailed analysis:
`QUERY_COMPARE_ANALYSIS_20260829.md`

## 5. XCX runtime result — GPU query path

First query-comparison capture:
`log(20260828-120900).txt`

Title:
`00050000-10116100`, v48 JP

Confirmed:
- `API_BEGIN/API_END` query type = **2 only** = GPU occlusion query
- sampled begin/end counters reached at least `n=75000`
- completed results include many true zero and nonzero sample sums
- sampled point: `FINISH_ZERO n=41000 total=70849 nonzero=29849`

Not observed:
- `GET_NOT_READY`
- `GET_READY_ZERO`
- `GET_READY_NONZERO`
- exported `GX2QueryBeginConditionalRender/EndConditionalRender` markers

This established that XCX does not consume these query results through exported `GX2QueryGetOcclusionResult()` in that capture.

## 6. XCX low-level predication static finding

At baseline source, `LatteCP_itSetPredication()`:
- reads `physQueryInfo` and `flags`
- decodes `queryTypeFlag` and `pixelsMustPassFlag`
- toggles only `conditionalRenderActive`
- does **not** read query memory/result
- does **not** test zero/nonzero
- does **not** invoke renderer predication/conditional rendering
- `conditionalRenderActive` is not used to gate draw execution elsewhere in this source

Also:
- GX2 producer encodes `dontWait` at bit 19
- consumer local code computes `(flags >> 1) & 19`, which does not extract bit 19
- that local value is unused, therefore this was not changed

Static interpretation before runtime trace:
- current Cemu low-level predication handler is effectively a packet/state stub, not an actual query-result consumer
- raw `IT_SET_PREDICATION` traffic still had to be observed before deciding whether XCX used that path

## 7. XCX `IT_SET_PREDICATION` runtime observation — CLOSED FOR CAPTURE

Observation branch:
`diag-xcx-predication-consumption`

Base:
`a9e731b1761d12eff97916108b11b19100e3b43d`

Runtime HEAD:
`e6fac132fff290ee3d54a58d4e8e7c03f391f25e`

Workflow:
`Cemu ARM64 XCX Predication Consumption Trace`

Run:
`33227559831` — **SUCCESS**

Behavior:
- observation only
- existing `[QUERY_COMPARE]` trace retained
- XCX `0x100000` workaround retained
- no query values, lifetime, bookkeeping, renderer visibility, return behavior changed

Input runtime log:
- uploaded `log.zip` → `log.txt`
- first line `Init Cemu e6fac13`
- XCX JP `00050000-10116100`, v48
- therefore correct observation binary usage confirmed

Runtime marker result:
- `[XCX_PREDICATION]` = **0**
- `[QUERY_COMPARE] CONDITIONAL_BEGIN` = **0**
- `[QUERY_COMPARE] CONDITIONAL_END` = **0**
- `[QUERY_COMPARE] GET_*` = **0**

At the same time query production remained extremely active:
- sampled `API_BEGIN/API_END` reached at least `n=89000`
- type = **2 only**
- latest sampled point: `FINISH_ZERO n=61000 total=85597 nonzero=24597`
- at that point ≈71.3% completed zero / 28.7% completed nonzero

Important additional observation from first 128 complete FINISH records:
- 16 contiguous query slots
- first slot `27998b80`
- exact `0x40` stride, matching `sizeof(GX2Query)==0x40`
- 13/16 slots produced both zero and nonzero results during reuse

Examples:
- `27998bc0`: zero → nonzero `2449511` → zero
- `27998f00`: zero → nonzero `2461251` → zero → nonzero
- `27998e40`: zero → `52565` → zero → later nonzero

Conclusion:
- XCX GPU query slots are actively reused and their completed results genuinely oscillate zero/nonzero.
- zero cannot be globally classified as merely uninitialized/default.
- **No raw `IT_SET_PREDICATION` packet reached `LatteCP_itSetPredication()` in this capture**, including the instrumented top-level and indirect/display-list call sites.
- Therefore the hypothesis `XCX bypasses exported API and consumes query through low-level IT_SET_PREDICATION` is **closed for this capture**.

Remaining XCX possibilities:
- direct guest-code reads of query memory/result fields
- query traffic whose consumer is elsewhere/not visibility-driving in the captured path

Do not implement predication or change the historical `0x100000` workaround based on this negative result.

## 8. Bayonetta 2 runtime result — CPU query path

Input log:
`log(20260828-121022).txt`

Title:
`00050000-1011B900`, v1 JP

Confirmed:
- `API_BEGIN/API_END` query type = **0 only** = CPU occlusion query
- sampled begin/end counters reached at least `n=32000`
- heavy `GX2QueryGetOcclusionResult()` consumption
- `GET_READY_ZERO` dominates
- sampled point: `GET_READY_ZERO n=31000 calls=31211 nonzero=211`
- finish side sampled point: `FINISH_ZERO n=32000 total=32211 nonzero=211`
- `GET_NOT_READY` not observed

Pointer-order check on sampled records:
- where the same query pointer had both FINISH and GET markers, no sampled GET occurred before its FINISH
- sampled zero path: `FINISH_ZERO → GET_READY_ZERO`
- sampled nonzero path: `FINISH_NONZERO → GET_READY_NONZERO`

Important interpretation:
- Bayo2's dominant ready-zero results are **not currently supported as simple premature/default-zero latency**.
- CPU query initialization uses `OCPU` not-ready magic; GET returns FALSE while it remains.
- no `GET_NOT_READY` was observed and sampled ready-zero values follow completed zero results.

Therefore **do not globally force Bayo2 ready-zero to visible** yet.

## 9. Bayonetta 2 frame/draw correlation build and runtime result

Observation branch:
`diag-bayo2-query-frame-draw-correlation`

Runtime HEAD:
`13c9705e99c23e30f476d3b46d21849b169b9212`

Workflow:
`Cemu ARM64 Bayo2 Query Frame Draw Correlation Trace`

Successful run:
`33230812891` — **SUCCESS**

Job:
`99043206588`

Artifact:
`cemu-arm64-bayo2-query-frame-draw-correlation`

Behavior:
- observation only
- frameSeq uses processed scanbuffer-swap boundary
- drawSeq wraps actual `DrawPassContext::executeDraw()` calls
- pointer generation increments on each BEGIN
- no query semantics, culling, visibility, or renderer behavior changed

### Runtime A — packs active

Log:
`log(20260829-070041).txt`

Final summary:
- GET 47,775
- zero 47,365 / nonzero 410
- `0->NZ` 383 / `NZ->0` 390
- repeat 0
- missingSnapshot 0
- overwrittenUnconsumed 3
- 154 unique finished/query slots
- all observed GET results matched the corresponding finished sampleSum

This run unintentionally still had Contrasty, 60 FPS Cutscenes, Force Maximum LOD, Dynamic Shadows, and Portal active.
User visual result: severe flicker.

### Runtime B — verified all packs OFF

Log:
`log(20260829-071604).txt`

Startup proves the clean baseline:
- `------- Activate graphic packs -------`
- zero following `Activate graphic pack:` entries

User visual result:
- **screen/flicker same as the immediately preceding severe run**

Final summary:
- frame 2274 / draw 1,007,535
- GET/newGenGET 61,352 / 61,352
- zero 60,992 / nonzero 360
- `0->NZ` 328
- `NZ->0` 338
- `NZ->NZ` 22
- `0->0` 60,570
- FIRST 94
- repeat 0
- missingSnapshot 0
- overwrittenUnconsumed 0
- 94 unique query pointers
- resultMatchesFinish mismatch 0
- GET_NOT_READY 0
- GET_NO_SNAPSHOT 0

Query lifetime characteristics:
- every observed BEGIN/END remained in one frame
- spanDraw median 1, p90 5, p95 7, max 18
- FINISH was one frame after END in 61,129 / 61,352 observations; same frame in 223

Cross-run conclusion:
- graphic packs OFF does not remove or visibly reduce the flicker
- aggregate zero/nonzero transition density changed from about 1.62% in runtime A to about 1.09% in clean runtime B while visual severity remained the same
- therefore global transition frequency is not a direct proxy for visual flicker severity
- however the same small set of query slots repeatedly rank as the strongest oscillators in both runs

Persistent examples:
- `46a92ec8`: 62 transitions in A, 88 in B
- `46a936c8`: 56 -> 66
- `46a93bc8`: 49 -> 41
- `46a93a08`: 34 -> 50
- `46a93708`: 38 -> 25

Across the 90 pointers common to both captures, per-pointer transition-rate correlation is about 0.786.

Interpretation:
- Bayo2 CPU query values are completed, internally consistent values; premature/default-zero is not supported
- narrow query draw spans are compatible with object/proxy visibility tests
- a global zero->visible workaround remains unjustified
- the persistent high-oscillation subset is the next useful observation boundary

## 10. Key comparison conclusion

XCX and Bayonetta 2 do **not** use the same observed query-consumption path:

XCX:
- GPU query type2
- >=89k query traffic in latest capture
- no exported CPU GET
- no exported conditional API
- no raw `IT_SET_PREDICATION` observed

Bayonetta 2:
- CPU query type0
- heavy GET consumption
- completed zero results dominate
- query pointers are heavily reused by generation
- a stable subset repeatedly oscillates zero/nonzero across independent captures

Thus:
- XCX remains useful as a control proving genuine zero/nonzero query dynamics and historical query-related flicker concerns
- current evidence does **not** justify transplanting the XCX workaround to Bayonetta 2
- the earlier Bayo2 `late result -> default zero -> hidden object` theory is strongly weakened
- the next question is not whether query values change, but which persistent query/draw relationship maps to the actual flickering geometry

## 11. NEXT ACTION

**No behavior-changing A/B yet. No global force-visible patch.**

Next proposed experiment is one observation-only **targeted query-to-draw fingerprint trace** for Bayonetta 2:

1. Keep the current clean graphics-pack-OFF baseline.
2. Focus on the persistent high-oscillation CPU query slots instead of logging all query traffic equally.
3. When one of those query generations changes zero/nonzero state, fingerprint its narrow associated draw range and enough of the following frame draw stream to detect draw clusters that appear/disappear with that query result.
4. Include shader/pipeline identity plus relevant render-target/depth state in the fingerprint so the same geometry/pass can be recognized across frames.
5. Do not modify query values, readiness, culling, visibility, render state, or XCX workaround.
6. Use the resulting correlation to select exactly one concrete query/draw relationship before any behavior-changing A/B.

Do not repeat:
- nested/duplicate occlusion bookkeeping experiment
- f544 seeded/unseeded coherence experiments
- XCX `IT_SET_PREDICATION` observation
- Bayo2 global ready-zero force-visible
- Force Maximum LOD / LOD experiment

**Implementation/new workflow/CI requires a fresh user `ㄱㄱ`.**

## 12. New-tab start prompt

Use exactly this context:

> Cemu Windows ARM64 / Adreno 구동분석·디버그 작업을 이어간다. GitHub 저장소 `npark2860-cyber/Cemu-Windows-ARM64`의 `TECH_BIBLE.md`, `DEBUG_HISTORY.md`, `DEBUG_HISTORY_20260829_QUERY_COMPARE.md`, `CURRENT_HANDOFF.md`, `QUERY_COMPARE_ANALYSIS_20260829.md`를 먼저 읽고, `CURRENT_HANDOFF.md`의 저장소/브랜치/HEAD와 현재 GitHub 상태를 확인해라. 이전 대화를 추측해서 복원하지 말고 이 문서들을 기준 상태로 삼아라. Bayonetta 2 CPU query frame/draw correlation에서 clean graphic-pack-OFF 상태에서도 severe flicker가 동일했고, completed query results는 internally consistent하며 aggregate zero/nonzero transition rate가 visual severity를 직접 설명하지 못한다는 최신 결론을 유지해라. 동일한 소수 query slots가 두 capture에서 반복적으로 높은 oscillation을 보였다는 결과를 기준으로 `CURRENT_HANDOFF.md`의 NEXT ACTION부터 계속해라. XCX workaround를 Bayonetta에 이식하거나 ready-zero를 premature로 단정하지 마라. 코드 수정/새 workflow/CI는 내가 새로 `ㄱㄱ`하기 전에는 시작하지 마라.
