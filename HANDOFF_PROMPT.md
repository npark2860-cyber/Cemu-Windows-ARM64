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

## 직전 P1 — ARM64 R_NAME GPR LDP

Experiment:
`arm64-rname-ldp`

Implementation:
`f929fa8007d6ef17f90a3c166b5d248d2ee30e3d`

Compile repair:
`fc330d1c7c29e68042208337ac6e46eb21c69421`

Validated CI:
- run `34591462835`
- SUCCESS
- artifact `cemu-arm64-test`
- artifact ID `10262500252`

실제 P1은 GPR `R0..R31`의 인접 uint32 state loads를 `LDP Wreg,Wreg`로 묶는 실험이다. 예전 handoff의 non-GPR 64-bit/+8/LR+CTR/XER+temporaryFPR 설명은 문서 오류이므로 사용하지 않는다.

## P1 VERIFY — PASS

`0x0420CB80` enterable state-restore segment에서 6 pair가 형성됨:
- r3+r4
- r5+r6
- r24+r25
- r26+r27
- r28+r29
- r30+r31

결과:
- `pairs=6`
- `native_bytes_saved=24`
- unrelated lowering 유지
- final JUMP 유지
- BOTW stable-gameplay smoke PASS

즉 codegen reduction 자체는 실제다.

## P1 PERFORMANCE — CLOSED / NON-WINNING

Primary window:
`t=70..260s`

Pair 1 — BASELINE -> CANDIDATE:
- `49.66745 -> 50.76435 FPS`
- candidate **+2.2085%**

Pair 2 — CANDIDATE -> BASELINE:
- candidate `48.12405 FPS`
- baseline `49.90825 FPS`
- candidate **-3.5750%**

두 order를 합친 condition mean:
- BASELINE `49.78785 FPS`
- CANDIDATE `49.44420 FPS`
- candidate **-0.6902%**

실행 순서 mean:
- 각 pair 첫 run `48.89575 FPS`
- 각 pair 두 번째 run `50.33630 FPS`
- 두 번째 run advantage 약 **+2.9462%**

판정:
- static/correctness PASS
- code-size reduction REAL
- repeatable FPS gain NOT CONFIRMED
- **DO NOT PROMOTE**
- `arm64-compare-reuse`와 결합 금지
- 새 근거/개선된 벤치마크 방식 없이는 P1 추가 재실험하지 않는다

## BENCHMARK 교훈

이 장비/장면에서 small effect는 run-order bias에 쉽게 묻힌다.

앞으로 sub-3% 후보는:
- 한 번의 BASELINE->CANDIDATE만으로 positive 판정 금지
- sacrificial preconditioning 후 AB/BA 또는 ABBA 권장
- 최소한 양방향 order를 모두 검증
- `t=70..260s` primary window는 유지

기존 `arm64-compare-reuse` +1.68%도 one-order 결과이므로 promotion 전 order-balanced 재검증이 필요하다.

## 지금 바로 할 일 — `0x02A281A0`

P1은 성능 방향으로 종료했다. 다음은 guest hotspot `0x02A281A0` 분석이다.

기존 native entry:
`17ffff66 d503201f`

첫 instruction은 branch/thunk-like 이므로 뒤 raw words를 straight-line body로 해석하지 않는다.

다음 순서:
1. 실제 Test branch HEAD/source 확인
2. 기존 report-only branch-target diagnostic 확인
3. 첫 AArch64 `B imm26` decode/follow
4. 실제 target에서 128 bytes 이상 dump
5. guest block/IML과 correlation
6. concrete redundant pattern이 증명될 때만 single-variable runtime-gated experiment 설계

분석 전 behavior-changing code를 쓰지 않는다.
