# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-08-27 KST  
> 목적: 새 탭이 이 문서만 읽고 즉시 현재 작업을 이어갈 수 있게 한다.  
> 완료된 장기 사실은 `TECH_BIBLE.md`, 세부 실험 이력은 `DEBUG_HISTORY.md`에 보존한다.

## 1. 현재 최우선 목표

현재 1순위는 **Bayonetta 2 (JP) Vulkan 원거리 폴리곤 플리커링** 원인 규명이다.

증상:
- 가까운 오브젝트의 일반 렌더 문제가 아니라 **멀리 있는 폴리곤이 거리에서 깜빡이는/flickering 현상**.
- crash가 현재 Bayonetta 2 주 증상이 아니다.

테스트 환경:
- Windows 11 ARM64
- Snapdragon X Elite / Qualcomm Adreno X1-85
- Vulkan 1.3
- Bayonetta 2 JP Title ID: `00050000-1011B900`
- Title version: v1
- 현재 확인 드라이버: Build `f22d572733`, compiler `E031.50.36.00`, branch `pp165`

## 2. 기준 저장소 / 보호 기준점

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

주 작업 브랜치:
`runtime-experiments-arm64`

2026-08-27 GitHub에서 다시 확인한 코드 기준 HEAD:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

Commit:
`diagnostics: require complete 77-item coverage`

이 `fa17d83`을 **현재 일반 진단/호환성 코드 기준점**으로 취급한다.
문서-only commit이 이후 추가될 수 있으므로 새 탭에서는 실제 branch HEAD와 code-changing parent를 구분한다.

### 절대 되돌리지 말 것

- VS producer-side `DEFAULT_VAL` synthesize / linkage compatibility fix
- AArch64 generated-code cache / I-cache coherency fix
- known-good pre-e834 Vulkan compatibility behavior
- 진단 항목을 실제 runtime producer와 연결한 77/77 구조

## 3. Runtime Diagnostics 현재 상태

`fa17d83`에서 Diagnostics 구현 집합은 **77/77 coverage를 강제**하도록 정리됐다.

핵심 규칙:
- `RuntimeDiagnostics::Enabled(flag)` = master + implemented + per-flag enabled
- UI 선택 가능 여부는 `RuntimeDiagnostics::IsImplemented()` 기준
- verifier가 UI `kDiagItems[]`와 implemented set의 정확한 일치를 검사

따라서 예전 handoff의 "여러 checkbox가 회색/미구현" 설명은 **현재 기준으로 폐기**한다.
새 진단판을 또 만들기보다 현존 77/77 빌드와 소스 A/B를 우선한다.

## 4. Bayonetta 2 — 지금까지 배제/하향된 가설

### A. Position Invariance — 주원인에서 배제

Cemu Metal backend에는 Bayonetta/Bayonetta 2용 Position Invariance 선례가 있음.
Vulkan GLSL에는 `invariant gl_Position`이 없어서 강한 후보로 보였음.

실험:
- Bayonetta 2 캡처의 VS hash 112개를 대상으로 그래픽팩 shader replacement 생성
- 각 VS에 `invariant gl_Position;`만 추가
- Cemu 본체 빌드 없이 A/B

사용자 관찰 결과:
**플리커링 전혀 개선되지 않음.**

결론:
- Position Invariance는 현재 증상의 주원인 후보에서 크게 하향.
- 같은 실험을 반복하지 않는다.

### B. Vulkan viewport depth range clamp — 주원인에서 배제

관찰:
- Bayonetta 2는 실행 중 거의 전반적으로 `rawNear=-1`, `rawFar=1`, `halfZ=0` 패턴을 사용.

실험:
- Bayonetta 2 전용으로 Vulkan viewport depth를 out-of-range일 때 `0..1`로 clamp.
- 실제 로그에서 대량의 `-1..1 -> 0..1` 적용을 확인.

사용자 관찰 결과:
**플리커링 그대로.**

결론:
- `VkViewport.minDepth/maxDepth`의 단순 `-1..1` handling은 주원인에서 배제.
- 이 clamp 실험을 다음 빌드에 섞지 않는다.

## 5. 현재 진행 중 실험 — Vulkan depthBiasClamp

목적:
- Vulkan은 `vkCmdSetDepthBias(constant, clamp, slope)`에서 Wii U `PA_SU_POLY_OFFSET_CLAMP`를 전달.
- OpenGL backend는 clamp를 실질적으로 사용하지 않는 차이가 있어, Bayonetta 2에서 Vulkan clamp만 `0.0f`로 맞추는 A/B를 시도.

전용 브랜치:
`exp/bayo2-depth-bias-clamp`

현재 HEAD:
`bdb644d89d8963ab7a39d8a586f6d73ac3d73f92`

Commit:
`fix: include CafeSystem for Bayonetta depth-bias experiment`

성공 workflow:
- `Cemu ARM64 Bayonetta2 Depth Bias Experiment`
- Run #4
- Run ID: `33056046387`
- result: **SUCCESS**

이 빌드의 Cemu init short hash도 최신 런타임 로그에서 `bdb644d`로 확인됨.

### 최신 로그

파일:
`log(20260827-093536).txt`

로그 환경:
- Cemu `bdb644d`
- Bayonetta 2 JP `00050000-1011B900`, v1
- Qualcomm Adreno X1-85
- Diagnostics master ON

활성 graphic packs:
- Contrasty
- Graphics 2560x1440 / High / 16x
- 60 FPS Cutscenes
- **Force Maximum LOD**
- Dynamic Shadows (Vulkan)
- Portal

중요: Position Invariance Test graphic pack은 최신 로그의 active pack 목록에 없음.

### `[BAYO2_DEPTH_BIAS]` 최신 로그 판독

로컬 전체 파일에서 기록된 diagnostic line을 집계:
- `[BAYO2_DEPTH_BIAS]` 기록: **128건** (`n=0..127`)
- 128/128 모두 동일:
  - `offset=0`
  - `slope=-0`
  - `rawClamp=0`
  - `appliedClamp=0`
  - `nonZeroClampCount=0`

해석:
- **기록된 128회에서는 원래 clamp 자체가 0이었기 때문에 실험 패치가 동작을 바꾼 것이 없다.**
- logger가 128건 이후 더 이상 같은 항목을 출력하지 않는 구조라면, 이 기록만으로 세션 후반까지 non-zero clamp가 절대로 없었다고 단정하지 않는다.
- 최신 로그에 있는 두 startup `PIPELINE_FAIL result=-13`, 기존 `GLSL_FAIL` 1건, suspicious swizzle 4건은 이전 Bayonetta 로그에서도 보이던 기존 신호이며 depth-bias 실험에서 새로 생긴 것으로 보지 않는다.

### 아직 기록되지 않은 것

**`bdb644d` depth-bias build에서 실제 화면 플리커링이 개선/동일/악화됐는지 사용자의 최종 시각 판정은 이 handoff 갱신 시점에 아직 명시적으로 기록되지 않았다.**

새 탭에서는 이것을 추측하지 말고, 현재 대화/사용자 답변이 없다면 시각 결과부터 확인한다.

## 6. Bayonetta 2에서 현재 살아 있는 후보

Position Invariance와 단순 viewport depth range가 실패한 뒤 우선순위:

1. **Depth format / 실제 depth precision / depth attachment 상태**
2. **Depth bias 자체의 offset/slope 사용 여부와 문제 장면 correlation**
   - 단, 최신 로그의 처음 128건은 모두 zero라 clamp 자체는 약한 후보
3. **Surface/texture reinterpretation 및 swizzle**
   - 반복 관찰 주소 예: `f4c24000`
   - 같은 메모리가 format `0x11`/`0x1a` 등으로 다뤄진 과거 로그 단서가 있음
   - `[SUSPICIOUS_TEXTURE] reason=swizzle`가 반복됨
4. **LOD / graphics-pack 영향**
   - 최신 테스트에도 `Force Maximum LOD`가 활성화되어 있음
   - 원거리 증상이라는 점 때문에 반드시 별도 A/B 가치가 있음
5. `halfZ=0`일 때 Vulkan GLSL의 `gl_Position.z = (z+w)/2` 변환
   - 정상 clip-space 변환이므로 무작정 제거하는 파괴적 실험보다 위 후보를 먼저 본다.

낮은 우선순위:
- startup pipeline `-13` 2건
- 기존 PS GLSL syntax failure 1건
- feedback-loop (지원/사용 로그상 직접 증거 약함)
- RT alias (기존 master 로그에서 0)

## 7. Tekken 1P → 2P 문제 — 별도 트랙

Tekken Tag Tournament 2의 컨트롤러 문제는 Bayonetta 그래픽 문제와 섞지 않는다.

확인된 상태:
- Cemu player0 → VPAD channel0까지는 정상
- KPAD 0~3은 disconnected
- 실제 게임에서는 1P로 지정한 컨트롤러가 2P side로 동작
- 동일 증상이 테스트한 x64 Cemu에서도 발생

따라서 ARM64 input index misassignment 가설은 약함.
다음 고정보다 먼저 GamePad/VPAD0 vs Pro Controller/KPAD 경로 및 Tekken join/side semantics를 소스 수준에서 본다.

## 8. 빌드/작업 원칙

- GitHub Actions 비용을 아끼기 위해 **정적 소스 검증 → 최소 A/B → CI 1회** 순서.
- 서로 다른 가설을 한 빌드에 섞지 않는다.
- 실패한 viewport clamp 실험을 depth-bias 실험에 포함하지 않는다.
- Position Invariance 그래픽팩은 현재 기본 OFF.
- 새 Diagnostics Edition을 이유 없이 만들지 않는다.
- 화면 결과와 로그 결과를 구분해서 기록한다.

# NEXT ACTION

1. **먼저 `bdb644d` depth-bias build의 실제 시각 결과를 확정 기록한다.**
   - 개선 / 동일 / 악화
2. 화면이 동일했다면 depthBiasClamp는 우선순위에서 하향한다.
   - 기록된 첫 128건의 `rawClamp=0`도 함께 근거로 사용.
3. 그 다음 새 CI 전에 가장 값싼 A/B부터 수행:
   - `Force Maximum LOD`만 OFF, 나머지 graphic pack/settings 동일, 같은 장면 비교.
4. LOD A/B에서도 동일하면 다음 소스 분석을 진행:
   - 문제 장면의 depth attachment format/precision/state
   - depth test/write/compare op
   - depth bias offset/slope non-zero draw correlation
   - `SUSPICIOUS_TEXTURE` / swizzle 및 surface reinterpretation correlation
5. 충분한 증거가 생기기 전에는 `halfZ` 변환을 전역으로 제거하지 않는다.
6. 다음 실제 코드 A/B가 필요할 때는 `fa17d83` 일반 기준점에서 새 실험 브랜치를 만든다.

## New-tab startup prompt

`Cemu ARM64 Bayonetta 2 플리커링 분석을 이어간다. GitHub의 CURRENT_HANDOFF.md를 먼저 읽고 runtime-experiments-arm64 실제 HEAD와 실험 브랜치 상태를 확인한 뒤 NEXT ACTION부터 바로 실행해. VS DEFAULT_VAL synthesize는 절대 롤백하지 말고, 이미 실패한 Position Invariance와 viewport depth-range 실험을 반복하지 마.`
