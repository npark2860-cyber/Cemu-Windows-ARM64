# LSFG 계산량 비교 시험본

최신 후속 파일은 `runtime-experiment/Cemu-lsfg-resize.exe`(`[LSFG RESIZE]`)다. 아래 세 프리셋을 유지하며 창 전환 수명 수정과 생성 포함 FPS 표시를 추가했다. TUNE 사용자 실행에서는 전체화면→창 모드 종료가 보고됐고 로그를 보존했다. RESIZE 실제 재검증은 대기 중이다. [변경 근거 및 확인 순서](RESIZE-FIX.md). 아래는 최초 TUNE 제작 시점의 설명이다.

사용자 요청: PROFILE에서 개선된 성능을 유지하면서 1440p에서도 원본 30 FPS에 더 가까워지도록 추가로 줄일 수 있는 비용을 확인한다. PROFILE 측정에서 LSFG prepass 약3.66ms + generated 약7.36ms였고 host submit gap은 약0.05ms였다. 이번 시험은 기존 모듈이 제공하는 Performance 셰이더와 내부 운동 추정 해상도를 노출한다. 실제 속도·화질은 아직 검증하지 않았다.

파일: `runtime-experiment/Cemu-lsfg-tune.exe`, 제목 `[LSFG TUNE]`. 기존 PROFILE, PERF, TEST 파일은 그대로 보존한다. 기준 소스는 순정 Release c5205cc이며 SE가 아니다.

## 사용 방법

Graphics 설정에서 기존 LSFG 체크박스 아래 `LSFG processing`을 선택한다. LSFG를 OFF로 한 다음 설정을 바꾸고 다시 ON으로 켠다.

| 선택 | 내부 설정 | 목적 |
|---|---|---|
| Quality / Full motion resolution (previous) | Quality, flow100% | PROFILE과 같은 화질·계산 설정 |
| Performance / Full motion resolution | Performance, flow100% | **새 시험본 기본값.** 제공된 Performance 셰이더 사용 |
| Performance / 75% motion resolution | Performance, flow75% | 내부 운동 추정의 가로·세로 해상도를75%로 줄여 계산량 감소 시도 |

세 설정 모두 **원본 프레임 사이에 생성 한 장을 넣는 2X**다. 75%는 생성 프레임 비율이 아니다. 최종 출력 해상도와 원본 렌더/FSR 설정은 바꾸지 않는다. 1440p에서75%는 내부 운동 추정을 약1920×1080으로 수행한다. 내부 픽셀 수는 원래의56.25%이지만 최종 합성·복사 등은 남으므로 전체 시간이 그 비율로 줄어든다고 예측하지 않는다.

Performance 및 낮은 운동 추정 해상도는 가림 경계, 빠른 회전, 얇은 선 등에 보간 품질 차이를 만들 수 있다. 동일한 장면·창 크기에서 각 설정을15초 이상 유지해 원본 FPS와 잔상/깨짐을 함께 비교한다. 같은 EXE에서 Quality로 돌아갈 수 있다. 앱을 다시 시작하면 기본 Performance/Full 설정으로 돌아가며 LSFG는 OFF로 시작한다.

## 구현과 수명

- 기존 ABI1의 context 구조는 변경하지 않고 준비 전 CPU-only `lsfg_cemu_set_context_tuning()`을 추가했다. 기존 호출자는 Quality/100% 기본값을 유지한다.
- Backend의 `perf`와 inverse-flow 인수로 전달한다. 내부 이미지의 양 축이128보다 작아지는 설정은 모듈 API에서 거부한다. 아주 작은 창에서는 Cemu 어댑터가75% 요청을100%로 조정하고 실제 값을 로그에 남긴다.
- GPU 자원 준비 뒤 tuning을 바꾸려 하면 API는 BUSY를 반환한다. 어댑터는 기존 Cemu 이미지 사용 완료를 확인한 뒤 context를 교체하고 새 history로3회 warmup한다. 옵션 변경은 OFF에서 가능하고 다음 ON 때 적용된다. 같은 옵션에서 단순OFF/ON은 기존 자원 재사용 경로를 유지한다.
- 크기/옵션 변경 시 통계 구간을 분리하고 PERF 로그에 `preset`과 실제 `flow_percent`를 추가했다. GPU/CPU 계측은 PROFILE과 같다.
- 최종 GPU 완료 대기와 overlay 수명 대기는 유지한다. 이번 변경은 계산 설정 비교이며 비동기화나 출력 pacing 완성본이 아니다. 두 present가 몰리는 문제는 별도 과제로 남는다.

## 검증 범위

빌드 성공, CPU CTest2 suites/109 checks/0 failures/GPU submissions0, diff check PASS. 로그는 `evidence/tune-build-verified.log`, `tune-cpu-tests.log`, manifest는 `tune-build-manifest.json`이다. 유효 범위, 최소 내부 크기, null/잘못된 구조·설정의 거부 및 GPU 접근 없는 설정 변경을 검사했다. Cemu/GPU 실행과 화면/입력 조작은 하지 않았다. 사용자의 수동 실행으로 성능과 화질을 확인하기 전 네 유지 버전에는 적용하지 않는다.
