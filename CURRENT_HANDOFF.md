# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-08-28 KST  
> 목적: 새 탭이 이 문서만 읽고 이미 끝난 실험을 반복하지 않고 즉시 현재 작업을 이어가게 한다.  
> 장기 확정 사실은 `TECH_BIBLE.md`, 세부 실험 이력은 `DEBUG_HISTORY.md`를 본다.

## 1. 현재 최우선 목표

**Bayonetta 2 (JP) Vulkan 원거리 폴리곤 플리커링 원인 규명**

증상:
- 멀리 있는 폴리곤/오브젝트가 거리에서 깜빡인다.
- 가까워지면 상대적으로 안정된다.
- 현재 Bayonetta 2의 주 타겟은 crash가 아니다.

테스트 환경:
- Windows 11 ARM64
- Snapdragon X Elite / Qualcomm Adreno X1-85
- Vulkan 1.3
- Bayonetta 2 JP `00050000-1011B900`, v1
- driver build `f22d572733`
- compiler `E031.50.36.00`
- driver branch `pp165`

## 2. 저장소 / 보호 기준점

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

주 작업 브랜치:
`runtime-experiments-arm64`

현재 일반 진단/호환성 code-changing baseline:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

Commit:
`diagnostics: require complete 77-item coverage`

문서-only `[skip ci]` commit은 이 뒤에 붙을 수 있으므로 branch HEAD와 code baseline을 구분한다.

### 절대 되돌리지 말 것

- VS producer-side `DEFAULT_VAL` synthesize / linkage compatibility fix
- AArch64 generated-code cache / I-cache coherency fix
- known-good pre-e834 Vulkan compatibility behavior
- 77/77 Runtime Diagnostics 구조

## 3. Runtime Diagnostics 상태

`fa17d83` 기준 **77/77 exact coverage**.

- `RuntimeDiagnostics::Enabled(flag)` = master + implemented + per-flag enabled
- UI selectable 여부 = `RuntimeDiagnostics::IsImplemented(flag)`
- verifier가 UI `kDiagItems[]`와 implemented set의 정확한 일치를 검사

새 Diagnostics Edition을 이유 없이 다시 만들지 않는다.

## 4. Bayonetta 2 — 이미 끝난 실험 / 반복 금지

### 확정 negative A/B

#### Position Invariance

- captured VS 113개 중 내부 all-zero shader 1개 제외
- 112개 replacement VS에 `invariant gl_Position;` 적용
- shader compile/SPIR-V 변화로 적용 확인
- 사용자 화면 결과: **플리커링 전혀 개선되지 않음**

결론: 주원인에서 크게 하향. 동일 조건 반복 금지.

#### Vulkan viewport depth range clamp

runtime에서 대량:
- `rawNear=-1`
- `rawFar=1`
- `halfZ=0`

Bayonetta 2 전용으로 Vulkan viewport depth를 `0..1`로 clamp했고 실제 대량 적용을 확인했다.

사용자 화면 결과: **플리커링 그대로**

결론: 단순 `VkViewport.minDepth/maxDepth` 처리 가설은 배제. 후속 build에 섞지 않는다.

#### Vulkan depthBiasClamp

전용 브랜치:
`exp/bayo2-depth-bias-clamp`

Successful HEAD:
`bdb644d89d8963ab7a39d8a586f6d73ac3d73f92`

Successful Run:
- #4
- ID `33056046387`

실험:
- Bayonetta 2에서만 Vulkan `depthBiasClamp=0.0f`
- offset/slope는 변경하지 않음

`log(20260827-093536).txt`의 첫 128개 `[BAYO2_DEPTH_BIAS]` 모두:
- `offset=0`
- `slope=-0`
- `rawClamp=0`
- `appliedClamp=0`
- `nonZeroClampCount=0`

사용자 화면 결과: **플리커링 전혀 개선되지 않음**

결론: depthBiasClamp 단독 가설 크게 하향. 동일 A/B 반복 금지.

### 이전 작업 기록에서 이미 배제/약화된 후보

다음은 이전 분석에서 이미 테스트되어 **배제 또는 약화**된 항목이다. 새 증거 없이 반복하지 않는다.

- `Force Maximum LOD` / LOD 일반 설정
- RT 단순 barrier
- strong barrier
- pre-begin barrier
- forced render-pass split
- depthclip
- pipeline pNext
- VS auxHash pipeline key

특히 **Force Maximum LOD OFF 테스트를 다시 요청하지 않는다.**

## 5. 현재 로그에서 새로 확인된 유효 신호

대표 최신 로그:
`log(20260827-093536).txt`

### A. 실제 depth attachment

Bayonetta 2 구간에서 반복적으로:
- depth attachment address `f5442800`
- GX2/Latte format `0x11`
- stencil enabled

이 확인된다.

소스 기준:
- hardware format `0x11` = `HWFMT_8_24`
- GX2 depth format `D24_S8_UNORM`은 이 hardware format family를 사용
- 현재 Vulkan pipeline 로그의 depth format 값 `129`는 `VK_FORMAT_D24_UNORM_S8_UINT`

따라서 현재 관찰 구간에서는 **D24S8가 D32S8 fallback으로 잘못 바뀌는 증거는 없다.**

이 사실은 "잘못된 depth format fallback" 후보를 약화하지만, depth precision/state 자체를 배제하지는 않는다.

### B. `f4c24000` surface reinterpretation / swizzle

현재 로그에서 `f4c24000`에 대해 실제로:

`[SUSPICIOUS_TEXTURE] reason=swizzle addr=f4c24000 current=000d0000 requested=00000000 lastRT=00000000 tile=4`

가 반복된다.

세션 texture lifecycle에는 같은 physical address `f4c24000`가 여러 representation으로 존재한다.
확인된 hardware format family:
- `0x11` = 8/24 계열
- `0x1a` = 8/8/8/8 계열

이것만으로 버그라고 단정하지 않는다. Cemu texture cache는 동일/겹치는 guest memory를 renderer view 또는 별도 compatible texture representation으로 취급할 수 있다.

하지만 현재 증상과 직접 연결할 가치가 있는 **실제 runtime 신호**다.

### C. swizzle mismatch 처리 소스

`LatteTextureLegacy.cpp`에서 texture bind 시:

- macro-tiled texture의 swizzle을 guest physical address bits에서 계산
- cached `baseTexture->swizzle`과 requested swizzle이 다르면 비교
- requested swizzle이 `lastRenderTargetSwizzle`과 같으면 reload 없이 base swizzle 갱신
- 그렇지 않으면 `swizzleChanged=true`로 두고 texture data를 reload

즉 현재 `[SUSPICIOUS_TEXTURE] reason=swizzle`은 단순 문자열 경고가 아니라 **실제 texture reload/validity 판단 경계**와 일치한다.

## 6. 현재 살아 있는 후보 우선순위

1. **surface/texture reinterpretation + swizzle/cache synchronization**
   - 특히 `f4c24000` 계열
2. **depth attachment state / precision과 해당 draw의 depth test-write-compare 상관관계**
   - 현재 정상 draw별 fixed-function state correlation 로그는 부족함
3. **feedback-loop / attachment dependency 중 아직 직접 증거가 없는 세부 경로**
4. `halfZ=0` shader Z conversion
   - 위 후보를 소진하기 전에 전역 제거하지 않는다.

낮은 우선순위 / 반복 금지:
- Position Invariance
- viewport depth-range clamp
- depthBiasClamp
- LOD 일반 설정 / Force Maximum LOD
- RT barrier variants / forced split
- depthclip / pipeline pNext / VS auxHash key
- startup pipeline `-13` 2건
- 오래된 GLSL failure `78a2659662685d55_0000000000000079`

## 7. 현재 source-level 핵심 구조

`LatteTexture.cpp`:
- overlapping guest-memory textures를 찾는다.
- `LatteTexture_CanTextureBeRepresentedAsView()`로 existing texture/view 재사용 가능성을 판정한다.
- format view compatibility와 texel-size compatibility를 별도로 판정한다.
- incompatible representation이면 별도 data texture 생성 가능성이 열린다.

`LatteTextureLegacy.cpp`:
- shader texture bind 때 lookup/create mapping 수행
- swizzle 변경 또는 mip physical address 변경 시 reload 여부 결정

따라서 다음 분석은 **같은 guest address가 어떤 조건에서 0x11/0x1a representation으로 분기되고, GPU-updated data가 어느 representation으로 동기화되는지**를 추적한다.

## 8. Tekken 1P → 2P — 별도 트랙

확인:
- physical controller → Cemu player0 → VPAD channel0
- VPAD connected=1, player=0
- KPAD 0–3 disconnected
- 게임에서는 2P side로 동작
- 테스트한 x64 Cemu에서도 동일

ARM64 InputManager player-index misassignment는 강하게 하향.
Bayonetta graphics 분석과 섞지 않는다.

## 9. 작업 원칙

- source/static verification → 최소 A/B → 필요한 경우에만 CI 1회
- 이미 끝난 실험 반복 금지
- 한 build에 다른 가설 혼합 금지
- 화면 관찰과 로그 fact 분리
- VS `DEFAULT_VAL` synthesize rollback 금지
- 충분한 증거 전 `halfZ` 전역 변경 금지

# NEXT ACTION

1. **새 빌드 없이** `LatteTexture_CanTextureBeRepresentedAsView()`와 `LatteTexture_CreateMapping()`의 format/isDepth/overlap 분기 전체를 추적한다.
2. `f4c24000`의 `0x11 ↔ 0x1a` representation이:
   - 하나의 renderer view인지
   - 별도 base texture인지
   - compatible relation + GPU copy synchronization 대상인지
   를 source로 확정한다.
3. render-target write 이후 `lastRenderTargetSwizzle`, `isUpdatedOnGPU`, compatible texture update 경로를 추적해 swizzle reload가 최신 GPU 데이터를 잃을 수 있는 경계가 있는지 확인한다.
4. 기존 로그에서 `f4c24000`, `f57c8000`, main depth `f5442800`을 역할별로 분리한다.
5. 이 정적 분석에서 의심 경계가 하나로 좁혀질 때만 **관찰 전용 최소 diagnostic**을 설계한다.
6. CI는 그 diagnostic이 실제로 필요한 것이 확인되기 전에는 실행하지 않는다.

## New-tab startup prompt

`Cemu ARM64 Bayonetta 2 원거리 폴리곤 플리커링 분석을 이어간다. GitHub의 CURRENT_HANDOFF.md, TECH_BIBLE.md, DEBUG_HISTORY.md를 먼저 읽고 runtime-experiments-arm64 HEAD와 code-changing baseline fa17d83을 구분해라. 이미 끝난 Position Invariance, viewport depth-range, depthBiasClamp, Force Maximum LOD/LOD, RT barrier variants, forced split, depthclip, pipeline pNext, VS auxHash 실험을 반복하지 말고 NEXT ACTION의 f4c24000 surface reinterpretation/swizzle cache 경로부터 계속해.`
