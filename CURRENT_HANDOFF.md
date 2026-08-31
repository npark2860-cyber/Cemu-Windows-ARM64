# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 이 파일은 **현재 상태만** 유지한다. 완료된 실험은 `DEBUG_HISTORY.md`로 이동한다. 새 탭은 실제 GitHub 상태와 이 문서를 대조한 뒤 `NEXT ACTION`부터 시작한다.

## 1. Current goal

Bayonetta 2의 CPU occlusion query `type=0`에서 실제 완료·소비된 zero/nonzero 결과가 바뀔 때, **target0 query `0x46a92ec8` 직후의 동일 downstream pipeline family에서 guest resource identity/content가 달라지는지** 확인한다.

현재 단계는 behavior fix가 아니라 **observation-only resource correlation**이다.

## 2. Repository state

- Repository: `npark2860-cyber/Cemu-Windows-ARM64`
- Handoff branch: `diag-bayo2-target0-resource-identity`
- Last code-changing checkpoint: `143d5631f48a3384c19e7366c39d9a1afb43ca5b`
- Code commit: `diagnostics: fix target0 resource trace constness`
- CI build branch: `diag-bayo2-target-query-draw-fingerprint`
- CI build branch code HEAD: `143d5631f48a3384c19e7366c39d9a1afb43ca5b`

`diag-bayo2-target0-resource-identity`는 `143d5631...`까지 fast-forward한 뒤 문서 전용 commit이 추가되어 있다. 따라서 **실험 코드 기준점은 `143d5631...`** 이며, 실제 branch HEAD는 시작 시 다시 확인한다.

`main`에는 이 실험 변경을 넣지 않는다.

## 3. Build checkpoints

### Last successful downstream build

- Commit: `b1694fc46ba56de381fd5e9e6ec37bbb93ec3f48`
- Message: `diagnostics: chain Bayo2 downstream trace`
- Workflow: `Cemu ARM64 Bayo2 Target Query Draw Fingerprint Trace`
- Run: `#7`
- Run ID: `33247256523`
- Result: **SUCCESS**

이 checkpoint로 target-transition downstream trace 자체는 compile 가능하다고 확정한다.

### First target0 resource build

- Commit: `725aae2f63d6b3e766c37efe26c46341059dae83`
- Run: `#8`
- Run ID: `33286935862`
- Result: **FAILURE**
- trace apply/static verification은 통과.
- `Build Cemu once`에서 실패.

정적 대조에서 resource helper의 `const uint32*`가 기존 `getCurrentBufferStride(uint32*)` API와 맞지 않는 compile incompatibility를 확인했다.

### Current validation build

- Commit: `143d5631f48a3384c19e7366c39d9a1afb43ca5b`
- Run: `#9`
- Run ID: `33349115978`
- Current state at this handoff update: **IN PROGRESS**
- 성공한 단계:
  - known-good base patches 적용
  - query-consumption trace validate/apply/observation-only verify
  - frame/draw correlation trace validate/apply/verify
  - targeted fingerprint + target0 resource trace validate/apply/verify
  - ARM64 toolchain setup
- 현재 확인된 진행 지점: `Configure`

현재 build conclusion과 artifact는 아직 확정하지 않는다.

## 4. Confirmed runtime facts that must be preserved

### Bayonetta 2

- CPU occlusion query `type=0` 사용.
- completed `GET_READY_ZERO`가 대량 존재.
- 현재 캡처에서는 zero를 missing snapshot 또는 overwritten-unconsumed slot으로 설명할 근거가 없다.
- 따라서 현재 관찰된 ready-zero는 실제 완료·소비된 query 결과로 취급한다.

### Xenoblade Chronicles X

- GPU occlusion query `type=2` 사용.
- 캡처에서 exported `GX2QueryGetOcclusionResult()` 소비는 관찰되지 않았다.

### Comparison rule

- Bayo2와 XCX의 query-consumption 경로를 동일하다고 가정하지 않는다.
- XCX의 소비 모델을 Bayo2에 그대로 대입하지 않는다.

## 5. Current observation chain

현재 code checkpoint는 다음 observation-only chain을 포함한다.

- `[BAYO2_QUERY_CORR]`
- `[BAYO2_TARGET]`
- `[BAYO2_DOWNSTREAM]`
- `[BAYO2_RESOURCE]`

Target transition watch:

- `0 -> nonzero`
- `nonzero -> 0`
- transition 직후 정확히 다음 3 frame을 관찰

Target0 resource filter:

- query: `0x46a92ec8`
- pipeline stateHash: `0x4addb8b25c8fc2bf`
- VS baseHash: `0xdba0c5a2b50b7103`
- PS baseHash: `0x2360006f2b86aae5`

`[BAYO2_RESOURCE] DRAW` 비교 필드:

- `vbCount`, `vbIdentity`, `vbContent`, first VB address/size/stride
- VS CB identity/content + uniform-var hash
- PS CB identity/content + uniform-var hash
- GS CB identity/content + uniform-var hash
- transition/watch/frame/draw correlation

## 6. Current code change

`tools/diagnostics/Apply-Bayo2Target0ResourceIdentityTrace.py`

`143d5631...`에서 수정한 것은 pointer constness 두 곳뿐이다.

- vertex-buffer summary helper `ctx`: `const uint32*` -> `uint32*`
- caller local `ctx`: `const uint32*` -> `uint32*`

query result, draw state, renderer behavior는 변경하지 않았다.

## 7. Ruled out / do not repeat

- Bayo2 ready-zero를 단순 NOT_READY로 취급하는 해석 반복 금지.
- missing snapshot / overwritten-unconsumed 가설을 현재 동일 캡처 조건에서 반복 금지.
- Bayo2와 XCX가 같은 exported consumption path를 사용한다고 가정 금지.
- 이미 성공한 `b1694fc...` downstream trace를 원인 확인 없이 되돌리지 말 것.
- build 실패 원인을 확인하지 않은 채 다음 instrumentation layer를 추가하지 말 것.

## 8. Live question

고정 pipeline family의 downstream draw에서 query transition 방향에 따라 다음 중 무엇이 달라지는가?

1. vertex-buffer identity만 달라지는가
2. vertex-buffer content만 달라지는가
3. VS/PS/GS uniform-buffer identity 또는 content가 달라지는가
4. uniform-variable data hash가 달라지는가
5. 위 resource fingerprint가 동일한데 query result만 달라지는가

이 질문에 runtime capture로 답하기 전에는 새로운 behavior workaround를 설계하지 않는다.

# NEXT ACTION

1. GitHub Actions Run `33349115978`의 최종 conclusion을 확인한다.
2. **실패 시**:
   - `Build Cemu once`의 최초 compile/link 오류만 확인한다.
   - `143d5631...` 이후 최소 수정만 적용한다.
   - 다른 진단 기능을 추가하지 않는다.
3. **성공 시**:
   - artifact 이름/ID/digest를 기록한다.
   - 해당 artifact를 Bayonetta 2에 실행한다.
   - target0 `0 -> NZ`와 `NZ -> 0` transition이 포함되도록 로그를 캡처한다.
4. `[BAYO2_RESOURCE] DRAW`를 transition 방향별로 묶어 다음을 비교한다.
   - `vbIdentity` / `vbContent`
   - `vsCbIdentity` / `vsCbContent` / `vsVarHash`
   - `psCbIdentity` / `psCbContent` / `psVarHash`
   - `gsCbIdentity` / `gsCbContent` / `gsVarHash`
5. 이 runtime 결과가 나오기 전에는 instrumentation layer를 추가하지 않는다.
6. 결과를 `DEBUG_HISTORY.md`에 누적하고 이 파일을 최신화한다.

## DO NOT ROLLBACK

- VS DEFAULT_VAL synthesize 기반 수정
- permanent PS DEFAULT_VAL linkage compatibility
- known-good pre-e834 runtime behavior
- AArch64 generated-code cache flush fix
- `b1694fc...`에서 compile 검증된 downstream transition trace
- observation-only 원칙

## New-tab startup prompt

`Cemu Windows ARM64 / Adreno 작업 계속. GitHub의 TECH_BIBLE.md, DEBUG_HISTORY.md, CURRENT_HANDOFF.md를 먼저 읽고 실제 branch/HEAD/Actions 상태와 대조해. 현재 code checkpoint는 CURRENT_HANDOFF의 값을 기준으로 확인하고 NEXT ACTION부터 실행해. Bayo2/ XCX query-consumption 차이를 유지하고 이미 배제된 실험을 반복하지 마. main은 건드리지 마.`
