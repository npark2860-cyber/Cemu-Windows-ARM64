# 순정 Release 기반 LSFG 시험

**사용자 F11 반복 전환 시험 통과(2026-09-29).** 사용자가 “F11연타해도 멀쩡해”라고 보고했고 RESIZE 로그에서 화면 자원 재생성24회 모두 완료, 이전 overlay 재사용 방지3회 및 매번 LSFG 생성 재개를 확인했다. 해당 치명 오류0, 총18,845 생성 및 renderer shutdown 기록. `evidence/user-manual-20260929-0624-resize-log.txt`/분석 JSON에 보존했다. 이 실행은Quality100이며 실제 프로세스 종료 코드는 미수집이다. 아래의 재시험 대기 중 **Quality100 F11 반복 전환 항목은 이 결과로 갱신**한다. FPS 화면 표시/다른 프리셋별 전환/scanout 검증은 남아 있다.

최신 시험본은 **`runtime-experiment/Cemu-lsfg-resize.exe`**, 제목 `[LSFG RESIZE]`, SHA256 `ced1fa7b1291dd29fec78188165651634e6e8a9a07025afc2904e35b63737504`다. TUNE에서 보고된 전체화면→창 모드 종료의 의심 경로를 수정했다. Swapchain 핸들 값 대신 자원 세대를 비교해 폐기된 ImGui draw data를 재사용하지 않고 history를 초기화한다. 주 화면 FPS는 실제로 받아들여진 원본+생성 present 수를 포함하며 Native FPS를 병기한다. 빌드와 CPU2 suites/109checks PASS. **실제 창 전환 해결 및 화면의 FPS 표시 재검증은 대기**다. [수정 근거와 시험](RESIZE-FIX.md).

프리셋은 Performance/full motion resolution 기본, Quality/full 및 Performance/75% 선택을 유지한다. **삽입은 모두2X**, 출력 해상도는 그대로다. LSFG OFF에서 선택한 뒤 ON으로 켠다. TUNE의 사용자 Performance75 실행 로그는 보존했지만 마지막 `vkQueueSubmit` 오류 -3으로 종료돼 안정성 통과로 간주하지 않는다. 기존 TUNE(SHA256 `5461c3586c93d79620befa25e5d627ca93dc2b16c7b9a6e4a8fb2fac06036b15`)도 보존한다. [프리셋 사용법](TUNING.md).

사용자가 PROFILE 시험본을 실행한 뒤 “많이 좋아졌다”고 보고했다. `evidence/user-manual-20260929-0528-profile-log.txt`와 분석 JSON에 보존. 마지막 1429x992 구간은 원본31.98~32.59 FPS/생성 포함63.95~65.18 present 요청/s. 1440p의 유효 ON 구간은 원본 평균26.773 FPS/생성 포함53.545 요청/s였다. 장면은 통제하지 않았고 OFF는 로딩 구간뿐이라 정확한 A/B 개선율은 알 수 없다. 총9818 생성과 renderer shutdown을 확인했으나 process exit code는 미수집이다. 표시 요청은 두 장씩 몰리는 패턴이 남아 있어 1440p 원본30FPS 지속 방어와 고른 표시 간격은 후속 과제다. 네 유지 버전은 아직 미적용이다.

보존한 이전 계측 빌드: `runtime-experiment/Cemu-lsfg-profile.exe`, 제목 `[LSFG PROFILE]`, SHA-256 `6312fdb0700b592fac02ca58e348334e1c0f85943707f7f384af75507a2180d7`. 빌드 및 CPU 2개 suite/94 checks PASS. GPU query, QueueSubmit CPU 시간, 완료 대기와 경계 간격을 추가했다. [계측 항목과 비교 방법](PROFILING.md). 사용자의 첫 PROFILE 실행 결과는 위와 같다. 목표는 **원본 30 FPS 이상 + 고른 60 FPS 출력**.

이전 성능 비교본 `Cemu-lsfg-perf.exe`(d58032…)와 최초 사용자 시험본 `Cemu-lsfg.exe`(e2f789…)는 보존했다. [성능 수정 설명](PERFORMANCE-REVISION.md). 사용자 제공 NPU 후보 자료는 [NPU 검토](NPU-REVIEW.md)에 정리했다. SDK 설치 및 NPU 실행은 하지 않았다.

렌더 스레드의 half-period sleep 및 capture 직후 CPU fence wait를 없애고, 같은 큐의 입력 복사/생성/출력 복사를 최종 fence 한 번으로 묶었다. Present 요청 빈도와 간격, CPU wall time 로그를 추가했다. 같은 큐의 GPU 의존성 및 자원 수명 대기는 유지한다. 아직 동기식이며 두 출력이 몰릴 수 있으므로 평균 present 수치만으로 성공 처리하지 않는다. 이전 `Cemu-lsfg.exe`(e2f789…)와 해당 PDB는 보존했다.

네 유지 버전에는 아직 반영하지 않았다. 아래 시험 폴더와 원본 설치 폴더는 별개다.

| 단계 | 현재 결과 | 근거 / 범위 |
|---|---|---|
| 공식 순정 Release, 기존 설정 | PASS | 야숨 실제 야외 화면 확인, 83.91초 후 Alt+F4, 종료 코드 0 |
| 원본 보존 | PASS | 원본 EXE·설정·세이브 82개 SHA-256 변화 없음 |
| 공식 순정 Release, 변경 설정 | 실패 / 원인 미확정 | 렌더 960x540 + 창 1050x740 조건에서 18.09초 후 0xC0000005. LSFG 미포함. FSR 활성 로그 전에 종료 |
| 로컬 Release 재빌드, 기존 설정 | 부분 확인 | 야숨 타이틀 화면 유지, 232.29초 후 Alt+F4, 종료 코드 0. 플레이 진입은 이 실행에서 미확인 |
| LSFG 포함 빌드 | PASS | CRT를 Cemu와 같은 MT로 맞춰 링크 성공. ARM64 Release 시험 EXE 및 PDB 보관 |
| CPU 전용 계약 검사 | PASS | C/C++ 2개 suite, 오류 계약 90개, 실패 0, GPU 제출 0 |
| LSFG 초기화 / 최초 OFF | 부분 확인 | 사용자 직접 실행. 시작 shaders=51/pipelines=51/generated=0 로그 확인 |
| LSFG ON / 크기 변경 / FSR | 부분 확인 | 사용자 정상 동작 피드백. 생성 10,352장, 1429x992→2560x1440→1429x992, FSR EASU+RCAS 활성 및 renderer shutdown 로그 확인 |
| 반복 토글 / 실제 출력 계측 / 화질 | 대기 | 동일 크기 OFF→ON 반복, 성공 present 빈도·cadence, 경계 픽셀 포함 품질 확인 필요 |
| 성능 개선 | 사용자 회귀 보고 / 미통과 | 패치 전 원본 약 40 FPS → ON 원본 약 20 FPS. 렌더 스레드의 동기 GPU 대기와 추가 half-period sleep 확인. 비용 계측 및 같은 조건 A/B 필요 |
| 네 유지 버전 반영 | 대기 | 실제 검증 성공 후 LSFG 변경만 이식 |

공식 순정 EXE SHA-256: `d2d77ee6961d9f834740ae450653a9f9235da27f43f3b82ed35ca7b2acc56abb`

LSFG 없는 로컬 재빌드 SHA-256: `dde2a914eab3bca24c57fa73e447bf0cfb72c259819e4312fe717166dc9556cb`

소스 기준은 `final-adreno-compat-arm64`의 `c5205cc`이며, 공식 CI 빌드 전처리(FSR 포함)를 재현했다. SE 소스를 초기 시험에 사용하지 않았다. 두 바이너리와 시험 실행별 기록은 `runtime-experiment` 및 `evidence`에 구분 보관한다.

사용자 Escape로 UI 조작이 한 번 중지됐으며, 이후 사용자 지시에 따라 재개했다. 어떤 실행에도 강제 종료 타이머를 설치하지 않았다.

**현재 실제 테스트 승인 대기 상태. 사용자 요청에 따라 이후 Cemu 실행·GPU 실행 시험·화면 및 입력 조작은 먼저 시간을 요청하고 명시적인 답을 받은 뒤 시작한다.** 실행 중 Cemu는 없고 빌드도 종료됐다. CPU 전용 계약 검사는 화면이나 GPU를 사용하지 않았다.

위 승인 대기는 에이전트의 컴퓨터 조작에 대한 기록이다. 이후 사용자가 직접 시험했다. 결과는 `evidence/user-manual-20260929-0335.json` 및 로그 사본에 보존했다. 기존 FPS 카운터는 게임 원본 프레임을 세며 LSFG가 추가로 present한 프레임은 포함하지 않는다. 20 FPS 표시는 출력이 20장뿐이라는 뜻이 아니다. 실제 출력률을 계측한 결과는 아직 없다.

시험 EXE는 `runtime-experiment/Cemu-lsfg.exe`, SHA-256 `e2f7899842c93c0bbee13ad9c23581b9f3a74595e80270725784bc8ae6d7ffa2`. 창 제목에 `[LSFG TEST]`를 표시한다. 빌드·소스·PDB 해시는 `evidence/lifecycle-build-manifest.json`, CPU 결과는 `evidence/lsfg-cpu-contract-tests.log`에 있다. 네 유지 기준은 `evidence/baselines-after-lifecycle-build.log`에서 모두 동일성 PASS.

이번 구현은 시작 시 pipeline/resource 준비, OFF 우회, 정상 토글의 자원 유지 및 history clear, 세 원본 프레임에 걸친 warmup 후 2X 출력이다. warmup 중에도 원본을 출력하지만 각 warmup의 GPU 완료를 동기적으로 기다리므로 무중단 속도를 보장하는 구조는 아니다. GPU 실행·자원 재사용·화질·출력 간격은 아직 미검증. [실행 시험 순서](RUNTIME-TEST-PLAN.md) 참고.

설정·세이브·캐시는 복사본이다. 각 runtime의 `portable/mlc01/usr/title`은 설치된 게임 콘텐츠를 읽기 위해 연결한 junction이므로 정리 시 대상 콘텐츠를 따라 삭제하지 않는다.
