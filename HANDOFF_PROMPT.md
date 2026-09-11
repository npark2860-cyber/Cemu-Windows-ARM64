# HANDOFF PROMPT — Cemu Windows ARM64 performance/JIT work

Cemu Windows ARM64 / Adreno 성능 최적화 작업을 이어간다.

GitHub 저장소:
`npark2860-cyber/Cemu-Windows-ARM64`

작업 branch:
`runtime-experiments-arm64`

GitHub를 source of truth로 사용하고 이전 대화를 추측해서 복원하지 않는다.

시작 시 반드시 실제 branch HEAD와 다음을 대조한다.
- `CURRENT_HANDOFF.md`
- `NEXT_ACTION.md`
- `HANDOFF_PROMPT.md`
- `DEBUG_HISTORY_20260911_ARM64_JIT_PERF.md`
- `PERFORMANCE_OPTIMIZATION_PLAN.md`
- `.github/workflows/runtime-experiments-arm64.yml`

`main`은 건드리지 않는다. Release/Diagnostics도 이번 단계에서는 수정하지 않는다.

## 직전 P1 — CLOSED

`arm64-rname-ldp`는 정적/codegen 검증은 PASS지만 성능 최적화로는 종료했다.

- six GPR pair loads verified
- `native_bytes_saved=24`
- BOTW correctness smoke PASS
- two-order condition mean: candidate 약 `-0.69%`
- 강한 second-run bias 약 `+2.95%` 확인
- DO NOT PROMOTE
- DO NOT COMBINE with `arm64-compare-reuse`

앞으로 sub-3% 후보는 한 방향 A/B만으로 positive 판정하지 말고 order-balanced 검증한다.

## 현재 타깃 — `0x02A281A0`

RUNNING-only profile share:
- 약 `4.12%`

기존 mapped native entry:

```text
17ffff66 d503201f
```

`0x17ffff66` 정적 decode:
- AArch64 `B imm26`
- signed imm26 = `-154`
- byte offset = `-616` = `-0x268`
- actual target = `nativeEntry - 0x268`

따라서 original entry 뒤쪽 raw words는 straight-line body로 해석하지 않는다.

## 기존 diagnostic — 이미 준비됨

`tools/diagnostics/Apply-ARM64JitRootCause.py`에 `0x02A281A0` 전용 branch-target follow가 이미 있다.

이 코드는 validated artifact build commit `fc330d1...`에도 존재한다.

기능:
- first `B imm26` 확인
- signed offset 계산
- actual branch target 기록
- target에서 128 bytes dump

기존 launcher:
- `JIT_HOTSPOT_NATIVE.cmd`
- `CEMU_EXPERIMENTS=jit-hotspot-native,perf-log`

validated artifact `10262500252` 그대로 사용 가능하다. 새 build 필요 없다.

## 지금 바로 할 일

사용자가 existing artifact에서:
1. `JIT_HOTSPOT_NATIVE.cmd` 실행
2. 같은 BOTW scene 로드
3. `Debug > View PPC threads`
4. `0E001800 / Default Core 1` 약 60초 profile
5. profiler 출력 후 Cemu 종료
6. 생성 log 업로드

필수로 확인할 log:
- `JIT_HOTSPOT_MAP` for `0x02A281A0`
- `JIT_HOTSPOT_CODE`
- `JIT_HOTSPOT_BRANCH` with `imm26=-154`, `byte_off=-616`
- `JIT_HOTSPOT_TARGET` 128-byte dump

로그를 받으면:
1. actual target body decode
2. guest/IML correlation
3. compare/load/state movement/branch glue/ABI mechanics/required semantics 분류
4. concrete redundant pattern이 증명될 때만 one-variable runtime-gated experiment 설계

로그 전에는 behavior-changing patch를 쓰지 않는다.
