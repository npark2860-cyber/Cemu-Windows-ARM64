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

Compile-only repair:
`fc330d1c7c29e68042208337ac6e46eb21c69421`

검증 CI:
- run `34591462835`
- job `103237476096`
- SUCCESS
- artifact `cemu-arm64-test`
- artifact ID `10262500252`

실제 P1은 GPR `R0..R31`의 인접 uint32 state loads를 `LDP Wreg,Wreg`로 묶는 실험이다. 예전 handoff의 non-GPR 64-bit/+8/LR+CTR/XER+temporaryFPR 설명은 문서 오류이므로 사용하지 않는다.

## VERIFY — PASS

`0x0420CB80` enterable state-restore segment에서:
- `r3+r4`
- `r5+r6`
- `r24+r25`
- `r26+r27`
- `r28+r29`
- `r30+r31`

총 6 pair가 형성되었고:
- `pairs=6`
- `native_bytes_saved=24`

final JUMP와 unrelated lowering은 유지되고 BOTW stable-gameplay smoke도 통과했다.

## 첫 controlled A/B — POSITIVE

실행 순서:
1. BASELINE
2. CANDIDATE

비교 구간:
`t=70..260s`

결과:
- avg FPS: `49.66745 -> 50.76435` = **+2.2085%**
- avg frame time: `20.13760 -> 19.70055 ms` = **-2.1703%**
- mean p99: `22.25870 -> 21.52095 ms` = **-3.3144%**
- mean 1% low: `45.10415 -> 46.49985 FPS` = **+3.0944%**

추가 확인:
- candidate가 20개 aligned window 중 19개에서 FPS 우세
- baseline `t=250..260s` 급락을 제외해도 우세 유지
- `t=70..240s`: 약 **+1.7869% FPS**
- `t=70..230s`: 약 **+1.7369% FPS**

판정:
- 첫 pair는 명확한 positive direction
- `arm64-rname-ldp`는 보존할 positive candidate
- 아직 FIX 아님
- 다음 단계는 같은 artifact로 역순 재검증 한 번

## 지금 바로 할 일

새 코드를 작성하거나 새 빌드를 만들지 않는다.

같은 artifact로 순서만 뒤집는다.

1. `ARM64_RNAME_LDP_CANDIDATE.cmd`
2. Cemu 완전 종료
3. `ARM64_RNAME_LDP_BASELINE.cmd`

조건:
- 동일 save/location/camera
- 정지 scene
- 동일 graphics/FPS++ settings
- fixed weather
- 각 preset마다 Cemu 재시작
- 최소 `t=260s`까지
- 비교 구간 `t=70..260s`
- `arm64-compare-reuse`는 섞지 않음

두 PERF 로그를 비교해 역순에서도 positive인지 확인한다.

역순에서도 positive + correctness OK면 P1을 repeatable positive candidate로 확정하고, promotion 전에 reprofile한다.

역순이 neutral/negative면 order/drift 영향을 분석하고 promotion하지 않는다.

`arm64-compare-reuse`는 별도의 약 +1.68% positive candidate이며 아직 FIX가 아니다.

P1이 validate/reject되기 전에는 `0x02A281A0` 등 다음 hotspot으로 넘어가지 않는다.
