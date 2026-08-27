# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-08-28 KST  
> 목적: 새 탭이 이 문서만 읽고 즉시 현재 작업을 이어갈 수 있게 한다.  
> 완료된 장기 사실은 `TECH_BIBLE.md`, 세부 실험 이력은 `DEBUG_HISTORY.md`에 보존한다.

## 1. 현재 최우선 목표

현재 1순위는 **Bayonetta 2 (JP) Vulkan 원거리 폴리곤 플리커링** 원인 규명이다.

정확한 증상:
- 가까운 오브젝트 일반 렌더 문제가 아니라 **멀리 있는 폴리곤이 거리에서 깜빡이는/flickering 현상**.
- crash가 현재 Bayonetta 2 주 증상이 아니다.

테스트 환경:
- Windows 11 ARM64
- Snapdragon X Elite / Qualcomm Adreno X1-85
- Vulkan 1.3
- Bayonetta 2 JP Title ID: `00050000-1011B900`
- Title version: v1
- driver Build `f22d572733`
- compiler `E031.50.36.00`
- branch `pp165`

## 2. 저장소 / 코드 기준점

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

주 작업 브랜치:
`runtime-experiments-arm64`

현재 일반 진단/호환성 **code-changing baseline**:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

Commit:
`diagnostics: require complete 77-item coverage`

문서-only `[skip ci]` commit들이 이 뒤에 붙으므로, 새 탭에서는 branch HEAD와 실제 code-changing baseline을 구분한다.

### 절대 되돌리지 말 것

- VS producer-side `DEFAULT_VAL` synthesize / linkage compatibility fix
- AArch64 generated-code cache / I-cache coherency fix
- known-good pre-e834 Vulkan compatibility behavior
- 77/77 Runtime Diagnostics 구조

## 3. Runtime Diagnostics 상태

`fa17d83`에서 **77/77 exact coverage**.

핵심:
- `RuntimeDiagnostics::Enabled(flag)` = master + implemented + per-flag enabled
- UI selectable 여부 = `RuntimeDiagnostics::IsImplemented()`
- verifier가 UI `kDiagItems[]`와 implemented set 정확 일치 검사

예전의 "여러 checkbox가 회색/미구현" 설명은 현재 기준으로 폐기한다.
새 Diagnostics Edition을 이유 없이 만들지 않는다.

## 4. Bayonetta 2 — 이미 실패/하향된 가설

### A. Position Invariance — 주원인에서 하향

근거:
- Metal backend에 Bayonetta/Bayonetta 2 Position Invariance 선례
- Vulkan GLSL path에는 `invariant gl_Position` 없음

A/B:
- captured VS 113개 중 all-zero 내부 shader 1개 제외
- 112개 VS graphics-pack replacement
- 각 VS에 `invariant gl_Position;`만 추가
- shader compile/SPIR-V 변화 확인으로 실험 적용 검증

사용자 관찰:
**플리커링 전혀 개선되지 않음.**

결론:
- 현재 distant-polygon flicker의 주원인 후보에서 크게 하향
- 동일 조건 반복 금지
- Position Invariance Test pack은 기본 OFF

### B. Vulkan viewport depth range clamp — 주원인에서 배제

runtime observation:
- 대량의 `rawNear=-1`, `rawFar=1`, `halfZ=0`

A/B:
- Bayonetta 2에서 out-of-range Vulkan viewport depth를 `0..1`로 clamp
- 실제 runtime에서 대량 적용 확인

사용자 관찰:
**플리커링 그대로.**

결론:
- 단순 `VkViewport.minDepth/maxDepth` `-1..1` handling은 주원인에서 배제
- 후속 build에 이 clamp를 섞지 않는다.

### C. Vulkan depthBiasClamp — 주원인에서 크게 하향

전용 브랜치:
`exp/bayo2-depth-bias-clamp`

Successful experiment HEAD:
`bdb644d89d8963ab7a39d8a586f6d73ac3d73f92`

Workflow:
`Cemu ARM64 Bayonetta2 Depth Bias Experiment`

Successful Run:
- #4
- ID `33056046387`
- result: **SUCCESS**

실험:
- Bayonetta 2에서만 Vulkan `depthBiasClamp=0.0f`
- offset/slope는 변경하지 않음

최신 로그:
`log(20260827-093536).txt`

기록된 첫 128건 (`n=0..127`) 모두:
- `offset=0`
- `slope=-0`
- `rawClamp=0`
- `appliedClamp=0`
- `nonZeroClampCount=0`

사용자 화면 판정:
**플리커링 전혀 개선되지 않음.**

결론:
- 적어도 기록된 구간에서는 원래 clamp가 이미 0이라 패치가 GPU state를 바꾸지 않음
- 화면 결과도 변화 없음
- `depthBiasClamp` 단독 가설은 크게 하향
- 동일 A/B 반복 금지
- 출력 제한 때문에 세션 전체에 non-zero clamp가 절대 없었다고 단정하지는 않음

## 5. 현재 가장 값싼 다음 A/B — Force Maximum LOD

최신 로그에서 활성 상태:
- Contrasty
- Graphics 2560x1440 / High / 16x
- 60 FPS Cutscenes
- **Force Maximum LOD**
- Dynamic Shadows (Vulkan)
- Portal

공식 Cemu graphic pack 기준 `Force Maximum LOD`는 Bayonetta 2의 high-LOD culling distance를:

- 기본 `100.0`
- → `200.0`

으로 직접 변경한다.

즉 원거리 모델/폴리곤 표시 거리를 바꾸는 변수다.
현재 증상이 원거리에서 발생하므로 build 없이 검증 가능한 최우선 A/B다.

### 다음 테스트 고정 조건

**`Force Maximum LOD`만 OFF**

나머지는 그대로 유지:
- Contrasty ON
- Graphics 2560x1440 / High / 16x
- 60 FPS Cutscenes ON
- Dynamic Shadows (Vulkan) ON
- Portal ON
- Position Invariance Test OFF
- depth-range clamp build 사용 금지

같은 장면 / 같은 카메라 거리에서 플리커링을 비교한다.

## 6. LOD 다음 살아 있는 Bayonetta 후보

LOD A/B가 동일일 때 순서:

1. **Depth format / 실제 depth precision / depth attachment state**
2. **Depth test/write/compare + non-zero offset/slope/bias draw correlation**
3. **Surface/texture reinterpretation / swizzle**
   - 과거 `[SUSPICIOUS_TEXTURE] reason=swizzle` 반복
   - 예: `f4c24000` 등이 format `0x11` / `0x1a`로 재해석된 단서
4. `halfZ=0`일 때 GLSL `gl_Position.z = (z+w)/2`
   - Vulkan clip-space 변환 자체는 정상 목적이므로 전역 제거보다 위 후보 먼저

낮은 우선순위:
- Position Invariance
- simple viewport depth-range clamp
- depthBiasClamp 단독 처리
- startup pipeline `-13` 2건
- 기존 GLSL failure 1건
- feedback-loop without direct evidence
- RT alias where previous master log showed 0

## 7. Tekken 1P → 2P — 별도 트랙

확인:
- physical controller → Cemu player0 → VPAD channel0
- VPAD connected=1, player=0
- KPAD 0–3 disconnected
- 게임에서는 2P side로 동작
- 테스트한 x64 Cemu에서도 동일

따라서 ARM64 InputManager player-index misassignment는 강하게 하향.

다음:
- GamePad/VPAD0 vs Pro Controller/KPAD
- Tekken join/side semantics

Bayonetta graphics 분석과 섞지 않는다.

## 8. 작업 원칙

- source/static verification → 최소 A/B → CI 1회
- 한 build에 서로 다른 가설을 섞지 않는다.
- 실패한 viewport clamp를 후속 실험에 포함하지 않는다.
- 실패한 depthBiasClamp A/B를 반복하지 않는다.
- Position Invariance pack OFF
- 새 Diagnostics Edition을 이유 없이 만들지 않는다.
- 화면 결과와 로그 사실을 구분한다.
- VS `DEFAULT_VAL` synthesize rollback 금지

# NEXT ACTION

1. **새 CI 없이 `Force Maximum LOD`만 OFF** 한다.
2. 나머지 graphics packs/settings는 모두 동일하게 유지한다.
3. 동일 장면/카메라에서 distant-polygon flicker가:
   - 개선
   - 동일
   - 악화
   중 무엇인지 판정한다.
4. LOD A/B가 동일이면 새 build 전에 기존 로그/source로:
   - depth attachment format/precision
   - depth test/write/compare op
   - non-zero offset/slope bias draw correlation
   - suspicious swizzle / surface reinterpretation correlation
   을 분석한다.
5. 충분한 증거 전에는 `halfZ` 변환을 전역 제거하지 않는다.
6. 다음 코드 A/B가 필요하면 `fa17d83` 일반 code baseline에서 새 실험 브랜치를 만든다.

## New-tab startup prompt

`Cemu ARM64 Bayonetta 2 플리커링 분석을 이어간다. GitHub의 CURRENT_HANDOFF.md, TECH_BIBLE.md, DEBUG_HISTORY.md를 먼저 읽고 runtime-experiments-arm64 실제 HEAD와 code-changing baseline을 구분한 뒤 NEXT ACTION부터 실행해. VS DEFAULT_VAL synthesize는 절대 롤백하지 말고, 이미 실패한 Position Invariance, viewport depth-range, depthBiasClamp 실험을 반복하지 마.`
