# Cemu Windows ARM64 / Adreno TECH BIBLE

> 이 문서는 프로젝트의 **확정된 사실, 구조, 원칙, 되돌리면 안 되는 기준점**만 기록한다. 실험별 세부 결과는 `DEBUG_HISTORY.md`, 현재 이어서 할 일은 `CURRENT_HANDOFF.md`를 본다.

## 1. Project scope

- Target: **Cemu on Windows ARM64**
- Primary hardware: **Snapdragon X Elite / Qualcomm Adreno X1-85**
- Primary graphics API: **Vulkan**
- Repository: `npark2860-cyber/Cemu-Windows-ARM64`
- Main debug branch: `runtime-experiments-arm64`
- correctness / compatibility가 performance optimization보다 우선한다.
- 모든 신규 진단/실험은 가능한 한 UI checkbox 또는 동등한 runtime control로 개별 ON/OFF 가능해야 한다.
- GitHub Actions 비용을 줄이기 위해 **source/static verification → minimal A/B → CI 1회** 순서를 우선한다.

## 2. Protected baselines

### Clean Windows ARM64

`windows-arm64`

- clean baseline SHA: `6129066e8bfa3ad89556756712c11d003e0ad31f`
- 실험용으로 수정하지 않는다.

### Known-good Adreno compatibility

`final-adreno-compat-arm64`

- commit: `e14b764b55bf6a5d6f561e7bf1bde8dc17d1b600`
- successful Actions run: `31864755800`
- artifact: `cemu-arm64-final-adreno-compat`

### Current generic diagnostic/code baseline

`runtime-experiments-arm64`

- last verified code-changing baseline: `fa17d834bfebd9a41c598b1b1b702000d0ff4618`
- commit: `diagnostics: require complete 77-item coverage`
- 문서-only commit이 이후 붙을 수 있으므로 branch HEAD와 code-changing baseline을 구분한다.

## 3. Build architecture

Windows ARM64 CI 핵심 구성:

- Runner: `windows-11-arm`
- MSVC ARM64 environment
- Compiler: `clang-cl`
- Generator: Ninja
- CMake 3.29.x 계열
- vcpkg
- build: `cmake --build build`

Configure가 성공하고 `Build Cemu`에서 실패하면 우선 C++ source/header/symbol/link 오류를 본다. runner/vcpkg/toolchain부터 추측하지 않는다.

## 4. Do-not-rollback fixes

### 4.1 VS → PS `DEFAULT_VAL` producer-side synthesize

Adreno에서 producer가 PS가 요구하는 varying을 실제로 export하지 않는 경우 Vulkan interface/pipeline 문제가 발생했다.

확정된 해결 방향:

- PS input을 무조건 상수로 치환하지 않는다.
- matching producer export가 존재하면 실제 varying을 유지한다.
- matching producer export가 없을 때 producer-side synthetic output을 만들고 해당 `DEFAULT_VAL`을 제공한다.

확인된 결과:

- BOTW 렌더 정상화
- Tekken Tag Tournament 2 렌더 정상화
- 관련 `VK_ERROR_UNKNOWN (-13)` 해소
- shader/interface 안정화

이 수정은 프로젝트의 영구 호환성 기준이다. **임의 rollback 금지.**

GS 경로는 VS→PS/no-GS 경로와 동일하다고 가정하지 않는다.

### 4.2 AArch64 generated-code cache / ReadyRE coherency

ARM64 JIT generated code 실행 전 instruction-cache coherency를 보장하는 수정은 안정성 기준으로 유지한다.

### 4.3 pre-e834 Vulkan visual compatibility behavior

Adreno에서 거대 triangle / horizontal band 류 시각 회귀를 해결한 known-good 조합:

1. swapchain attachment loadOp `DONT_CARE → LOAD`
2. Vulkan command-buffer usage `ONE_TIME_SUBMIT → SIMULTANEOUS_USE` 2곳
3. `DrawBackbufferQuad`에서 pre-renderpass `ClearColorbuffer(padView)` 복원
4. renderpass 내부 `vkCmdClearAttachments()` 제거

이 조합은 검증된 compatibility baseline이다. 근본 책임을 Qualcomm driver 단독 문제로 단정하지 않는다.

## 5. Runtime Diagnostics architecture

`fa17d83` 기준 Diagnostics는 **77/77 구현 coverage를 강제**한다.

핵심 규칙:

- `RuntimeDiagnostics::Enabled(flag)` = master enabled + implemented + per-flag enabled
- UI selectable 여부 = `RuntimeDiagnostics::IsImplemented(flag)`
- verifier가 UI `kDiagItems[]`와 implemented set의 정확한 일치를 검사
- 예전의 다수 회색/미구현 checkbox 상태는 현재 기준으로 폐기한다.

따라서 새 Diagnostics Edition을 습관적으로 만들지 않는다. 기존 77/77 진단판과 source-level A/B를 우선한다.

주요 진단 범위:

- ARM64/JIT lifecycle, mapping, branch patch, ReadyRE
- command buffer / fence / semaphore / submit completion
- pipeline cache/create/failure/state/hash
- VS/PS/GS/shader interface/compile failure
- renderpass / attachment / load-store / barriers / RAW / WAW / self-dependency
- feedback-loop 관련 상태
- texture/cache/surface 관련 상태
- frame timing / GPU timestamp / CPU wait
- descriptor / upload / hitch / overhead / summary
- input/controller mapping

## 6. Confirmed hardware/runtime environment

현재 대표 테스트 환경:

- Windows 11 Home 25H2
- Qualcomm Adreno X1-85
- Vulkan 1.3
- driver build: `f22d572733`
- driver date: 2026-05-22
- compiler: `E031.50.36.00`
- driver branch: `pp165`
- RAM: 약 16 GB

Wii U decrypt는 Windows ARM64에서 동작 확인됨.

## 7. Bayonetta 2 graphics issue — confirmed scope

현재 Bayonetta 2 주 타겟은 crash가 아니라:

**멀리 있는 폴리곤이 거리에서 flicker하는 그래픽 문제**다.

대표 테스트 타이틀:

- Bayonetta 2 JP
- Title ID: `00050000-1011B900`
- v1

### Ruled down / do not repeat without new evidence

#### Position Invariance

Metal backend의 Bayonetta/Bayonetta 2 Position Invariance 선례를 근거로 Vulkan VS 112개에 `invariant gl_Position;`을 적용한 graphics-pack A/B를 수행했다.

사용자 관찰: **전혀 개선되지 않음.**

현재 증상의 주원인 후보에서 크게 하향한다.

#### Simple viewport depth-range clamp

Bayonetta 2는 runtime에서 대량으로 `rawNear=-1`, `rawFar=1`, `halfZ=0`을 사용했다.

Vulkan viewport depth를 out-of-range일 때 `0..1`로 clamp하는 A/B를 실제 대량 적용했으나 사용자 관찰은 **플리커링 그대로**였다.

따라서 `VkViewport.minDepth/maxDepth`의 단순 `-1..1` handling은 현재 주원인에서 배제한다.

### Depth-bias clamp fact

Vulkan backend는 `vkCmdSetDepthBias(constant, clamp, slope)`에 Wii U clamp 값을 전달하지만 OpenGL backend와 동작 차이가 있다.

Bayonetta 2 전용 `depthBiasClamp=0` 실험 빌드의 최신 로그 초반 128개 `[BAYO2_DEPTH_BIAS]` 기록에서는 모두:

- `offset=0`
- `slope=-0`
- `rawClamp=0`
- `appliedClamp=0`
- `nonZeroClampCount=0`

이었다.

따라서 **적어도 기록된 구간에서는 패치가 실제 GPU state를 바꾸지 않았다.** 이 사실만으로 세션 전체에 non-zero clamp가 절대 없었다고 과잉 일반화하지 않는다.

### Current higher-value candidates

- depth format / actual depth precision / depth attachment state
- depth test/write/compare + non-zero bias correlation
- surface/texture reinterpretation and swizzle
- LOD / graphics-pack interaction, 특히 `Force Maximum LOD`
- `halfZ=0` 시 GLSL `(z+w)/2` 변환은 정상 clip-space 변환이므로 파괴적 전역 제거보다 위 후보를 먼저 본다.

## 8. Tekken controller issue — separate track

Tekken Tag Tournament 2의 현재 1P→2P 현상은 과거 shader/pipeline 문제와 별개다.

확인된 로그 경계:

- physical controller → Cemu player0
- player0 → VPAD channel0
- VPAD connected=1, player=0
- KPAD 0–3 disconnected
- 실제 게임에서는 1P로 지정한 컨트롤러가 2P side에서 동작
- 테스트한 x64 Cemu에서도 같은 현상

따라서 ARM64 InputManager player-index misassignment는 강하게 하향한다. 다음은 GamePad/VPAD0 vs Pro Controller/KPAD 경로와 Tekken join/side semantics를 본다.

## 9. Debugging rules

1. 한 번에 한 변수만 바꾼다.
2. 이미 배제된 원인을 동일 조건으로 반복하지 않는다.
3. 성공 build/commit/artifact를 기준점으로 보존한다.
4. 로그 최초 오류를 우선한다. 뒤 오류는 cascade일 수 있다.
5. 화면 관찰과 로그 fact를 분리한다.
6. Adreno workaround 범위는 최소화한다.
7. 일반화 가능한 수정과 진단/게임 전용 A/B를 분리한다.
8. 새 build 전에 source/static verification을 끝낸다.
9. 실패 실험을 다음 실험에 섞지 않는다.
10. VS `DEFAULT_VAL` synthesize는 절대 되돌리지 않는다.

## 10. Documentation protocol

### `TECH_BIBLE.md`

- 확정 사실
- 구조/원칙
- 되돌리면 안 되는 기반 수정
- 반복하면 안 되는 명확한 배제 결과

### `DEBUG_HISTORY.md`

- 날짜별 실험
- build/run/branch
- 로그/덤프
- 성공/실패
- 배제된 가설

### `CURRENT_HANDOFF.md`

- 현재 branch/code checkpoint
- 현재 실험 build
- 최신 로그
- 살아 있는 가설
- NEXT ACTION

새 탭에서는 세 문서를 먼저 읽고 GitHub 실제 branch/HEAD와 대조한다.
