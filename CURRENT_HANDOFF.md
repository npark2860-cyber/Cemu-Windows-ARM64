# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-08-28 KST  
> 목적: 새 탭이 이 문서만 읽고 이미 끝난 실험을 반복하지 않고 즉시 현재 작업을 이어가게 한다.  
> 장기 확정 사실은 `TECH_BIBLE.md`, 세부 실험 이력은 `DEBUG_HISTORY.md`를 본다.

## 1. 현재 최우선 목표

**Bayonetta 2 (JP) Vulkan 원거리/배경 폴리곤 플리커링 원인 규명**

증상:
- 멀리 있는 폴리곤/오브젝트가 거리에서 깜빡이거나 나타났다 사라진다.
- 가까워지면 상대적으로 안정된다.
- 현재 주 타겟은 crash가 아니다.

테스트 환경:
- Windows 11 ARM64
- Snapdragon X Elite / Qualcomm Adreno X1-85
- Vulkan 1.3
- Bayonetta 2 JP `00050000-1011B900`, v1
- driver build `f22d572733`
- compiler `E031.50.36.00`
- driver branch `pp165`

upstream `cemu-project/Cemu` Issue #1348에는 RTX 3060 Ti에서도 Bayonetta 2 Chapter VIII flicker가 graphic-pack 설정과 무관하게 발생하고 2026년에도 unresolved라는 기록이 있다. 현재 사용자 장면과 동일 근본원인이라고 확정하지는 않지만 **ARM64/Adreno 전용 버그라고 전제하지 않는다.**

## 2. 저장소 / 보호 기준점

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

주 문서/진단 브랜치:
`runtime-experiments-arm64`

일반 진단/호환성 code-changing baseline:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

Commit:
`diagnostics: require complete 77-item coverage`

문서-only `[skip ci]` commit은 이 뒤에 붙을 수 있으므로 branch HEAD와 code baseline을 구분한다.

### 절대 되돌리지 말 것

- VS producer-side `DEFAULT_VAL` synthesize / linkage compatibility fix
- AArch64 generated-code cache / I-cache coherency fix
- known-good pre-e834 Vulkan compatibility behavior
- 77/77 Runtime Diagnostics 구조

## 3. 이미 끝난 Bayonetta 2 실험 — 반복 금지

확정 negative / 크게 하향:
- Position Invariance (`invariant gl_Position`): **개선 0**
- Vulkan viewport depth-range clamp: **개선 0**
- Vulkan `depthBiasClamp=0`: **개선 0**
- Force Maximum LOD / LOD 일반 설정: 유의미한 개선 없음
- native Vulkan `negativeOneToOne` / shader-side `(z+w)/2` 제거: **개선 0**
- RT simple barrier
- strong barrier
- pre-begin barrier
- forced render-pass split
- depthclip
- pipeline pNext
- VS auxHash pipeline key
- `f4c24000` `0x11↔0x1a` actual alias conversion
- `f4c24000` depth↔color format-conversion

새 직접 증거 없이 반복하지 않는다.

## 4. Bayonetta 2 alias-sync trace — 완료

Branch: `diag-bayo2-alias-sync`  
Base: `fa17d834bfebd9a41c598b1b1b702000d0ff4618`  
Workflow HEAD: `fd5f6376959d739cb50e5dfd79ef64716a40cb60`  
Run: `33119155975` — **SUCCESS**  
User log: `log(20260828-002909).txt`

결과:
- `[BAYO2_ALIAS_REL]` = 10
- `[BAYO2_ALIAS_COPY]` = 1024
- actual copy 1024/1024 모두 `0x1a` non-depth `640x368 → 640x360`, `path=image-copy`
- `0x11→0x1a` = 0
- `0x1a→0x11` = 0
- depth→color = 0
- color→depth = 0
- `format-conversion` = 0

따라서 `f4c24000` multi-representation relation은 실제지만, 의심했던 R24/D24↔RGBA8 또는 depth/color conversion handoff는 캡처된 flicker 세션에서 실행되지 않았다.

주 gameplay depth attachment는 별도로 반복 관찰됨:
- address `f5442800`
- hardware format `0x11`
- stencil=1
- Vulkan depth format `129` = `VK_FORMAT_D24_UNORM_S8_UINT`

## 5. Native `negativeOneToOne` A/B — 완료, negative

Branch:
`exp/vk-native-negative-one-to-one`

Base:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

Patch script commit:
`601eac82108db1626254c025aaff1efc83a0ccc5`

Workflow HEAD:
`66ab7c76af02f7bff76747ea6dcbb6f28b6a6c13`

Workflow:
`Cemu ARM64 Bayonetta2 Native Depth Clip Control`

Run:
- ID `33131685028`
- **SUCCESS**

User runtime log:
`log(20260828-014616).txt`

Runtime validity:
- `[BAYO2_NATIVE_DEPTH_CLIP] VK_EXT_depth_clip_control: supported`
- `[BAYO2_NATIVE_DEPTH_CLIP] negativeOneToOne=1 shaderZRemap=0`
- 같은 VS hash를 이전 build와 비교하면 GLSL source가 일관되게 55 bytes 짧아져 실제 `(z+w)/2` Z-remap 코드 제거도 확인됨.
- 새로운 SPIR-V/device-lost 회귀 없음.

User visual result:
- **플리커링 그대로 / 개선 0**

결론:
- extension 미지원 fallback이 아니라 실제 native negative-one-to-one path가 활성화된 유효 A/B였다.
- shader-side `(z+w)/2` FP remap 자체는 현재 distant flicker의 주원인 후보에서 **강하게 하향**한다.
- 동일 실험 반복 금지.

## 6. 정상 depth-state 정적 확인

`VulkanPipelineCompiler::InitDepthStencilState()`와 OpenGL depth state를 비교했다.

양쪽 모두 동일하게 Wii U `DB_DEPTH_CONTROL`에서:
- `Z_ENABLE`
- `Z_WRITE_ENABLE`
- `Z_FUNC`

를 읽고, compare function도 다음 동일 의미 순서로 매핑한다:
- NEVER
- LESS
- EQUAL
- LEQUAL
- GREATER
- NOTEQUAL
- GEQUAL
- ALWAYS

따라서 단순 `Z_ENABLE/Z_WRITE/Z_FUNC` API 매핑 차이는 현재 소스에서 보이지 않는다.

다만 현재 77/77 pipeline-state snapshot은 **pipeline failure에서만** depthTest/depthWrite/depthCompare를 상세 출력한다. 정상 gameplay draw의 성공 pipeline에는 이 상태가 기록되지 않으므로 runtime correlation은 아직 없다.

## 7. 새 강한 관찰 후보 — 중첩 occlusion-query bookkeeping

증상 형태가 거리/가시성에 따라 오브젝트가 나타났다 사라지는 것이므로 occlusion/visibility query를 별도 축으로 검토했다.

`src/Cafe/HW/Latte/Core/LatteQuery.cpp`에서 구조적 이상을 확인했다.

`LatteQuery_EndOcclusionQuery()`는 한 GX2 query가 끝난 뒤 다른 GX2 query가 아직 active이면:
1. 새 renderer query를 생성한다.
2. `LatteQuery_begin(queryObject, currentEventId)`로 **active** 상태로 만든다.
3. 그 직후 `list_queriesInFlight.emplace_back(queryObject)`에 넣는다.
4. 동시에 `_currentlyActiveRendererQuery = queryObject`로 유지한다.

그러나 `list_queriesInFlight`는 `LatteQuery_UpdateFinishedQueries()`가 `queryEnded`인 객체를 결과 수집/파괴하는 대기열로 사용한다. active 객체는 `queryEnded==false`라 skip된다.

이 동일 객체가 나중에 실제 종료되면 `LatteQuery_endActiveRendererQuery()`가 다시 `list_queriesInFlight.emplace_back(_currentlyActiveRendererQuery)`를 수행하므로 **동일 pointer가 완료 대기열에 중복 삽입될 수 있는 코드 흐름**이다.

가능한 결과:
- 같은 query result의 이중 처리/누적
- 동일 query object의 중복 cache 반환
- debug build에서는 동일 `queryEventEnd` 재처리 시 ordering assert 가능성

중요:
- 이것은 **코드 구조상 실제 anomaly 후보**다.
- 그러나 Bayonetta 2가 문제 장면에서 `hasActiveGX2Query == true`인 nested/overlap query 경로를 실제 사용하는지는 아직 증명되지 않았다.
- 최신 upstream `cemu-project/Cemu`에도 동일 로직이 그대로 존재한다. 따라서 non-Adreno 공통 flicker 가능성과 모순되지 않는다.
- 아직 이 줄을 삭제하거나 동작을 고치지 않는다. 먼저 observation-only trace로 runtime hit 여부를 확인한다.

## 8. 현재 후보 우선순위

1. **nested/overlapping GX2 occlusion-query 경로의 실제 사용 여부**
   - 먼저 observation-only trace
   - hit가 없으면 즉시 하향
2. **정상 gameplay draw의 depth test/write/compare + D24 attachment correlation**
3. **upstream #1348과 현재 사용자 장면의 공통 render path 식별**
4. `f4c24000` same-format `0x1a 640x368→640x360` sync
   - direct correlation이 생길 때만 재상승

크게 하향 / 반복 금지:
- clip-space shader Z remap / native negativeOneToOne
- Position Invariance
- viewport clamp
- depthBiasClamp
- LOD
- barrier/split/depthclip/pNext/auxHash
- `f4c24000` format/depth-class conversion

## 9. Tekken 1P→2P — 별도 트랙

확인:
- physical controller → Cemu player0 → VPAD channel0
- VPAD connected=1, player=0
- KPAD 0–3 disconnected
- 게임에서는 2P side로 동작
- 테스트한 x64 Cemu에서도 동일

ARM64 InputManager player-index misassignment는 강하게 하향. Bayonetta graphics 분석과 섞지 않는다.

## 10. 작업 원칙

- source/static verification → 최소 observation/A-B → 필요한 경우에만 CI 1회
- 이미 끝난 실험 반복 금지
- 한 build에 다른 가설 혼합 금지
- 화면 관찰과 로그 fact 분리
- generic upstream bug 가능성이 있으면 Adreno-specific hack보다 공통 원인을 우선
- VS `DEFAULT_VAL` synthesize rollback 금지
- **occlusion anomaly는 runtime hit를 확인하기 전 behavior fix 금지**

# NEXT ACTION

1. `LatteQuery.cpp`에 **observation-only** Bayonetta 2 occlusion trace 설계를 적용한다.
2. 기록할 것:
   - GX2 query BEGIN / END count와 queryMPTR
   - active GX2 query count
   - END 후 `hasActiveGX2Query`가 true인 resume/nested 횟수
   - 새 active renderer query가 `list_queriesInFlight`에 들어가는 횟수
   - `list_queriesInFlight` 내부 `queryEnded==false` 객체 존재 횟수
   - 동일 query pointer duplicate 존재 여부
3. 동작은 절대 바꾸지 않는다. 문제로 보이는 `list_queriesInFlight.emplace_back(queryObject)`도 아직 제거하지 않는다.
4. 정적 anchor/diff 검증 후에만 dedicated diagnostic build를 고려한다.
5. Bayonetta에서 nested/resume path가 **0회**면 occlusion 후보를 즉시 하향하고 정상 gameplay draw depth-state correlation으로 이동한다.
6. nested/resume + duplicate/inflight anomaly가 실제 발생하면 그때 **단일-line bookkeeping fix A/B**를 설계한다.
7. 새 직접 증거 없이 기존 LOD/barrier/clip-space/alias 실험을 반복하지 않는다.

## New-tab startup prompt

`Cemu ARM64 Bayonetta 2 flicker 분석을 이어간다. GitHub의 CURRENT_HANDOFF.md, TECH_BIBLE.md, DEBUG_HISTORY.md를 먼저 읽고 runtime-experiments-arm64 문서 HEAD와 code-changing baseline fa17d83을 구분해라. 이미 끝난 Position Invariance, viewport clamp, depthBiasClamp, Force Maximum LOD/LOD, RT barrier variants, forced split, depthclip, pipeline pNext, VS auxHash, f4c24000 0x11/0x1a conversion, native negativeOneToOne 실험을 반복하지 마. native negativeOneToOne Run 33131685028은 실제 extension support 및 activation이 확인됐지만 사용자 화면 결과는 개선 0이었다. 현재 가장 먼저 확인할 것은 LatteQuery_EndOcclusionQuery의 nested GX2 query resume 경로가 Bayonetta 문제 장면에서 실제 발생하는지 observation-only trace로 확인하는 것이다. CURRENT_HANDOFF의 NEXT ACTION부터 계속해.`