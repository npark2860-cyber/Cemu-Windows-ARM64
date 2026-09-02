# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 이 파일은 **현재 상태만** 유지한다. 완료된 실험은 `DEBUG_HISTORY.md`로 이동한다. 새 탭은 실제 GitHub 상태와 이 문서를 대조한 뒤 `NEXT ACTION`부터 시작한다.

## 1. Current goal

Bayonetta 2의 CPU occlusion query `type=0`에서 실제 완료·소비된 zero/nonzero 결과가 바뀔 때, **target0 query `0x46a92ec8` 직후의 동일 downstream pipeline family에서 guest resource identity/content가 달라지는지** runtime capture로 확인한다.

현재 단계는 behavior fix가 아니라 **observation-only resource correlation**이다.

## 2. Repository state

- Repository: `npark2860-cyber/Cemu-Windows-ARM64`
- Handoff/docs branch: `diag-bayo2-target0-resource-identity`
- CI build branch: `diag-bayo2-target-query-draw-fingerprint`
- CI branch current HEAD: `4f24fca6e0cc49d64bd14bca0b5ce1e586d2b59f`
- CI branch first validated successful target0-resource checkpoint: `6b96fb4a0fceb6f1285ea6a39db82852d4ad8972`
- Handoff-branch equivalent validated code checkpoint: `80d94fff50fa764c2d7bf3be59e3ffaa5d3c9ba1`
- Validated resource trace script blob: `6f9e41911bf64b51eda0df94a1f3b8b3407fe0d6`

`4f24fca...`는 Run #10 성공 여부를 재확인하기 전에 추가된 redundant normalization commit이며 Run #11에서도 compile 성공이 확인됐다. behavior 차이는 없으므로 runtime 기준 빌드는 계속 **`6b96fb4...` / Run #10**으로 고정한다.

Handoff branch에는 문서 commit이 추가되므로 branch HEAD와 code checkpoint를 구분한다.

`main`에는 이 실험 변경을 넣지 않는다. 2026-09-02 재확인한 `main` HEAD는 `58954b34d147b134d7b23ee61b2057f49da2c014`이다.

## 3. Build checkpoints

### Last successful downstream-only build

- Commit: `b1694fc46ba56de381fd5e9e6ec37bbb93ec3f48`
- Run: `#7`
- Run ID: `33247256523`
- Result: **SUCCESS**

이 checkpoint로 target-transition downstream trace 자체는 compile 가능하다고 확정한다.

### Target0 resource trace failures

Run #8:

- Commit: `725aae2f63d6b3e766c37efe26c46341059dae83`
- Run ID: `33286935862`
- Result: **FAILURE**
- 정적 대조에서 `getCurrentBufferStride(uint32*)`에 `const uint32*`를 전달한 compile incompatibility 확인.
- `143d5631f48a3384c19e7366c39d9a1afb43ca5b`에서 최소 수정.

Run #9:

- Commit: `143d5631f48a3384c19e7366c39d9a1afb43ca5b`
- Run ID: `33349115978`
- Result: **FAILURE**
- `Configure`: **SUCCESS**
- `Build Cemu once`: **FAILURE**
- Artifact: 없음
- 최초 C++ 오류: `VulkanRendererCore.cpp(293,1): error: expected expression`
- 원인: resource helper template의 raw string 때문에 들여쓰기 `\t`가 literal backslash+t로 생성 C++에 삽입됨.

### Run #10 — validated target0 resource build

- Commit: `6b96fb4a0fceb6f1285ea6a39db82852d4ad8972`
- Message: `diagnostics: fix target0 resource trace indentation escapes`
- Run: `#10`
- Run ID: `33369558184`
- Result: **SUCCESS**

따라서 target0 resource identity/content trace는 Windows ARM64에서 정상 compile되는 것이 검증됐다.

Artifact:

- Name: `cemu-arm64-bayo2-target-query-draw-fingerprint`
- Artifact ID: `9750570882`
- Size: `11,979,643` bytes
- SHA-256: `9951398732e1185d0874c2d530e14b91829922d05791aae52498deeddd052127`
- Created: `2026-08-31T08:20:41Z`
- Expires: `2026-11-29T07:42:28Z`

**다음 runtime 테스트에는 이 Run #10 artifact를 기준으로 사용한다.**

### Run #11 — redundant normalization, final result confirmed

- Commit: `4f24fca6e0cc49d64bd14bca0b5ce1e586d2b59f`
- Message: `diagnostics: normalize target0 resource trace indentation`
- Parent: `6b96fb4a0fceb6f1285ea6a39db82852d4ad8972`
- Change: 생성 문자열의 남은 literal `\t`를 실제 tab으로 정규화하는 defensive build-only 처리
- Run: `#11`
- Run ID: `33467898875`
- Result: **SUCCESS**

Run #11 artifact:

- Name: `cemu-arm64-bayo2-target-query-draw-fingerprint`
- Artifact ID: `5552367848`
- Size: `24,598,681` bytes
- SHA-256: `b753fa631077337ffc3024888218fb153800621887908befd81663465e8e80dc`
- Created: `2026-09-02T01:52:28Z`
- Expires: `2026-12-01T01:52:20Z`

Run #10이 이미 최초 성공 checkpoint이고 Run #11은 redundant normalization뿐이므로 **추가 CI는 실행하지 않는다.**

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

검증된 Run #10 code checkpoint는 다음 observation-only chain을 포함한다.

- `[BAYO2_QUERY_CORR]`
- `[BAYO2_TARGET]`
- `[BAYO2_DOWNSTREAM]`
- `[BAYO2_RESOURCE]`

Target transition watch:

- `0 -> nonzero`
- `nonzero -> 0`
- transition 직후 정확히 다음 3 command-stream frame을 관찰

Target0 resource filter:

- query: `0x46a92ec8`
- pipeline stateHash: `0x4addb8b25c8fc2bf`
- VS baseHash: `0xdba0c5a2b50b7103`
- PS baseHash: `0x2360006f2b86aae5`

`[BAYO2_RESOURCE] DRAW` 비교 필드:

- `vbCount`, `vbIdentity`, `vbContent`, first VB address/size/stride
- `vsCbIdentity`, `vsCbContent`, `vsVarHash`
- `psCbIdentity`, `psCbContent`, `psVarHash`
- `gsCbIdentity`, `gsCbContent`, `gsVarHash`
- transition/watch/frame/draw correlation

### Vertex-buffer fingerprint interpretation

`vbIdentity` / `vbContent`는 **guest-declared vertex resource fingerprint**로 해석한다.

Cemu Vulkan renderer는 실제 GPU-visible vertex-buffer 범위에서 게임이 준 size를 그대로 신뢰하지 않고 max index / stride / attribute max offset 등을 이용해 `fixedBufferSize`를 다시 계산한다. 따라서 현재 trace의 `vbContent`를 "Vulkan에 실제 bind/upload된 정확한 전체 byte-range hash"라고 부르면 안 된다.

다만 query transition 방향 사이에서 guest resource identity/content가 바뀌는지 비교하는 용도에는 유효하다.

## 6. Confirmed build-only fixes in target0 resource trace

`tools/diagnostics/Apply-Bayo2Target0ResourceIdentityTrace.py`

최초 성공 checkpoint `6b96fb4...`까지의 build fix는 다음 세 가지다.

1. vertex-buffer summary helper `ctx`: `const uint32*` -> `uint32*`
2. caller local `ctx`: `const uint32*` -> `uint32*`
3. resource helper template: raw triple string -> normal triple string

Run #11의 `4f24fca...`는 3번의 효과를 defensive하게 정규화한 추가 build-only commit이다.

query result, draw state, renderer behavior는 변경하지 않았다.

## 7. Latest supplied runtime log status

사용자가 제공한 `log(2).zip`의 `log.txt`에는 `[BAYO2_QUERY_CORR]` 기록은 존재하지만 **`[BAYO2_RESOURCE]` 기록은 관찰되지 않았다.**

따라서 이 로그는 현재 live question인 target0 resource identity/content 비교에 사용할 수 없다. 이 사실만으로 resource trace 자체가 실패했다고 판단하지 않으며, 검증된 Run #10 target0-resource artifact로 다시 캡처해야 한다.

## 8. Ruled out / do not repeat

- Bayo2 ready-zero를 단순 NOT_READY로 취급하는 해석 반복 금지.
- missing snapshot / overwritten-unconsumed 가설을 현재 동일 캡처 조건에서 반복 금지.
- Bayo2와 XCX가 같은 exported consumption path를 사용한다고 가정 금지.
- 이미 성공한 `b1694fc...` downstream trace를 원인 확인 없이 되돌리지 말 것.
- Run #10/Run #11 성공 뒤 같은 compile validation을 다시 돌리기 위한 CI 실행 금지.
- runtime evidence 전에는 새 instrumentation layer를 추가하지 말 것.

## 9. Live question

고정 pipeline family의 downstream draw에서 query transition 방향에 따라 다음 중 무엇이 달라지는가?

1. vertex-buffer identity가 달라지는가
2. vertex-buffer content가 달라지는가
3. VS/PS/GS uniform-buffer identity 또는 content가 달라지는가
4. uniform-variable data hash가 달라지는가
5. 위 resource fingerprint가 동일한데 query result만 달라지는가

이 질문에 runtime capture로 답하기 전에는 새로운 behavior workaround를 설계하지 않는다.

# NEXT ACTION

1. **Run #10 artifact ID `9750570882`를 사용해 Bayonetta 2를 실행한다.**
2. 동일 재현 조건에서 target0 query `0x46a92ec8`의 `0 -> NZ`와 `NZ -> 0` transition이 모두 포함되도록 Cemu 로그를 캡처한다.
3. 새 로그에 `[BAYO2_RESOURCE] DRAW`가 실제 존재하는지 먼저 확인한다. 없으면 비교 분석으로 넘어가지 않는다.
4. marker가 존재하면 transition 방향별로 다음을 비교한다.
   - `vbIdentity` / `vbContent`
   - `vsCbIdentity` / `vsCbContent` / `vsVarHash`
   - `psCbIdentity` / `psCbContent` / `psVarHash`
   - `gsCbIdentity` / `gsCbContent` / `gsVarHash`
5. resource fingerprint 변화가 실제 flicker 방향/transition과 상관되는지 판정한다.
6. 이 runtime 결과 전에는 새 instrumentation, behavior workaround, 추가 CI를 하지 않는다.
7. runtime 결과를 `DEBUG_HISTORY.md`에 누적하고 이 파일을 다시 최신화한다.

## DO NOT ROLLBACK

- VS DEFAULT_VAL synthesize 기반 수정
- permanent PS DEFAULT_VAL linkage compatibility
- known-good pre-e834 runtime behavior
- AArch64 generated-code cache flush fix
- `b1694fc...`에서 compile 검증된 downstream transition trace
- Run #10에서 compile 검증된 target0 resource observation trace
- observation-only 원칙

## New-tab startup prompt

`Cemu Windows ARM64 / Adreno 작업 계속. GitHub의 TECH_BIBLE.md, DEBUG_HISTORY.md, CURRENT_HANDOFF.md를 먼저 읽고 실제 branch/HEAD/Actions 상태와 대조해. CURRENT_HANDOFF의 validated checkpoint와 NEXT ACTION부터 실행해. Bayo2/XCX query-consumption 차이를 유지하고 이미 배제된 실험을 반복하지 마. main은 건드리지 마.`