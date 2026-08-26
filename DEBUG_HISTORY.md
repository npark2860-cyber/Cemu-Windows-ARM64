# Cemu Windows ARM64 / Adreno DEBUG HISTORY

> 날짜별 실험 결과를 누적한다. 현재 이어서 할 일은 `CURRENT_HANDOFF.md`를 본다.

## 2026-08-16 — VS DEFAULT_VAL synthesize

### Problem

Adreno에서 일부 vertex input/default value 처리와 shader key 안정성이 깨지면서 Vulkan 오류 및 렌더 문제 발생.

### Change

- VS DEFAULT_VAL synthesize 도입
- 누락/default vertex input을 안정적으로 shader key에 반영

### Result

- Adreno X1-85에서 BOTW 렌더 정상 확인
- Tekken Tag Tournament 2 렌더 정상 확인
- `VK_ERROR_UNKNOWN (-13)` 해소 확인

### Status

- **확정 수정**
- 임의 rollback 금지
- GS 경로는 미검증

---

## 2026-08-24 ~ 2026-08-26 — 범용 Vulkan 진단/Adreno runtime experiments

### Goal

게임별 임시 수정이 아니라 Windows ARM64 + Adreno에서 Vulkan runtime 문제를 범용적으로 진단할 수 있는 버전을 만든다.

### Principles established

- 모든 실험/진단 기능은 UI에서 개별 ON/OFF 가능해야 함
- 한 번에 한 변수만 바꿀 것
- 이미 배제된 실험을 반복하지 않을 것
- RenderDoc/WinDbg/내부 로그를 함께 사용하되, 로그의 최초 실패 지점을 우선할 것

### Diagnostic areas worked on

- Descriptor/resource lifetime
- Semaphore flow
- Command-buffer lifecycle
- Fence lifecycle
- Shader interface
- SPIR-V compile failure
- Attachment usage
- Feedback-loop use

### UI observation

진단 UI에서 회색 처리된 항목은 원인 배제 상태가 아니라 **아직 프로브가 연결되지 않았거나 현재 빌드에서 사용할 수 없는 항목**으로 취급한다.

---

## 2026-08-26 — CI regression investigation

### Known historical checkpoint

동일 `runtime-experiments-arm64` 계열에서 한 시점까지 빌드 성공 후, 진단 기능 연결 커밋들이 연속으로 들어가면서 C++ 빌드 회귀가 발생했다.

조사 중 확인된 핵심:

- Configure 단계는 통과
- 실패는 `Build Cemu` 단계
- 따라서 우선순위는 C++ compile/link 오류
- ARM64 runner/vcpkg/CMake 자체 실패로 단정하지 않음

### Important process lesson

여러 진단 기능을 한 번에 추가하고 각 커밋의 빌드 완료 전에 다음 푸시를 이어가면 최초 회귀 commit을 찾기 어려워진다. 이후부터는 성공 checkpoint를 고정하고, 정적 검증 후 빌드를 실행한다.

---

## 2026-08-27 — Current diagnostic build recovered

### Repository

- Repo: `npark2860-cyber/Cemu-Windows-ARM64`
- Branch: `runtime-experiments-arm64`

### Source checkpoint

- Last verified non-documentation code commit: `8bca12fa5119f12b34b73ba5482d2ffeea89f5a8`
- Commit message: `Fix literal tab escapes in RT diagnostics`

### GitHub Actions

- Workflow: `Cemu ARM64 Diagnostic Edition`
- Run number: `#24`
- Run ID: `33017387410`
- Result: **success**
- Head SHA: `8bca12fa5119f12b34b73ba5482d2ffeea89f5a8`
- Artifact: `cemu-arm64-diagnostic-edition`
- Artifact ID: `9626115561`
- Artifact SHA-256 digest: `9540922b3f7b0155148f6eadcf7469e4d1e4d58e9591bee53cbdb05429f040f3`

### Meaning

직전의 CI compile regression은 현재 source checkpoint에서는 해결되어 **진단판 포함 Windows ARM64 빌드가 다시 성공**한다.

### Current runtime question

진단 UI에서 일부 항목이 회색 비활성 상태다. 이는 해당 진단 기능의 UI shell은 있으나 실제 runtime probe가 미연결/미지원인 상태일 가능성이 높으므로, 다음 작업은 회색 항목 각각의 실제 연결 여부를 소스에서 확인하는 것이다.

---

## Logging template for future experiments

각 실험은 아래 형식으로 추가한다.

```text
## YYYY-MM-DD — Experiment name

Goal:
Build/commit:
Game:
GPU/driver:
Checkbox/options:
Log/dump:
Observed result:
Confirmed fact:
Ruled out:
Still possible:
Next action:
```

완료되어 더 이상 현재 상태에 필요 없는 내용은 `CURRENT_HANDOFF.md`에서 제거하고 이 파일에 남긴다.
