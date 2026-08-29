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
- query traffic whose consumer is elsewhere/not visibility-driving in this captured path

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

## 9. Key comparison conclusion

XCX and Bayonetta 2 do **not** use the same observed query-consumption path:

XCX:
- GPU query type2
- >=89k query traffic in latest capture
- no exported CPU GET
- no exported conditional API
- no raw `IT_SET_PREDICATION` observed

Bayonetta 2:
- CPU query type0
- >=32k query traffic
- heavy GET consumption
- completed zero results dominate sampled reads

Thus:
- XCX remains useful as a control proving genuine zero/nonzero visibility-query dynamics and historical query-related flicker concerns.
- current evidence does **not** justify transplanting the XCX workaround to Bayonetta 2.
- the earlier provisional Bayo2 `late result -> default zero -> hidden object` theory remains strongly weakened.

## 10. Current live questions

### XCX
Where are GPU query results actually consumed, if at all, in the captured path?

Remaining plausible boundary:
- direct guest-memory access to GX2Query result fields

Do not immediately instrument the entire JIT memory-read path; that would be high-overhead and broad. XCX predication tracing is complete and should not be repeated.

### Bayonetta 2
What do the many completed-zero CPU queries represent?

Need to determine whether they correspond to:
- distant geometry visibility/culling
- unrelated effects or passes
- stable legitimate occlusion decisions
- zero/nonzero oscillation for the same query/object slot around visible flicker

## 11. NEXT ACTION

**No behavior-changing A/B yet. No global force-visible patch.**

Next high-value experiment is Bayonetta 2 observation-only CPU-query correlation:

1. Create an actual command-stream frame sequence using the processed scanbuffer-swap boundary; do **not** use `LatteGPUState.flipCounter` as a generic Bayo frame counter.
2. Create a monotonic draw sequence around `DrawPassContext::executeDraw()`.
3. Track each query pointer with a reuse generation; pointer alone must not be treated as one permanent query lifetime.
4. On GPU-side BEGIN/END/FINISH record pointer + generation + event range + begin/end frameSeq + begin/end drawSeq + `sampleSum`.
5. On CPU GET record pointer + generation + result and classify completed transitions: `0→0`, `0→nonzero`, `nonzero→0`, `nonzero→nonzero`.
6. Keep logging sampled/summary-oriented; do not dump every draw.
7. Use this to determine whether stable query slots oscillate zero/nonzero across adjacent visible frames and whether their lifetimes span narrow draw ranges consistent with object visibility.
8. Only after a concrete wrong visibility correlation should one behavior A/B be proposed.

Do not repeat:
- nested/duplicate occlusion bookkeeping experiment
- f544 seeded/unseeded coherence experiments
- XCX `IT_SET_PREDICATION` observation
- Bayo2 global ready-zero force-visible

**Implementation/new workflow/CI requires a fresh user `ㄱㄱ`.**

## 12. New-tab start prompt

Use exactly this context:

> Cemu Windows ARM64 / Adreno 구동분석·디버그 작업을 이어간다. GitHub 저장소 `npark2860-cyber/Cemu-Windows-ARM64`의 `TECH_BIBLE.md`, `DEBUG_HISTORY.md`, `DEBUG_HISTORY_20260829_QUERY_COMPARE.md`, `CURRENT_HANDOFF.md`, `QUERY_COMPARE_ANALYSIS_20260829.md`를 먼저 읽고, `CURRENT_HANDOFF.md`의 저장소/브랜치/HEAD와 현재 GitHub 상태를 확인해라. 이전 대화를 추측해서 복원하지 말고 이 문서들을 기준 상태로 삼아라. XCX raw `IT_SET_PREDICATION` observation 결과가 0건으로 끝났다는 최신 결론을 유지하고, 이미 배제된 실험을 반복하지 마라. Bayonetta 2 ready-zero를 premature-zero로 단정하거나 XCX workaround를 그대로 이식하지 마라. `CURRENT_HANDOFF.md`의 NEXT ACTION부터 즉시 계속해라. 코드 수정/새 workflow/CI는 내가 새로 `ㄱㄱ`하기 전에는 시작하지 마라.
