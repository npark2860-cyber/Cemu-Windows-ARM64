# HANDOFF PROMPT — Cemu Windows ARM64 performance/JIT work

Cemu Windows ARM64 / Adreno 성능 최적화 작업을 이어간다.

GitHub 저장소:
`npark2860-cyber/Cemu-Windows-ARM64`

작업 branch:
`runtime-experiments-arm64`

GitHub를 source of truth로 사용하고 이전 대화를 추측해서 복원하지 않는다.

시작 시 반드시 실제 branch HEAD와 다음 문서를 서로 대조한다.

- `CURRENT_HANDOFF.md`
- `NEXT_ACTION.md`
- `HANDOFF_PROMPT.md`
- `DEBUG_HISTORY_20260911_ARM64_JIT_PERF.md`
- `PERFORMANCE_OPTIMIZATION_PLAN.md`
- `.github/workflows/runtime-experiments-arm64.yml`

`main`은 건드리지 않는다. Release/Diagnostics도 이번 단계에서는 수정하지 않는다.

## 기준점

마지막 검증 성공 non-documentation code checkpoint:
`04b5626c77503aceed1fb712e45563bf620262fc`

- CI run `34558962681`
- SUCCESS
- artifact `cemu-arm64-test`
- artifact ID `10184443139`

현재 P1 behavior-changing code commit:
`f929fa8007d6ef17f90a3c166b5d248d2ee30e3d`

- message: `jit: pair adjacent ARM64 state loads`
- experiment: `arm64-rname-ldp`
- changed source: `src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp`

인수인계 문서 커밋으로 실제 branch HEAD는 위 코드 커밋보다 앞서 있을 수 있으므로 시작 즉시 실제 HEAD를 다시 조회한다.

## 현재 막힌 지점 — BUILD FAILURE

`f929fa8...` 대상 Test CI가 실패했다.

- workflow: `ARM64 Windows Test Build`
- run ID: `34576700718`
- job ID: `103190682420`
- result: FAILURE
- failed step: `Build Cemu`
- checkout/configure/vcpkg는 성공
- artifact 없음

현재 connector에서는 job log 다운로드가 정상 decode되지 않아 **정확한 compiler error line은 아직 확보하지 못했다.**

따라서 다음 작업의 첫 단계는 소스 추측이 아니라:
1. 실패 run/job의 실제 compiler diagnostic을 확보하거나 동일 빌드를 로컬 재현한다.
2. 그 에러가 `arm64-rname-ldp` 변경 때문인지 확정한다.
3. P1 변경 때문이면 해당 컴파일 문제만 최소 수정한다.
4. 최적화 범위를 넓히지 않는다.
5. Test CI를 다시 통과시킨다.

CI가 green이 되기 전에는 BOTW A/B, 새 최적화, candidate 조합, Release promote를 하지 않는다.

## P1의 근거

P0 분석은 `0x0420CB80`에서 다음을 확정했다.

- pre/post RA IML에서 non-GPR `R_NAME` state loads가 남는다.
- `PPCInterpreter_t`의 인접한 64-bit field pair가 각각 `LDR`로 내려간다.
- 예:
  - `SPR::LR + SPR::CTR`: offsets 328 / 336
  - `SPR::XER + temporaryFPR`: offsets 512 / 520
- native examples:
  - `F940A546  ldr x6, [x10,#328]`
  - `F940A942  ldr x2, [x10,#336]`
  - `F9410146  ldr x6, [x10,#512]`
  - `F9410542  ldr x2, [x10,#520]`
- guest memory semantics가 아니라 emulator state load다.
- RA가 merge/remove하지 않으며 AArch64 lowering이 개별 `LDR`를 낸다.

그래서 `arm64-rname-ldp`는 다음 경우만 인접 load 둘을 `LDP`로 묶는 단일 변수 실험이다.

- consecutive `ImlOperation::R_NAME`
- both non-GPR
- distinct destination registers
- second offset = first offset + 8
- legal/aligned positive scaled LDP immediate
- 나머지는 기존 lowering으로 fallback

## 빌드 복구 후 검증 순서

1. native dump에서 실제 target pair가 `LDP`가 되었는지 확인
2. branch/control flow와 unrelated lowering이 바뀌지 않았는지 확인
3. GPR special-load behavior와 protected paths가 그대로인지 확인
4. 같은 빌드에서 BASELINE vs `arm64-rname-ldp` BOTW A/B
5. `t=70..260s`, avg FPS/frame time/p99/1% low 비교
6. repeatable positive + correctness OK일 때만 candidate로 보존하고 reprofile
7. neutral/negative/unstable/correctness regression이면 reject

`arm64-compare-reuse`는 약 +1.68%의 별도 positive candidate지만 아직 FIX가 아니며 이번 `arm64-rname-ldp` 측정에 섞지 않는다.

현재 실험이 validate/reject되기 전에는 `0x02A281A0` 등 다음 hotspot 작업으로 넘어가지 않는다.

이미 종료/비승리 판정한 timer, Vulkan barrier/render-pass, NEON texture hash, historical compare/branch fusion/direct-dispatch 실험은 새 근거 없이 반복하지 않는다.
