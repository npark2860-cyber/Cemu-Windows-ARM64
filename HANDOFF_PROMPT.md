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
- `.github/workflows/runtime-experiments-arm64.yml`

문서 작성 직전 마지막 검증된 non-documentation code checkpoint는:
`04b5626c77503aceed1fb712e45563bf620262fc`

해당 code checkpoint의 CI:
- Test Run #56
- run ID `34558962681`
- SUCCESS
- artifact `cemu-arm64-test`
- artifact ID `10184443139`

문서 커밋으로 실제 branch HEAD는 이후 달라질 수 있으므로 반드시 다시 조회한다.

현재 핵심 상태:

- BOTW 고정 장소/카메라/날씨 조건의 `perf-log` 벤치마크가 구축되어 있다.
- 1 ms PPC profiler cadence는 측정 교란이 커서 폐기했고, 현재는 RUNNING-only + 10 ms cadence를 사용한다.
- 최신 guest hotspot 상위 후보는 `0x0420CB80`, `0x02A281A0`, `0x03B84854`, `0x0399B4DC` 등이다.
- `0x03B84854`에서 동일 CMP가 반복 생성되는 패턴을 실제 ARM64 JIT dump로 확인했다.
- `arm64-compare-reuse` 실험은 동일 비교의 NZCV를 재사용해 `CMP + CSET + CMP + CSET + CMP + CSET` 계열을 `CMP + CSET + CSET + CSET`으로 줄인다.
- 같은 Run #56 빌드의 BOTW `t=70..260s` A/B에서 baseline 52.091 FPS, compare-reuse 52.968 FPS로 약 +1.68%였다.
- generated-code 개선은 확실하지만 성능 차이는 작으므로 **아직 FIX가 아니며 Release/Diagnostics에 promote하지 않는다.**

다음 작업:

1. 코드를 바꾸기 전에 `0x0420CB80`의 exact guest basic block / IML / native sequence를 분석한다.
2. load-heavy native dump가 guest semantic load인지, spill/reload인지, state restore인지 구분한다.
3. `0x02A281A0`은 mapped entry가 branch/thunk 형태이므로 첫 branch target을 따라간 뒤 실제 target code를 분석한다.
4. 명확한 redundant JIT instruction pattern 하나가 증명되기 전에는 새 최적화를 넣지 않는다.
5. 새 실험은 한 변수만 바꾸고, 다른 candidate와 섞지 않은 same-build BASELINE A/B로 검증한다.

이미 종료/비승리로 판정한 timer, Vulkan barrier/render-pass, NEON texture hash, historical compare/branch fusion/direct-dispatch 실험은 새 근거 없이 반복하지 않는다.

`main`은 건드리지 않는다. Release/Diagnostics도 이번 단계에서는 수정하지 않는다.
