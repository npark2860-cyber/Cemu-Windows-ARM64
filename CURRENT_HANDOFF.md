# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-08-29 KST  
> 새 탭은 `TECH_BIBLE.md` → `DEBUG_HISTORY.md` → 이 문서 → `QUERY_COMPARE_ANALYSIS_20260829.md` 순서로 읽는다.  
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

## 4. Latest query-comparison observation build

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

Input log:
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

Interpretation:
- XCX definitely emits huge GPU query traffic.
- It does **not** consume these results through exported `GX2QueryGetOcclusionResult()` in this capture.
- exported conditional-render API was also not observed.
- query results may still be consumed through low-level PM4/display-list `IT_SET_PREDICATION` or direct guest-memory access; this boundary is uninstrumented.

Historical XCX source workaround:
- GPU query begin preloads endValue `0x100000`
- comment says default-zero query latency can hide objects and cause flicker
- current log proves many queries also legitimately complete with `sampleSum=0`, so that workaround does not cover all zero outcomes.

Do not add the same workaround again; it already exists.

## 6. Bayonetta 2 runtime result — CPU query path

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

Therefore **do not globally force Bayo2 ready-zero to visible** yet. That would alter many apparently completed legitimate zero occlusion results.

## 7. Key comparison conclusion

XCX and Bayonetta 2 do **not** use the same observed query-consumption path:

XCX:
- GPU query type2
- >=75k query traffic
- no exported CPU GET observed
- no exported conditional API observed

Bayonetta 2:
- CPU query type0
- >=32k query traffic
- heavy GET consumption
- completed zero results dominate sampled reads

Thus:
- XCX is a useful control proving Cemu has historical query-related flicker mechanisms.
- current evidence does **not** justify transplanting the XCX workaround to Bayonetta 2.
- the earlier provisional Bayo2 `late result -> default zero -> hidden object` theory is strongly weakened by the captured CPU-query ordering.

## 8. Current live questions

### XCX
Where are GPU query results actually consumed?

High-value missing boundary:
- `LatteCP_itSetPredication()` / raw `IT_SET_PREDICATION`
- query address and flags at predication time
- whether XCX low-level display lists bypass exported conditional-render API
- whether zero/nonzero completed results correlate with the visible character/object flicker

### Bayonetta 2
What do the many completed-zero CPU queries represent?

Need to determine whether they correspond to:
- distant geometry visibility/culling
- unrelated effects or passes
- stable legitimate occlusion decisions
- zero/nonzero oscillation for the same query/object slot around visible flicker

## 9. NEXT ACTION

**No behavior-changing A/B yet. No new global force-visible patch.**

Next tab should begin by reading the two logs through `QUERY_COMPARE_ANALYSIS_20260829.md`, then perform observation-first narrowing:

1. Static-read `GX2_Query.cpp`, `LatteQuery.cpp`, `LatteCP_itSetPredication()` and preserve the distinction between API-level and PM4-level consumption.
2. For XCX, design the smallest observation-only `IT_SET_PREDICATION` trace. Log query address, flags, queryTypeFlag, pixelsMustPass, dontWait and current query memory/result if safe.
3. For Bayonetta 2, design observation that correlates CPU query pointer/result transitions with frame/draw timing. Do not repeat nested/duplicate bookkeeping trace.
4. Only if one title shows a concrete wrong visibility decision should a single behavior A/B be proposed.
5. Implementation/new workflow/CI requires a fresh user `ㄱㄱ` in the new tab.

## 10. New-tab start prompt

Use exactly this context:

> Cemu Windows ARM64 / Adreno 구동분석·디버그 작업을 이어간다. GitHub 저장소 `npark2860-cyber/Cemu-Windows-ARM64`의 `TECH_BIBLE.md`, `DEBUG_HISTORY.md`, `CURRENT_HANDOFF.md`, `QUERY_COMPARE_ANALYSIS_20260829.md`를 먼저 읽고, `CURRENT_HANDOFF.md`의 저장소/브랜치/HEAD와 현재 GitHub 상태를 확인해라. 이전 대화를 추측해서 복원하지 말고 이 문서들을 기준 상태로 삼아라. Bayonetta 2와 XCX의 query-consumption 로그 비교 결과를 그대로 유지하고, 이미 배제된 실험을 반복하지 마라. 특히 Bayo2 ready-zero를 premature-zero로 단정하거나 XCX workaround를 그대로 이식하지 마라. `CURRENT_HANDOFF.md`의 NEXT ACTION부터 즉시 계속해라. 코드 수정/새 workflow/CI는 내가 새로 `ㄱㄱ`하기 전에는 시작하지 마라.
