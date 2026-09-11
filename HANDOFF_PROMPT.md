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

## 현재 P1 — ARM64 R_NAME GPR LDP

Experiment:
`arm64-rname-ldp`

Implementation commit:
`f929fa8007d6ef17f90a3c166b5d248d2ee30e3d`

실제 commit message:
`perf: add ARM64 R_NAME LDP experiment`

Build-time installer:
`tools/diagnostics/Apply-ARM64RNameLdp.py`

Compile-only repair:
`fc330d1c7c29e68042208337ac6e46eb21c69421`

- Python raw triple-quoted helper string 때문에 생성 C++에 literal `\t`가 들어간 문제만 수정
- 최적화 의미/범위는 변경하지 않음

검증 CI:
- run `34591462835`
- job `103237476096`
- SUCCESS
- artifact `cemu-arm64-test`
- artifact ID `10262500252`
- digest `sha256:7fb8e3f213818d4f0cc46067bd02ff6cd1fd4be37553564e9105a111f037d8fe`

## 반드시 기억할 정정 사항

빌드 실패 뒤 작성된 이전 handoff에는 P1을 다음처럼 잘못 설명한 부분이 있었다.
- non-GPR 64-bit R_NAME
- +8 byte adjacent fields
- LR+CTR / XER+temporaryFPR
- `F940...` native examples

이 설명은 실제 `f929fa8...` 구현과 맞지 않으며, pre-P1 `DEBUG_HISTORY`에도 그 상세 근거가 기록되어 있지 않다. 다시 source of truth로 사용하지 않는다.

실제 P1은 다음과 같다.
- `PPCREC_IML_TYPE_R_NAME`
- IML base format `I64`
- 이름은 `PPCREC_NAME_R0..R31`만
- contiguous `R_NAME` run 안에서 guest GPR n/n+1을 찾음
- 각 GPR이 run 안에 정확히 한 번 있고 목적 host register가 서로 다를 때만 pair
- `PPCInterpreter_t::gpr[]`는 `uint32[32]`
- 기존 개별 `ldr W...` 두 개 대신 `ldp W...,W...` 하나를 emit
- unmatched GPR과 non-GPR R_NAME은 기존 lowering 그대로

## VERIFY 결과 — PASS

성공 artifact에서 `ARM64_RNAME_LDP_VERIFY.cmd` 실행 로그 확인 완료.

Hot entry:
- `0x0420CB80`

Enterable post-RA state-restore segment:
- `ppc=0x00000000`
- `enter=0x0420CB80`

관찰된 pair:
- r3+r4
- r5+r6
- r24+r25
- r26+r27
- r28+r29
- r30+r31

Runtime diagnostic:
- `pairs=6`
- `native_bytes_saved=24`

여섯 partner IML은 추가 native bytes가 0으로 기록되어 pair emission과 정확히 일치한다. 마지막 JUMP도 유지된다. BOTW stable gameplay smoke도 통과했다.

VERIFY 실행의 초기 FPS 숫자는 성능 판정에 사용하지 않는다.

## 지금 바로 할 일

새 코드를 작성하거나 새 빌드를 만들지 않는다.

기존 성공 artifact로 첫 controlled A/B를 실행한다.

순서:
1. `ARM64_RNAME_LDP_BASELINE.cmd`
2. Cemu 종료
3. `ARM64_RNAME_LDP_CANDIDATE.cmd`

조건:
- 동일 save/location/camera
- 정지 scene
- 동일 graphics/FPS++ settings
- weather fixed
- 각 preset마다 Cemu 재시작
- 최소 `t=260s`까지 실행
- 비교 구간 `t=70..260s`
- `arm64-compare-reuse`는 섞지 않음

두 PERF log를 받아 avg FPS, avg frame time, p99, 1% low를 비교한다.

첫 pair가 의미 있게 positive면 역순으로 한 번 더 반복한 뒤 candidate 보존 여부를 판단한다. Neutral/negative면 benchmark invalidation 증거가 없는 한 P1을 reject한다.

`arm64-compare-reuse`는 별도의 약 +1.68% positive candidate이며 아직 FIX가 아니다.

P1이 validate/reject되기 전에는 `0x02A281A0` 등 다음 hotspot으로 넘어가지 않는다.
