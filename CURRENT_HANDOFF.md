# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 이 파일은 **현재 상태만** 유지한다. 완료된 실험은 `DEBUG_HISTORY.md`로 이동한다. 새 탭은 이 파일의 `NEXT ACTION`부터 시작한다.

## 1. Current goal

Windows ARM64 / Snapdragon X Elite / Adreno X1-85 환경에서 Cemu Vulkan의 멈춤/강종/저성능 원인을 범용 진단판으로 좁힌다.

현재 우선순위는 **진단 UI에서 회색 비활성 상태인 항목들이 왜 비활성인지 소스에서 확인하고, 실제 runtime probe가 빠진 항목을 한 그룹씩 연결하는 것**이다.

## 2. Repository state

- Repository: `npark2860-cyber/Cemu-Windows-ARM64`
- Active branch: `runtime-experiments-arm64`
- Last verified **code-changing** HEAD: `8bca12fa5119f12b34b73ba5482d2ffeea89f5a8`
- Commit: `Fix literal tab escapes in RT diagnostics`

주의: 이 handoff 체계를 만들면서 위 code checkpoint 뒤에 문서 전용 commit이 추가되었다. 다음 탭에서는 반드시 GitHub에서 실제 branch HEAD를 다시 읽고, `8bca12fa...` 이후 변경이 문서-only인지 코드 변경인지 확인한다. **소스 기준점은 `8bca12fa...`** 이다.

## 3. Last successful build / current test build

### Latest successful CI

- Workflow: `Cemu ARM64 Diagnostic Edition`
- Run: `#24`
- Run ID: `33017387410`
- Head SHA: `8bca12fa5119f12b34b73ba5482d2ffeea89f5a8`
- Result: **SUCCESS**
- Artifact: `cemu-arm64-diagnostic-edition`
- Artifact ID: `9626115561`
- Artifact digest: `sha256:9540922b3f7b0155148f6eadcf7469e4d1e4d58e9591bee53cbdb05429f040f3`

### Runtime state

- 위 diagnostic build는 실행되어 **ARM64 Diagnostics UI가 열리는 것까지 확인**됨.
- 이 탭에서는 게임별 전체 runtime A/B를 새로 수행하지 않음.
- 과거 gameplay 정상 기준: VS DEFAULT_VAL synthesize 적용 후 Adreno X1-85에서 BOTW/TTT2 렌더 정상 확인.

## 4. Current Diagnostics UI state

Reference screenshot: `스크린샷 2026-08-27 073356.png` (conversation attachment; repository file 아님)

- `Diagnostics master`: **OFF / unchecked**
- `Preset`: **Custom**
- `Hitch threshold (ms)`: **50**
- 화면에 보이는 모든 개별 checkbox: **unchecked**

### Enabled/selectable but currently OFF

Left column:

- JIT block lifecycle
- Branch patching
- JIT execution entry
- Guest memory access
- Queue submit
- Pipeline creation
- Pipeline state snapshot
- VS diagnostics
- GS diagnostics
- Pipeline barriers
- WAW dependency
- Render-pass split

Right column:

- Guest/host JIT mapping
- readonly / I-cache
- ARM64 exception context
- Pipeline cache
- Pipeline failure
- Shader hash association
- PS diagnostics
- Shader auxHash
- Render-pass begin/end
- RAW dependency
- Self dependency
- Synchronization summary

### Grey / disabled in current UI

Left column:

- Semaphore flow
- Device-lost / submit errors
- Pipeline-cache mismatch
- Shader interface
- SPIR-V compile failure
- Dump every shader
- FBO changes
- Load/store behavior
- Feedback-loop support

Right column:

- Command-buffer lifecycle
- Fence lifecycle
- Submit completion
- Shader creation
- GLSL compile failure
- Dump failed shader
- Attachment usage
- Render-target aliasing
- Feedback-loop use

**Interpretation rule:** grey means “원인 배제”가 아니다. UI 항목은 존재하지만 backend/probe가 미연결이거나 현재 build 조건에서 지원되지 않는 상태로 취급한다.

## 5. Confirmed facts

- Windows ARM64 build toolchain 자체는 현재 동작한다.
- Run #24가 성공했으므로 현재 source checkpoint `8bca12fa...`는 CI compile 가능하다.
- 과거 compile regression은 Configure가 아니라 `Build Cemu` 단계에서 발생했으며 현재 checkpoint에서는 해결됨.
- VS DEFAULT_VAL synthesize는 Adreno shader key 문제 해결에 효과가 있었고 확정 기반 수정이다.
- Wii U decrypt는 ARM64에서 동작 확인됨.
- Diagnostics UI의 회색 항목은 현재 선택할 수 없다.

## 6. Ruled out / do not repeat blindly

- “ARM64라서 CMake/vcpkg 자체가 근본적으로 빌드 불가” 가설은 현재 Run #24 성공으로 배제.
- 과거의 `33006509619` 같은 다른 프로젝트/Eden 계열 Run ID를 Cemu Run으로 재사용하지 말 것.
- VS DEFAULT_VAL synthesize를 제거하여 원점 회귀하는 실험 금지.
- 빌드 실패 원인을 확인하지 않고 다음 진단 기능을 계속 누적하는 방식 금지.

## 7. Live hypotheses

1. 회색 항목 중 일부는 UI 정의만 있고 실제 backend probe/flag 연결이 빠져 있다.
2. 일부는 platform/build feature guard 때문에 Windows ARM64에서 의도치 않게 disable 되어 있을 수 있다.
3. Vulkan 멈춤/강종의 핵심을 잡으려면 submit/synchronization/lifetime 계열의 미연결 진단이 특히 중요할 가능성이 높다.
4. Command buffer / fence / semaphore / submit completion / device-lost 로그를 동시에 무조건 켜기보다 각각 독립 toggle로 연결해야 A/B가 가능하다.

## 8. Files changed in this handoff tab

Source code: **변경 없음**

Documentation added at repository root:

- `TECH_BIBLE.md`
- `DEBUG_HISTORY.md`
- `CURRENT_HANDOFF.md`

## 9. Latest log / dump references

- 이 handoff 작성 탭에서 새 게임 runtime log/dump는 제공되지 않음.
- 최신 UI 상태 근거: `스크린샷 2026-08-27 073356.png`
- 새 로그/덤프가 들어오면 파일명을 이 섹션에 즉시 추가한다.

# NEXT ACTION

1. GitHub에서 `runtime-experiments-arm64`의 실제 HEAD를 확인한다.
2. `8bca12fa...` 이후가 문서-only commit인지 검증한다.
3. ARM64 Diagnostics UI를 구현한 파일과 backend diagnostic flag/probe 정의를 찾는다.
4. 위 **grey/disabled 18개 항목 각각**에 대해 다음 중 어느 상태인지 표로 만든다.
   - backend 구현 있음 + UI 연결 누락
   - backend 일부 구현
   - 완전 미구현
   - platform/feature guard 때문에 disabled
5. 첫 구현 대상은 submit/lifetime 그룹으로 한다:
   - Command-buffer lifecycle
   - Fence lifecycle
   - Semaphore flow
   - Submit completion
   - Device-lost / submit errors
6. 한 번에 한 그룹만 연결하고 정적 검증한다.
7. 정적 검증 통과 후에만 CI를 실행한다.
8. 새로 확인한 사실/실험 결과는 `DEBUG_HISTORY.md`에 누적하고 이 파일을 다시 최신화한다.

## DO NOT ROLLBACK

- VS DEFAULT_VAL synthesize 기반 수정
- 현재 정상 CI checkpoint `8bca12fa...`의 코드 상태를 근거 없이 되돌리는 작업
- UI에서 각 실험을 독립적으로 제어해야 한다는 원칙

## New-tab startup prompt

`Cemu ARM64 디버그 작업 계속. GitHub의 TECH_BIBLE.md, DEBUG_HISTORY.md, CURRENT_HANDOFF.md를 읽고 실제 브랜치/HEAD까지 확인한 뒤, CURRENT_HANDOFF.md의 NEXT ACTION부터 바로 실행해. 이전 대화 추측 금지, 이미 배제된 실험 반복 금지, 완료 후 문서 갱신.`
