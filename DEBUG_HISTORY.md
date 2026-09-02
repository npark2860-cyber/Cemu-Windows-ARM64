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

## 2026-08-27 — Diagnostic build recovered

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

직전의 CI compile regression은 이 source checkpoint에서는 해결되어 진단판 포함 Windows ARM64 빌드가 다시 성공했다.

---

## 2026-08-28 ~ 2026-08-29 — Bayonetta 2 / XCX query-consumption comparison

### Goal

Bayonetta 2의 zero occlusion-result가 query 생산/완료 단계의 문제인지, 소비 방식의 차이인지 XCX와 비교한다.

### Confirmed runtime facts

**Bayonetta 2**

- CPU occlusion query `type=0` 경로 사용.
- completed `GET_READY_ZERO`가 대량 존재.
- 현재 캡처에서 snapshot 누락/미소비 slot overwrite로 zero를 설명할 근거가 없었다.
- 따라서 관찰된 ready-zero는 실제 완료·소비된 query 결과로 취급한다.

**Xenoblade Chronicles X**

- GPU occlusion query `type=2` 경로 사용.
- 캡처에서 exported `GX2QueryGetOcclusionResult()` 소비는 관찰되지 않았다.

### Conclusion

- Bayo2와 XCX를 동일한 query-consumption 경로로 가정하는 비교는 금지.
- Bayo2의 zero를 단순히 "query가 아직 준비되지 않음" 또는 "snapshot overwrite"로 되돌려 설명하는 가설은 현재 캡처와 맞지 않는다.

---

## 2026-08-29 — Bayo2 target transition downstream trace

### Goal

Bayo2 targeted query가 `0 -> nonzero` 또는 `nonzero -> 0`으로 바뀐 직후 실제 draw stream이 어떻게 달라지는지 observation-only로 좁힌다.

### Implementation

- query transition 발생 시 short watch를 arm.
- 정확히 다음 3 command-stream frame의 draw fingerprint를 기록.
- renderer state/query result/draw command는 변경하지 않음.

### Verified build checkpoint

- Commit: `b1694fc46ba56de381fd5e9e6ec37bbb93ec3f48`
- Message: `diagnostics: chain Bayo2 downstream trace`
- Workflow run: `#7`
- Run ID: `33247256523`
- Result: **SUCCESS**

### Meaning

downstream transition trace 자체는 Windows ARM64에서 compile 가능한 정상 checkpoint다.

---

## 2026-08-30 — Bayo2 target0 resource identity/content trace

### Goal

반복 관찰된 target0 query `0x46a92ec8`의 downstream pipeline family에서 draw argument만이 아니라 guest resource identity/content가 transition에 따라 달라지는지 기록한다.

### Added observation data

`[BAYO2_RESOURCE] DRAW`에서 다음을 기록하도록 chain했다.

- vertex-buffer count / identity hash / sampled content hash
- VS/PS/GS uniform-buffer identity/content hash
- VS/PS/GS uniform-variable size/content hash
- target0 transition/watch/frame/draw correlation

고정 filter:

- query: `0x46a92ec8`
- pipeline stateHash: `0x4addb8b25c8fc2bf`
- VS baseHash: `0xdba0c5a2b50b7103`
- PS baseHash: `0x2360006f2b86aae5`

### Initial chained checkpoint

- Commit: `725aae2f63d6b3e766c37efe26c46341059dae83`
- Message: `diagnostics: chain Bayo2 target0 resource trace`
- Workflow run: `#8`
- Run ID: `33286935862`
- Result: **FAILURE**
- All trace transform/static verification steps succeeded.
- Failure occurred at `Build Cemu once`.

### Static root-cause inspection

새 resource helper가 `const uint32* ctx`를 `LatteParsedFetchShaderBufferGroup_t::getCurrentBufferStride(uint32*)`에 전달하고 있었다. 기존 API 시그니처와 맞지 않는 compile incompatibility를 확인했다.

### Vertex-buffer interpretation caveat

현재 `vbIdentity` / `vbContent`는 **guest-declared vertex resource fingerprint**다. Vulkan renderer는 실제 GPU-visible vertex-buffer 범위를 게임이 준 size만으로 정하지 않고 max index / stride / attribute max offset 등을 이용해 `fixedBufferSize`를 재계산한다.

따라서 `vbContent`를 Vulkan에 실제 bind/upload된 정확한 전체 byte-range hash라고 해석하지 않는다. 다만 query transition 방향 사이의 guest resource identity/content 변화 비교에는 사용할 수 있다.

---

## 2026-08-31 — target0 resource trace constness fix

### Change

`tools/diagnostics/Apply-Bayo2Target0ResourceIdentityTrace.py`에서 필요한 두 포인터만 `uint32*`로 수정했다.

- vertex-buffer summary helper의 `ctx`
- `LatteGPUState.contextNew.GetRawView()`를 받는 caller local `ctx`

query/render behavior 변경 없음.

### Code checkpoint

- Commit: `143d5631f48a3384c19e7366c39d9a1afb43ca5b`
- Message: `diagnostics: fix target0 resource trace constness`
- Parent: `725aae2f63d6b3e766c37efe26c46341059dae83`
- Diff scope: resource trace script only

### CI validation — Run #9

- Workflow: `Cemu ARM64 Bayo2 Target Query Draw Fingerprint Trace`
- Run number: `#9`
- Run ID: `33349115978`
- Head: `143d5631f48a3384c19e7366c39d9a1afb43ca5b`
- Result: **FAILURE**
- `Configure`: **SUCCESS**
- `Build Cemu once`: **FAILURE**
- Artifact: 없음

### Exact first compiler failure

Job log에서 최초 C++ 오류를 직접 확인했다.

```text
VulkanRendererCore.cpp(293,1): error: expected expression
293 | \thash ^= value + 0x9e3779b97f4a7c15ULL + (hash << 6) + (hash >> 2);
```

이후 `\tif`, `\tuint64`, struct member declaration 등 동일 literal `\t`가 들어간 줄에서 연쇄 parser error가 발생했다.

### Confirmed root cause

resource helper template가 다음처럼 Python raw string이었다.

```python
resource_helpers = r'''...'''
```

따라서 template 내부의 `\t`가 실제 tab으로 escape되지 않고 생성 C++에 문자 backslash+t로 삽입됐다. 이는 type/namespace/linkage 문제가 아니었다.

### Minimum fix

CI branch:

- Commit: `6b96fb4a0fceb6f1285ea6a39db82852d4ad8972`
- Message: `diagnostics: fix target0 resource trace indentation escapes`
- Diff: 정확히 1줄

```text
-resource_helpers = r'''...
+resource_helpers = '''...
```

Handoff branch에도 동일 source blob으로 반영:

- Commit: `80d94fff50fa764c2d7bf3be59e3ffaa5d3c9ba1`
- Script blob: `6f9e41911bf64b51eda0df94a1f3b8b3407fe0d6`

새 instrumentation이나 query/render behavior 변경은 없다.

### Current validation at that documentation point

- Workflow run: `#10`
- Run ID: `33369558184`
- CI head: `6b96fb4a0fceb6f1285ea6a39db82852d4ad8972`
- State at that documentation update: **IN PROGRESS**

---

## 2026-09-01 — target0 resource trace build validated

### Run #10 final result

- Workflow: `Cemu ARM64 Bayo2 Target Query Draw Fingerprint Trace`
- Run number: `#10`
- Run ID: `33369558184`
- Head: `6b96fb4a0fceb6f1285ea6a39db82852d4ad8972`
- Result: **SUCCESS**

따라서 Run #9의 literal indentation compile failure는 `6b96fb4...`에서 해결됐고, target0 resource identity/content observation trace가 Windows ARM64에서 정상 compile되는 것이 검증됐다.

### Runtime artifact

- Name: `cemu-arm64-bayo2-target-query-draw-fingerprint`
- Artifact ID: `9750570882`
- Size: `11,979,643` bytes
- SHA-256 digest: `9951398732e1185d0874c2d530e14b91829922d05791aae52498deeddd052127`
- Created: `2026-08-31T08:20:41Z`
- Expires: `2026-11-29T07:42:28Z`

이 artifact가 다음 Bayonetta 2 runtime capture의 기준 빌드다.

### Redundant Run #11 provenance

현재 CI branch에는 Run #10 성공 여부를 재확인하기 전에 추가된 redundant normalization commit이 하나 더 있다.

- Commit: `4f24fca6e0cc49d64bd14bca0b5ce1e586d2b59f`
- Message: `diagnostics: normalize target0 resource trace indentation`
- Parent: `6b96fb4a0fceb6f1285ea6a39db82852d4ad8972`
- Diff: `resource_helpers = resource_helpers.replace(chr(92) + "t", chr(9))` 한 줄 추가
- Run: `#11`
- Run ID: `33467898875`
- Last checked state: **IN PROGRESS**

Run #10이 이미 성공했으므로 Run #11은 runtime 검증에 필요하지 않다. 추가 CI는 실행하지 않는다. 검증된 build checkpoint는 계속 `6b96fb4...` / Run #10으로 고정한다.

### Next runtime question

Run #10 artifact로 Bayonetta 2를 실행해 target0 `0 -> NZ`와 `NZ -> 0` transition을 모두 포함한 로그를 캡처한 뒤 `[BAYO2_RESOURCE] DRAW`를 비교한다.

- `vbIdentity` / `vbContent`
- `vsCbIdentity` / `vsCbContent` / `vsVarHash`
- `psCbIdentity` / `psCbContent` / `psVarHash`
- `gsCbIdentity` / `gsCbContent` / `gsVarHash`

이 runtime evidence 전에는 새 instrumentation layer나 behavior workaround를 추가하지 않는다.

---

## 2026-09-02 — Run #11 final status and supplied runtime-log check

### Run #11 final result

- Workflow: `Cemu ARM64 Bayo2 Target Query Draw Fingerprint Trace`
- Run number: `#11`
- Run ID: `33467898875`
- Head: `4f24fca6e0cc49d64bd14bca0b5ce1e586d2b59f`
- Result: **SUCCESS**

`4f24fca...`는 literal indentation을 defensive하게 다시 정규화한 build-only commit이며 query/render behavior는 바꾸지 않는다. Run #10이 이미 최초 성공 checkpoint이므로 추가 compile-validation CI는 실행하지 않는다.

### Run #11 artifact

- Name: `cemu-arm64-bayo2-target-query-draw-fingerprint`
- Artifact ID: `9786258817`
- Size: `11,979,654` bytes
- SHA-256 digest: `35770f76d30e17ebe2845e1debbbd115846bebd8e145f2858f35538a64de8936`
- Created: `2026-09-01T04:32:41Z`
- Expires: `2026-11-30T03:54:28Z`

Runtime 기준 checkpoint는 계속 `6b96fb4...` / Run #10으로 유지한다.

### Supplied `log(2).zip`

사용자가 제공한 runtime `log.txt`에는 `[BAYO2_QUERY_CORR]` 기록은 다수 존재하지만 `[BAYO2_RESOURCE]` 기록은 관찰되지 않았다.

따라서 이 로그만으로는 target0 transition의 VB/CB/uniform resource fingerprint 비교를 수행할 수 없다. 이 사실만으로 resource trace 자체 실패를 의미하지 않으며, Run #10 target0-resource artifact로 다시 캡처해야 한다.

### Next action

Run #10 artifact에서 target0 `0 -> NZ`와 `NZ -> 0`을 모두 포함한 로그를 새로 캡처하고, `[BAYO2_RESOURCE] DRAW` marker 존재를 먼저 확인한 뒤 resource fingerprint를 비교한다. runtime evidence 전에는 새 instrumentation이나 behavior workaround를 추가하지 않는다.

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