# Cemu Windows ARM64 / Adreno TECH BIBLE

> 이 문서는 프로젝트의 **확정된 사실, 구조, 원칙**만 기록한다. 실험별 세부 결과는 `DEBUG_HISTORY.md`, 현재 이어서 할 일은 `CURRENT_HANDOFF.md`를 본다.

## 1. Project scope

- Target: **Cemu on Windows ARM64**
- Primary hardware: **Snapdragon X Elite / Adreno X1-85**
- Primary graphics API: **Vulkan**
- Repository: `npark2860-cyber/Cemu-Windows-ARM64`
- 현재 작업 branch/HEAD는 고정값으로 이 문서에 박지 않고 **`CURRENT_HANDOFF.md`와 실제 GitHub 상태를 source of truth로 사용**한다.
- 모든 신규 진단/실험 기능은 가능한 한 **UI의 checkbox 또는 동등한 런타임 제어 방식**으로 개별 ON/OFF 가능해야 한다.

## 2. Build architecture

Windows ARM64 CI의 핵심 구성:

- Runner: `windows-11-arm`
- MSVC ARM64 environment
- Compiler: `clang-cl`
- Generator: Ninja
- CMake: 3.29.x 계열
- Dependency manager: vcpkg
- Build command: `cmake --build build`

따라서 Configure가 성공하고 `Build Cemu` 단계에서 실패하면 우선순위는 **C++ 소스/헤더/심볼/링크 오류**이며, vcpkg 또는 ARM64 툴체인을 먼저 의심하지 않는다.

## 3. Confirmed ARM64 / Adreno facts

### 3.1 Shader key / VS default value issue

2026-08-16에 Vertex Shader의 missing/default input에 대해 **DEFAULT_VAL synthesize**를 도입하여 shader key 불안정 문제를 해결했다.

확인된 결과:

- Adreno X1-85에서 BOTW 렌더 정상화
- Tekken Tag Tournament 2 렌더 정상화
- 기존 `VK_ERROR_UNKNOWN (-13)` 경로 해소
- 이 수정은 확정된 기반 수정으로 취급하며 임의로 되돌리지 않는다.
- GS 관련 경로는 별도 검증 대상이다.

### 3.2 Wii U decrypt

- Wii U decrypt는 Windows ARM64에서 동작 확인됨.

### 3.3 Game-level observations

- BOTW: ARM64에서 정상 구동 가능한 기준 빌드가 존재한다.
- Bayonetta 2: x64 Cemu 2.5/2.6 계열에서는 그래픽 문제가 있어도 실행되지만, 일부 ARM64 빌드에서는 강제 종료가 발생했다.
- Tekken 관련 과거 그래픽/셰이더 문제와 이후 1P/2P 문제는 서로 다른 이슈로 취급한다.

### 3.4 Bayonetta 2 / XCX occlusion-query facts

현재까지 캡처로 확정된 차이는 다음과 같다.

- **Bayonetta 2**: CPU occlusion query `type=0` 경로를 사용한다.
- Bayonetta 2에서는 completed `GET_READY_ZERO`가 대량 존재하며, 해당 zero는 snapshot 누락이나 unconsumed slot overwrite로 설명되지 않는다. 즉 현재 캡처 기준으로 실제 완료·소비된 query 결과다.
- **Xenoblade Chronicles X**: GPU occlusion query `type=2` 경로를 사용한다.
- XCX 캡처에서는 exported `GX2QueryGetOcclusionResult()` 소비가 관찰되지 않았다.
- 따라서 Bayo2와 XCX의 query-consumption 모델을 동일하다고 가정하지 않는다.

## 4. Vulkan / Adreno debugging principles

1. **한 번에 한 변수**를 바꾼다.
2. 이미 배제된 원인을 동일 조건으로 반복 실험하지 않는다.
3. 성공한 빌드/commit/artifact를 반드시 기준점으로 보존한다.
4. 로그에서 최초 오류를 우선한다. 후속 오류는 cascade일 수 있다.
5. Vulkan 진단 기능은 전역 강제 변경보다 **UI에서 개별 toggle** 가능하도록 한다.
6. Adreno workaround는 GPU vendor/feature 조건과 결합해 범위를 최소화한다.
7. 일반화 가능한 수정과 진단 전용 코드는 분리한다.
8. CI 비용 절감을 위해 소스/문법/호출부 정적 검증 후 필요한 경우에만 Actions를 실행한다.
9. 진단 trace는 가능한 한 observation-only로 유지하고, 관찰 단계와 behavior change 실험을 분리한다.

## 5. Diagnostic UI policy

진단판의 항목은 세 상태로 구분한다.

- 활성화 가능: 실제 프로브/로그 경로까지 연결됨
- 회색/비활성: UI 항목은 있으나 실제 진단 프로브가 아직 미연결 또는 현재 빌드에서 미지원
- 숨김: 아직 구현 전이며 UI에도 노출하지 않음

회색 항목은 "원인이 배제됨"을 뜻하지 않는다. 단지 **현재 빌드에서 해당 진단을 켤 수 없다는 뜻**이다.

대표 진단 대상:

- Semaphore flow
- Command-buffer lifecycle
- Fence lifecycle
- Shader interface
- SPIR-V compile failure
- Attachment usage
- Feedback-loop use
- Descriptor / resource lifetime

## 6. Known generalized Vulkan patch direction

과거 진단 과정에서 검토/적용된 일반화 방향:

- Swapchain attachment의 `VK_ATTACHMENT_LOAD_OP_DONT_CARE` 사용 재검토
- command-buffer usage flags 재검토
- `DrawBackbufferQuad` clear 타이밍을 renderpass 외부로 이동하는 방식 검토
- renderpass 내부 `vkCmdClearAttachments` 의존 제거 방향

이 항목들은 이미 적용 여부/정확한 commit을 `DEBUG_HISTORY.md`와 현재 소스에서 확인한 뒤 다룬다. 문서만 보고 중복 적용하지 않는다.

## 7. Documentation protocol

### TECH_BIBLE.md
- 확정된 사실
- 구조
- 프로젝트 원칙
- 되돌리면 안 되는 기반 수정

### DEBUG_HISTORY.md
- 날짜별 실험
- 성공/실패 빌드
- 로그/덤프
- 배제된 원인
- 새로 확인된 사실

### CURRENT_HANDOFF.md
- 현재 저장소 / branch / code checkpoint
- 마지막 정상 빌드
- 현재 테스트 빌드
- 옵션/checkbox 상태
- 살아 있는 가설
- NEXT ACTION

새 탭에서는 반드시 이 세 문서를 먼저 읽고, GitHub의 실제 branch/HEAD와 대조한다.

## 8. Rules that must not be violated

- 확정된 VS DEFAULT_VAL synthesize 수정 임의 제거 금지
- permanent PS DEFAULT_VAL linkage compatibility 수정 임의 제거 금지
- known-good pre-e834 runtime behavior 임의 제거 금지
- AArch64 generated-code cache flush 수정 임의 제거 금지
- 이미 배제된 실험의 무의미한 반복 금지
- Bayo2와 XCX의 query-consumption 경로를 동일하다고 가정하지 말 것
- 서로 다른 emulator/project의 Run ID 혼용 금지
- Eden/SnapRyu의 GitHub Actions Run ID를 Cemu 저장소 Run ID로 취급하지 말 것
- UI 제어 요구를 무시한 하드코딩 실험 금지
- 실패한 빌드 위에 원인 미확인 상태로 진단 기능을 계속 누적하지 말 것
