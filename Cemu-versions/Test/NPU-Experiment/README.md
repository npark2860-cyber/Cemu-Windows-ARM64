# Cemu NPU 독립 실험

## 후속 상태 — 사용자 RC1 통과 및 네 버전 통합

사용자가 “테스트 다 해봤고 아주 잘 된 것 같아”라고 보고했다. RC1의 마지막 720p 게임 로그와 확인 기록을 `../../NPU-Promotion/evidence`에 보존했다. 네 버전의 로컬 NPU 통합 빌드와 파일 검증은 완료됐으며 [실행 파일·소스 목록](../../NPU-Promotion/README.md)에 정리했다. 새 네 실행 파일 자체의 게임 실행은 하지 않았다. 아래 RC1 준비 단계의 “미검증” 표시는 당시 기록이다.

## 현재 상태 — NPU 전용 Release RC1, 1080p / 720p

사용자가 NPU만 정식 기능으로 남기고 1080p 기본 / 720p 성능 모드를 추가하는 방향을 승인했다. 새 후보는 `../NPU-Release-RC1/runtime/Cemu-NPU-Release.exe`이며 제목은 `Cemu ARM64 [NPU RC1 - Release - 1080p/720p]`다. SHA256은 `aa00dfc2261f8173eed1ef6406e34dcd7c417e450e6136d9ff241c001133ff8e`, manifest SHA256은 `5981cd28313e2b702eb2e65cc6952b4d07920e4e8c40531b906f936562f7c0f9`다.

LSFG UI/빌드 의존성/초기화/계측을 제거하고 NPU를 독립 옵션으로 분리했다. Lossless.dll은 필요 없다. 1080p를 기본값으로 하며 선택한 해상도는 다음 게임 시작 시 모델·공유 버퍼·GPU 흐름 계산·블릿 크기에 함께 적용된다. 모듈 ABI는 2다. ON/OFF 토글은 세션에만 유지되고 OFF는 패스스루다. ON 동안 버퍼링한 원본과 생성 이미지 모두 선택 해상도를 거친다. 720p는 1080p의 가로·세로 2/3, 픽셀 수 4/9이고 기존 LSFG 75% 프리셋과는 다르다.

1080p 모델·셰이더는 v4와 바이트가 같다. 720p 모델은 기존 U8 NHWC 가중치·양자화 값을 유지하고 고정 입출력/자르기 크기를 바꿨다. QNN이 거부했던 빈 reflect Pad만 항등 연산임을 확인하여 제거했다. 53개 네트워크 연산 형태와 CPU 작은 입력 3종의 비트 일치가 확인됐다. 720p 셰이더의 모든 소수 상수 보존도 검사했다. 초기 준비 스크립트의 소수 앞자리 0 제거 오류는 오프라인 검토에서 발견해 수정했고, 실행하지 않은 잘못된 산출물은 `promotion-v1/rejected-asset-prep-v1`에 격리해 보존했다.

Release ARM64 전체 빌드, 진단 코드 제외, LSFG 빌드 그래프 제외, CPU 검사 536개(27 profile + 17 timeline + 7 경로 + 485 overlay), PowerShell 5.1/7 파일·드라이버 검사가 통과했다. 패키지에는 고정 파일 120개, 소스 오버레이, 모듈/셰이더 소스와 기록이 있다. 코드 변경 전 작업 소스는 `promotion-v1/before-source`에 보존했다. 실기 검사는 사용자가 직접 하기로 했으며 **RC1/720p의 GPU·NPU·Cemu 실행은 아직 하지 않았다.** 새 후보의 게임 검증 후 네 가지 버전으로 승격할 단계다. 현재 Release / 최신 SE_Test 기반 Release+SE / Diagnostics / Diagnostics+SE 기준 소스는 모두 깨끗하며 기존 실행 파일은 변경하지 않았다.

아래 내용은 v4까지의 이력이다. 당시의 “현재”, “미검증” 표기는 각 단계의 기록이다.

2026-09-29. 사용자는 현재 GPU LSFG 빌드를 정식 승격 가능한 수준으로 평가했고, NPU를 먼저 시도하고 싶다고 요청했다. 이 폴더는 Cemu 실행 파일이나 renderer를 수정하지 않는 독립 실험이다. 기준은 F11 반복 전환을 통과한 `../LSFG-Release/runtime-experiment/Cemu-lsfg-resize.exe`이며 해시는 `ced1fa7b1291dd29fec78188165651634e6e8a9a07025afc2904e35b63737504`다. 기준 소스의 기록된 파일 해시도 일치했다. 해당 manifest는 `baseline/LSFG-RESIZE-BUILD.json`에 보존했다.

## Cemu 연결 현재 상태 — v4 Flow Cache 시험본 준비

**v4 사용자 게임 확인:** 사용자는 소폭 개선됐다고 보고했다. 새 게임 로그를 `evidence/cemu-npu-v4-game-20260929-171722.log`에 보존하고 같은 이름의 `.summary.json`에 집계했다. ON/eligible 상태의 1.8~2.2초 보고 구간 중 history/크기 변경 뒤 4초 이상 지난 구간을 모두 포함했다. 1440p 227구간(약 457.65초)의 시간 가중 평균은 원본 33.02FPS, 생성 29.22FPS, accepted present 62.24FPS였다. NPU Run 19.48ms, GPU 움직임 3.783ms였으며 stale 1,739회/no_slot 0회였다. 유효 구간 전체에 NPU 오류는 없었고 여러 창 크기 전환 후 세 번째 캡처에서 생성 프레임이 다시 나왔다. 일정하게 고정 2X가 되는 것은 아니며 원본 FPS가 높은 구간에서 폐기가 남았다. 동일 장면 v3/v4 A/B가 아니므로 FPS 개선률이나 실제 scanout을 이 로그로 확정하지 않는다. 에이전트는 로그만 읽었고 추가 장치 실행은 하지 않았다.

**사용자 GPU 비교 통과 및 Cemu v4 준비:** 사용자가 16:57:22~16:57:23에 `flow-cache-v4`를 실행하여 `FLOW_CACHE_WARP_MAPPING_VERIFIED`/exit 0을 얻었다. 측정 30쌍의 움직임 GPU 시간은 평균 3.9068→2.9646ms(24.12%, 0.9422ms 감소), p95 4.2782→2.9700ms였다. 검증/warmup/측정 45쌍의 1080p CPU 합성 매핑 차이는 0이었다. 전체 성분이 같은 쌍은 18이며 폐기 벡터/기록 비용 차이를 따로 기록했다. 이는 독립 GPU flow 단계와 CPU 소비자 매핑의 결과이며 게임 FPS/실제 GPU 합성 이미지 검증은 아니다. 결과는 `evidence/flow-cache-v4-20260929-165722-515.json`이다.

게임용 파일은 `../NPU-Release-v4/runtime/Cemu-npu-exp-v4.exe`, 제목은 `Cemu ARM64 [NPU EXP v4 - Release - Flow Cache]`다. v3에서 코드 변경은 창 제목 2곳뿐이고 패키지의 움직임 셰이더만 검증된 것으로 교체했다. 나머지 고정 runtime 파일은 v3와 해시가 같고 원본 v3/GPU LSFG 패키지는 보존했다. v3 설정을 별도 portable 폴더에 복사했으며 MLC 경로는 동일하다. Release ARM64 빌드/진단 코드 제외 확인/소스 변경 범위/파일 및 드라이버 확인과 PowerShell 5.1 preflight가 통과했다. 새 게임 패키지는 에이전트가 실행하지 않았으며 사용자가 직접 확인한다. `integration-v4`에 재현 스크립트, `../NPU-Release-v4/NPU-RELEASE-BUILD.json`에 고정 결과와 검증 범위를 보존했다. 아래는 단계별 이력이다.

**GPU 비교 도구 현재 파일은 v4:** 사용자 v3 실행(16:48:16)은 장면 전환에서 양쪽 모두 폐기하는 신뢰도 0 벡터 10개의 차이로 중단됐다. 종료 코드는 1로 올바르게 수집됐다. 저장된 출력의 1080p 전체 픽셀 합성 매핑 차이는 0이었고, 서로 다른 벡터 쌍의 정수 RGB SAD가 모두 동점임을 확인했다. 증거는 `evidence/flow-cache-v3-review-20260929-164816-533.json`이다. `flow-cache-v4`는 같은 GPU 셰이더를 유지하고, 신뢰도/유효 벡터의 완전 일치와 전체 픽셀 매핑 동등성을 검사한다. 양쪽 모두 폐기하는 벡터와 비용 기록의 허용된 차이는 별도로 보고한다. 실제 v2/v3 덤프와 변조·경계·상호 일치 사례를 포함한 CPU 검사 23개, 독립 Python 매핑 검토, ARM64 빌드와 PowerShell 5.1 파일 검사를 통과했다. GPU 재실행은 하지 않았다. 사용자 실행 파일은 `flow-cache-v4/run.ps1 -Run`이며, 실제 GPU warp 출력/게임 화질과 속도는 아직 추가 검증 대상이다.

**GPU 비교 도구 최신 수정:** 사용자가 `flow-cache-v2`를 16:36:21에 직접 실행했다. xy/신뢰도는 전부 같고, 경계 7개 블록의 기록용 비용만 1/1,000,000씩 달라 기존 전 성분 완전 일치 검사에서 중단됐다. Windows PowerShell 5.1의 이전 실행 스크립트는 종료 코드도 null로 남겼다. 상세 검토는 `evidence/flow-cache-v2-review-20260929-163621-945.json`이다. `flow-cache-v3`는 동일 GPU 셰이더를 유지하면서 xy/z 완전 일치와 미사용 비용 w의 차이 최대 1을 검사하고 그 차이를 명시적으로 기록한다. 소비자 소스를 다시 컴파일해 게임의 SPIR-V와 해시 일치도 확인했다. 종료 코드 수집은 .NET Process 핸들을 직접 소유하도록 수정했고, CPU 비교 검사 13개와 PowerShell 5.1/7 각각 6개 프로세스 검사가 통과했다. 수정본의 GPU 비교/성능 측정은 아직 하지 않았다. 사용자가 직접 실행할 파일은 `flow-cache-v3/run.ps1 -Run`이며 게임 패키지는 그대로다.

**GPU 비용 후속 검토:** 최근 `evidence/cemu-npu-v3-gpu-review-20260929-161534.log`의 원본 44~46FPS 구간은 GPU 움직임 계산 약 4.4~5.1ms이며 생성 결과 대부분이 마감을 놓쳤다. 사용자 승인으로 `flow-cache-v1`을 16:30:11~16:30:12에 GPU 비교했으나, 두 번째 입력에서 16,320개 양방향 블록 중 경계 두 블록의 정수화 비용이 1씩 달라 중단했다. 이동 벡터·신뢰도는 해당 입력 전체에서 일치했으며 성능 측정은 시작하지 않았다. 증거는 `evidence/flow-cache-v1-20260929-163011-700*.json` 및 출력 덤프, `evidence/flow-cache-v1-review-20260929-163011-700.json`이다. UNORM 재변환 또는 생성 산술 차이가 원인 후보이며 확정되지 않았다. 게임 패키지는 변경하지 않았고 장치 사용 종료를 알렸다. 후속 `flow-cache-v2`는 imageLoad 실수 값을 그대로 공유 scalar 배열에 저장한다. 모든 유효 주소·저장 비트의 CPU 검사와 셰이더/ARM64 도구 빌드·파일 검사를 통과했다. 31,488바이트의 공유 메모리를 사용하므로 실제 성능은 별도 GPU 검증이 필요하다. 새 시간 승인을 요청했으며 `flow-cache-v2/run.ps1` 기본 실행은 파일 검사만 한다. 정확성과 속도 확인 전에는 게임에 적용하지 않는다.

**후속 사용자 실기 확인:** 사용자가 v3를 실행한 뒤 체감 성능이 훨씬 좋아졌다고 보고했다. `evidence/cemu-npu-v3-game-20260929-112152.log`에서 11:20:00~11:20:54의 1440p 구간은 원본 FPS 평균 33.89, present FPS 평균 59.30, NPU Run 가중 평균 19.355ms였다. 1429×992 창모드 전환 후 세 번째 캡처에서 생성 프레임이 다시 나왔으며, 이후 짧은 구간은 원본 평균 34.91/present 평균 68.04였다. 수집 로그에 NPU 초기화/실행 오류는 없었다. 동일 장면 A/B나 실제 scanout 검증은 아니며 1440p 집계 구간에는 stale 459회가 있어 완전한 고정 2X 달성을 뜻하지 않는다. 집계는 `evidence/cemu-npu-v3-game-summary.json`에 보존했다. 아래 준비 시점 설명과 고정 빌드 manifest는 당시 상태의 기록이다.

사용자가 v2에서 실제 NPU 동작을 확인했고, 사용량은 70~80%로 관찰했다. 게임 로그의 두 번째 전체화면 구간(24개 약 2초 간격)에서 원본 FPS 평균 25.67, present FPS 평균 51.29, NPU Run 가중 평균 19.835ms, GPU 움직임 계산 5.233ms였다. 슬롯 부족은 0회, stale은 1회였다. 창모드의 1429×992 출력은 기존 크기 제한에 걸려 원본 표시로 전환됐다. 증거는 `evidence/cemu-npu-v2-game-20260929-105954.log`, 집계는 `evidence/cemu-npu-v2-game-summary.json`이다. 통제된 동일 장면 A/B 비교가 아니며 OS 사용률과 추론 wall time만으로 NPU 포화 여부를 단정하지 않는다.

후속 수정본은 `../NPU-Release-v3/runtime/Cemu-npu-exp-v3.exe`다. 고정 1080p 처리를 현재 창 크기에 맞춰 표시하며, 생성/원본 오버레이를 한 번 업로드해 두 번 읽는다. 원본 프레임 기준으로 제출 대기를 관리하고 재사용할 오버레이 버퍼의 마지막 읽기 명령까지 필요한 완료를 확인한다. 병목 위치를 구분하는 `[NPU-HOST]` 계측을 추가했다. NPU DLL/모델/움직임 셰이더는 v2와 동일하다. Release ARM64 빌드, CPU 오버레이 메모리 수명·경로·표시 순서 검사와 파일 확인이 통과했으며 **v3 실기 및 성능 향상은 아직 미검증**이다. 사용자가 직접 테스트하기로 했으므로 에이전트는 이번 작업 중 Cemu/GPU/NPU를 실행하지 않았다.

## v2 준비와 최초 수정 기록

사용자의 v1 게임 로그에서 NPU 초기화가 한글 경로 변환 오류로 실패한 것이 확인됐다. `runs=0`, 제출/완료 0회였으며 NPU 보간 성공 상태가 아니었다. 원본 로그는 `evidence/cemu-npu-v1-startup-failure-20260929-104104.log`에 보존했다. 동일한 예외를 시스템 코드 페이지 949에서 CPU 검사로 재현했다.

수정본은 `../NPU-Release-v2/runtime/Cemu-npu-exp-v2.exe`다. QNN 백엔드 경로를 검증된 ORT 디렉터리의 ASCII 파일명으로 전달하고, 실패 단계와 화면 알림을 추가했다. 사용자의 요청에 따라 1080p 고정 처리 결과를 1440p로 확대하는 출력 경로도 추가했다. ON 동안 원본도 1080p를 거친다. CPU 경로 검사 7개, 프레임 순서 검사 17개, ARM64 빌드·파일/드라이버 검사가 통과했으며 장치 및 게임 실행은 별도 시간 승인 후 검증한다. 자세한 내용은 `../NPU-Release-v2/README.md`와 고정 빌드 기록을 참조한다. 기존 GPU LSFG 및 NPU v1 패키지는 보존했다.

## 이전 Cemu v1 빌드 준비 기록

Release 기반의 별도 연결본 `../NPU-Release/runtime/Cemu-npu-exp-v1.exe`를 빌드했다. 제목은 `NPU EXP v1 - Release`이며 GPU LSFG와 별도 체크박스로 선택한다. 1080p SDR 전용, 원본 한 프레임 보관, 지연된 생성 결과 폐기, 3개 공유 텐서 슬롯과 지속 NPU 작업자 구조다. 표시 순서 CPU 검사 17개, ARM64 PE/파일 해시/드라이버 검사 및 Release 구분 검사가 통과했다. **이 Cemu 연결본의 실제 게임 실행은 아직 하지 않았다.** 사용자에게 실기 시간을 요청한 상태이며 자세한 사용법과 검증 범위는 `../NPU-Release/README.md`, 빌드 증거는 `../NPU-Release/NPU-RELEASE-BUILD.json`을 참조한다. 기존 GPU LSFG 실행 파일은 변경하지 않았다.

## 독립 시험 결과: 움직임 정렬과 비동기 작업자

사용자 승인으로 09:48:56~09:49:24에 독립 장치 시험을 완료했다. 1080p 정지·두 방향 이동·장면 전환의 입력/이동/NPU 출력/GPU 합성 검사가 모두 통과했다. 움직임 정렬과 비동기 작업자를 포함한 전체 시험 루프 평균은 30.7758ms, p95 31.7457ms, 최대 31.8657ms로 30회 모두 33.333ms 미만이었다. NPU Run 평균 19.3605ms, GPU 움직임 계산 평균 3.8257ms다. Cemu에는 아직 연결하지 않았고 실제 게임 품질·30→60FPS는 미검증이다. 현재 결론과 측정 범위는 `MOTION1080-RESULTS.md`, 증거는 `evidence/motion1080-session-20260929-094856-971.json`을 참조한다. 사용 시간은 종료됐고 추가 장치 실행은 새 시간 승인이 필요하다.

준비 단계의 CPU 검사 52개, ARM64 빌드·파일 해시·드라이버 검사가 통과했다. 준비 계획은 `MOTION1080-EXPERIMENT.md`, 고정 파일 목록은 `evidence/motion1080-probe-manifest.json`에 보존했다.

## 첫 NPU 실행 결과

**최신 결과:** 아래는 초기 FP16 측정 이력이다. 이후1080p UINT8 NHWC 모델의 GPU 이미지→공유 NPU→GPU 합성이 검증됐고, 전체 직렬 처리 평균21.3951ms/p9521.8377ms,30회 모두33.333ms 미만이었다. 실제 운동 정렬·Cemu 동시 부하·게임 품질은 아직 제외되어 있다. 현재 결론은 `ANVIL1080-RESULTS.md`를 참조한다.

사용자가 “지금 진행해”라고 시간 사용을 승인해06:44:09~06:44:47에 아래 세 단계를 실행했다. 모두 프로세스 exit0, CPU fallback 금지, QnnHtp backend 및 ORT의 QNNExecutionProvider만 사용하는 kernel profile이 확인됐다. Cemu 실행/화면 입력은 없었다. 사용 종료를 알렸으며 추가 NPU/GPU 실행은 새 시간 협의 후 진행한다.

| 단계 | 결과 | 측정 범위 |
|---|---|---|
| UINT8 QDQ 32×32 Conv | HTP 통과, 산술 oracle 최대오차0.5 | 20회 평균9.888ms, detailed profiling 포함 |
| FP16 32×32 Conv | HTP 통과, float I/O oracle 최대오차0.000414 | 20회 평균10.451ms, detailed profiling 포함 |
| 원본 ANVIL 1080p, FP16 경로 | HTP 통과, 출력 유한값 확인 | 10회 평균128.937ms, p95131.046ms, 최소127.984ms |

ANVIL 세션 준비4.310초, 첫 추론181.793ms. 첫 추론+3warmup을 제외한 QNN profile의 `Accelerator (execute excluding wait)` 평균97.081ms, `Accelerator (execute)`97.562ms, `QNN accelerator (execute)`119.272ms, RPC119.816ms, QNN execute123.433ms였다. 이들은 중첩되는 구간이므로 더하지 않는다. Accelerator 측정도 layout/형식 변환 등 장치 연산을 포함하므로 CNN 연산만의 시간은 아니다. Vulkan↔NPU 전체 전송 비용은 미측정이다.

**실제 NPU 구동에는 성공했지만 현재 설정은 실시간 생성 목표에 미달한다.** 초당30장 생성 예산약33.3ms보다 NPU 내부 실행 자체가 길다. 단순히 로깅/CPU 호출만 줄이면 해결된다고 볼 수 없다. 이번 값은 balanced 전력 및 상세 profiling 설정의 최초 FP16 기준값이다. 다음 후보는 대표 게임 프레임을 이용한 INT8 양자화, 모델 경량화, 입력/출력 및 정렬 경로의 비용 절감이며 속도와 화질을 함께 검증해야 한다. 이번 합성 입력 결과는 보간 화질을 입증하지 않는다.

요약과 각 원본 실행 링크/설정: `evidence/first-htp-results.json`. 실행 디렉터리는 `htp-smokequantized-20260929-064409-810`, `htp-smokefp16-20260929-064424-693`, `htp-anvil-20260929-064439-619`다.

## 해상도별 NPU 측정 결과

사용자의 “지금 측정해” 승인으로07:04:56~07:06:46에720p/540p 시험을 수행했다. 측정 종료와 컴퓨터 사용 가능 상태를 알렸으며, 이 사용 시간은 종료됐다. Cemu/화면 조작/강제 종료는 없었다.

| 입력 해상도 | ORT Run 평균 | p95 | 장치 실행 중 대기 제외 평균 |
|---|---:|---:|---:|
| 1080p, 앞선 측정 | 128.937ms | 131.046ms | 97.081ms |
| 720p | 49.079ms | 49.671ms | 35.503ms |
| 540p | 39.255ms | 39.627ms | 25.998ms |

모두 같은 probe/FP16/balanced/detailed profiling, 첫 실행1회와warmup3회 후10회 측정이다. 성공한720p/540p는 프로세스exit0, 매 추론의 QNN 단독 kernel14개, 실제 입출력 shape, 출력 유한값과 파일 크기를 확인했다. 각 평균은 짧은 독립 측정이며 동시 Cemu 부하나 장시간 발열 상태를 반영하지 않는다. 장치 값은 `Accelerator (execute excluding wait) time`이고 형식 변환 등을 포함한다. ORT Run에 포함되는 중첩 구간이므로 더하지 않는다.

720p 최초 모델은 패딩이 전부0인 `Pad`를 QNN이 거부(`Got QNN invalid zero only padding value`)하여 세션 준비 중exit1로 종료했다. CPU fallback 금지 정책이 작동했으며 추론 측정치는 없다. 해당 모델과 실패 로그를 보존했다. `scripts/prepare_zero_pad_720.py`는 이 항등 연산과 그 상수 계산만 제거하고, 첫 Conv의 입력을 원본 이미지로 연결한다. CNN/crop 및 가중치가 그대로인지 확인한 뒤 재측정이 통과했다. 실제720p 성공 모델은 **`models/anvil-small-720p-fp32-nopad.onnx`**, SHA256 `3151da962cb40410d8e73be27cf67c4b6db1dfb4ff1a59cc05f7b4e95cad9339`다.

해상도 축소의 효과는 확인됐지만 **540p도 host 추론 호출39.3ms로 초당30회 예산33.3ms를 넘는다.** 추론만 약15% 시간 단축이 더 필요하며, 실제 파이프라인에는 운동 추정/정렬, Vulkan 전송, 합성 비용까지 남아 있다. 장치 구간26ms만으로60FPS 성공이라고 판단하지 않는다. 다음 후보는 대표 입력 보정을 거친 INT8 및 입출력/호출 비용 개선이며 아직 ANVIL INT8은 시험하지 않았다. 합성 입력이라 게임 영상 품질도 미검증이다.

전체 결과: `evidence/resolution-results-20260929.json`. 성공 실행은 `htp-resolution-720p-20260929-070643-579`, `htp-resolution-540p-20260929-070530-368`이다. 최초720p 실패는 `htp-resolution-720p-20260929-070456-603`. 첫 준비 metadata/manifest는 각각 `resolution-models-v1.json`, `resolution-probe-manifest-v1.json`으로 보존했다. 현재 runner는 수정된720p를 검증해 사용한다. 모델 재생성 시 `prepare_resolution_models.py` 뒤에 `prepare_zero_pad_720.py`를 실행해야 하며, manifest가 다른 파일을 조용히 실행하지 않고 해시 불일치로 중단한다.

## 현재 준비 상태

### 1080p GPU 이미지 → ANVIL → GPU 합성 검증 성공

**revision2 검증 완료:** “지금 재검증해” 승인으로09:12:34~09:12:56에 실행했고, GPU→NPU→GPU3패턴 모두 입력·잔차·합성이 정확히 일치했다. 별도30회 측정은 NPU Run 평균19.5440ms, 전체21.3951ms/p9521.8377ms/최대22.3159ms였고 모두33.333ms 미만이었다. 첫 시험의 packed-byte 경계 읽기 문제는4픽셀당3 uint를 명시적으로 읽는 수정으로 해결됐다. 장치 사용은 종료됐다. Cemu 동시 부하와 운동 정렬은 아직 제외됐으며, 실제 연동에는 렌더 스레드를 막지 않는 별도 NPU 작업자가 필요하다. 상세 결과는 `ANVIL1080-RESULTS.md`, 요약은 `evidence/anvil1080-results-20260929.json`이다.

`anvil1080-pipeline-probe.exe`를 ARM64로 빌드하고 셰이더3개를 컴파일했다. 바뀌는 합성 RGBA8 이미지 쌍을 GPU에서 NHWC로 변환하고, 직접 공유 tensor Run으로 ANVIL 잔차를 받아 GPU에서 합성한다. Verify 모드는 일반 메모리 QNN 기준과3패턴을 비교하고, 통과한 경우에만 상세 로그를 끈 Measure 모드의 첫 실행1회+warmup3회+측정30회를 수행한다. GPU 구간, CPU wall, submit/fence 시간을 구분한다.

초기 준비에서 빌드, ARM64 식별, 파일/드라이버 preflight, 인자 없을 때 장치 초기화 전 거부하는 검사, offline 판독 검사14개가 통과했다. revision2는 판독 검사16개와 실제 장치 검증까지 통과했다. 사전 검사는 `evidence/anvil1080-preflight-v2.json`, `evidence/anvil1080-offline-tests-v2.json`, 성공 세션은 `evidence/anvil1080-session-20260929-091234-183.json`에 있다. 재실행은 새 장치 사용 시간 승인 후 `run-anvil1080-probe.ps1 -Run`으로 한다. 초기 계획은 `ANVIL1080-EXPERIMENT.md`, 실행 도구의 준비 시점 식별은 `evidence/anvil1080-probe-manifest.json`이다. 실제 운동 정렬·Cemu·게임 품질·GPU/NPU 중첩 실행은 이 독립 시험에 포함되지 않는다.

### Vulkan ↔ QNN 공유 버퍼 전달 검증 성공

**revision5 장치 검증 완료:** “지금 재검증해” 승인으로08:41:16~08:41:17에 실행했고, GPU→NPU→GPU 왕복 검산5회가 모두 통과했다. ORT1.24.4 BindInput의 사전 복사 경로를 제거하고 원본 공유 tensor를 직접 Run에 전달했다. QNN memHandle 연결10회, RAW clientBuf0회, QNN 단독 kernel5개와 매회 달라지는 출력의 정확성을 확인했다. GPU31.0.170.0/NPU30.0.224.10000, Vulkan import 정렬4096byte, memory type4/flags7이었다. 작은 모델에서 앱 측 입출력 복사 없는 전달을 확인했으며 장치 사용 시간은 종료됐다.1080p나 Cemu 전체 framegen 검증은 아니다. 성공 범위·이전 실패와 수정은 `ZERO-COPY-RESULTS.md`, 원자료는 `evidence/interop-results-20260929.json`을 참조한다.

zero-copy 가능성 확인 요청에 따라 `npu-vulkan-interop-probe.exe`를 별도로 ARM64 빌드했다. Vulkan host pointer import 지원을 먼저 조회하고, 가능하면 QnnHtpShared 입력/출력을 Vulkan storage/transfer buffer로 import한다. GPU가5회 바뀌는32×32 입력을 생성하고 NPU 평균 모델을 실행한 뒤 GPU가 출력을 읽도록 했다. CPU는 별도 진단 readback에서 산술 결과를 검산한다. 이는 작은 버퍼의 애플리케이션 복사 없는 handoff 시험이며, 드라이버 내부 무복사·1080p 처리·완성된 framegen을 증명하지 않는다.

초기 준비 때 빌드, 해시/현재 GPU31.0.170.0 및 NPU30.0.224.10000 preflight, 명시적 실행 플래그가 없으면 장치를 시작하지 않는 검사, 합성 결과 판독 검사7개가 통과했다. 이후 revision5에서 판독 검사8개와 실제 장치 시험까지 통과했다. 성공 원본은 `evidence/vulkan-qnn-interop-20260929-084116-151-run.json`이다. 재실행은 새 사용 시간 승인 후 `run-interop-probe.ps1 -Run`으로 수행한다. 초기 계획은 `ZERO-COPY-EXPERIMENT.md`, 파일 식별은 `evidence/interop-probe-manifest.json`, 초기 준비 검사는 `evidence/interop-preflight.json` 및 `evidence/interop-guard-check.json`, 최신 판독 검사8개는 `evidence/interop-reader-fixture-20260929-083509-727/tests.json`에 있다. manifest는 실행 당시 해시를 보존하기 위해 준비 시점 기록을 유지한다.

### 호출·공유 메모리 비교 도구 준비

**후속 장치 비교 완료:** 사용자의 “진행해” 승인으로08:06:20~08:06:58에6조건을 실행했고 사용 시간은 종료했다. 현재 드라이버 `30.0.224.10000`에서 기준36.5719ms → QNN 상세 추적 off19.9228ms → 일반 버퍼 재사용20.0158ms → 공유 메모리 balanced19.5981ms → 공유 메모리 sustained19.6416ms → 기준 재측정36.5602ms였다. off 네 조건은 각각30회 모두33.333ms 미만이고, 여섯 실행 모두 QNN 단독 실행과 기존 출력 SHA256 일치를 확인했다. ORT profile은 유지했다. 주된 개선은 QNN 상세 추적을 끈 데서 나왔다. Cemu 전송·정렬·합성, 변화하는 게임 프레임, 장시간/동시 부하는 아직 검증하지 않았다. 상세 결과는 `TUNING-RESULTS.md`, 원자료 요약은 `evidence/tuning-results-20260929.json`이다.

사용자의 후속 최적화 요청으로 `npu-tuning-probe.exe`를 별도로 ARM64 빌드했다. 같은1080p U8NHWC 모델로 기존 기준 → QNN 상세 추적 끄기 → 일반 출력 버퍼 재사용/I/O binding → QNN 공유 메모리 → 공유 메모리+지속 성능 모드 → 기준 반복을 비교하도록 준비했다. 모든 조건에서 ORT 실행 profile과 CPU fallback 금지를 유지하며, 출력 SHA256·실제 allocator·설정·전체 QNN 실행 여부를 검사한다. 현재 드라이버와 RPC DLL도 고정했다.

준비 단계에서 빌드 성공, 다섯 조건의 해시/드라이버 preflight 통과, 저장 자료를 사용한 결과 판독기 검사7개 통과를 확인했다. 그때는 새 도구의 NPU 실행 전이었으며 이후 승인된 실제 결과는 위에 추가했다. 상세 계획은 `TUNING-EXPERIMENT.md`, manifest는 `evidence/tuning-probe-manifest.json`, 파일 검사는 `evidence/tuning-preflight.json`, 판독기 검사는 `evidence/tuning-reader-fixture-20260929-080353-429/tests.json`에 있다.

### 8비트 입출력 및 NHWC 후보 준비

**드라이버 변경 확인:** 사용자가 NPU `30.0.224.10000` 업데이트는 두 번째 NHWC 실행(38.384ms)부터 적용됐다고 확인했다. 현재 연결 장치도 해당 버전을 사용 중이다. 첫 34.374ms는 업데이트 전, 38.384ms 및 36.012ms는 업데이트 후로 구분한다. 모델·실행 옵션은 같아도 시스템 드라이버 환경이 달랐으므로 전체를 동일 환경의 반복 측정으로 보거나 차이를 부팅 탓으로 확정하지 않는다. 자세한 구분은 `IO-RESULTS.md`와 `evidence/driver-update-context-20260929.json`에 있다.

**최신 측정:** 부팅 부하 가능성을 논의한 뒤 사용자가 “지금 괜찮아”라고 승인해07:42:27~07:42:33에U8NHWC10회를 추가 측정했다. 평균36.012ms/p9536.253ms/최소35.699ms, 장치 대기 제외18.148ms였다. 출력은 앞선 두NHWC 실행과SHA256까지 동일하며 QNN 단독 실행이 다시 확인됐다. 직전38.384ms보다 편차와 평균이 개선됐지만 부팅 원인은 미확정이고33.3ms 예산에도 미달이다. 사용 시간은 종료했다. 기록은 `evidence/io-post-boot-results-20260929.json`.

**측정 및 재측정 완료:** 승인된1080p 비교에서기존 INT8 FLOAT32/NCHW I/O105.900ms → U8NCHW92.066ms → U8NHWC34.374ms였다. 사용자의 추가1회 요청에 따른U8NHWC 재측정은38.384ms(p9540.365ms)였다. QNN 단독 실행과 실제I/O 검증 통과, 두NHWC 실행 출력은바이트 단위로 동일했고 U8NCHW와도 배치 복원 후 동일했다. 상세 profile의 큰Transpose 항목이NHWC에서 제거된 것도 확인했다.33.3ms 목표와 전체 Cemu 파이프라인은 아직 미달/미검증이다. 장치 사용 시간은 종료했다. 범위·숫자·출력 차이와 후속 후보는 `IO-RESULTS.md`, 원본 증거는 `evidence/io-results-20260929.json`에 있다.

1080p INT8의 다음 실험으로 기존FLOAT32/NCHW I/O, U8/NCHW I/O, U8/NHWC I/O를 같은 논리 영상으로 비교할 준비를 마쳤다. 작은CPU 검사에서 배치 복원 후U8 출력은 바이트 단위로 같고, float로 복원한 결과도 기존QDQ 모델과 일치했다. 입출력 tensor 크기는74.6→18.7MB다. 새 ARM64 probe는 별도 파일로 빌드했고, NPU 측정은 새 시간 승인 후 진행한다. 세 후보와 측정 범위는 `IO-EXPERIMENT.md`에 기록했다.

### 1080p INT8 예비 후보

**후속 측정 완료:** 07:18:21~07:18:45 사용자 승인 시험에서1080p U8/U8 QDQ 후보가 CPU fallback 없이 HTP 실행에 성공했다. 같은 설정의FP16 재측정129.007ms 대비INT8 평균105.306ms로18.37% 단축됐다. 장치 실행 중 대기 제외는96.857→65.864ms다.33.3ms 목표에는 여전히 미달하며, 가장 큰 개별 NODE profile 항목은Transpose였다. 추가 장치 실행 없이 로그 및 저장 출력을 분석했다. 자세한 결과와 후속 후보는 `INT8-RESULTS.md`, 구조화된 증거는 `evidence/int8-1080p-results-20260929.json`에 있다. 사용 시간은 종료했고 컴퓨터 사용 가능 상태를 알렸다.

사용자의 추가 요청으로 합성 입력을 이용한1080p U8/U8 QDQ 후보를 별도 준비했다. 기존 `INT8-NEXT.md`의 실제 게임 품질 보정 경로와 구분한다. CPU 한 스레드의 작은 합성 타일로 양자화 범위를 얻었고, 구조 및 작은 출력 검사를 통과했다. 후보의 입출력 해상도는1080p이며 host 형식은 기존FP16 시험과 같은FP32다. 이 준비 시점에 NPU는 아직 실행하지 않았다. 후보/해시/검증 범위/실행 절차는 `INT8-EXPERIMENT.md`에 기록했다.

### 해상도 축소 실험 준비

`scripts/prepare_resolution_models.py`로 720p(1280×720), 540p(960×540) 모델을 파생했다. 원본1080p 파일과 기존 실행 도구/manifest는 보존했다. 파생 모델은 입력/출력 shape와 해상도에 대응하는 Constant4개만 변경하고 initializer72개 및 네트워크 연산을 그대로 유지한다. 540p는 아래쪽4픽셀, 원본1080p는 아래쪽8픽셀 반사 패딩이 필요하며 720p는 패딩이 없다.

ONNX checker, 네트워크84개 연산의 텐서 shape, skip 연결 양쪽 shape, 반사 패딩 및 최종 crop의 reference 계산이 통과했다. 입력 크기만 바꾸고 기존1080p 상수를 남긴 잘못된 모델을 거부하는 검사도 통과했다. 이는 전체 CNN 수치 동등성이나 화질/NPU 성능 검증은 아니다. 기록은 `evidence/resolution-models.json`.

`run-resolution-probe.ps1`은 기존 probe binary와 모든 기본 파일 해시 및 새 모델 해시를 검증한다. 실행 후에는 QNN 단일 그래프의 매 추론별 실제 입출력 shape, 출력 파일 크기, iteration 수까지 확인한다. 최초 준비는 장치 실행 없이 이전1080p 로그 재분석으로 결과 판독기를 확인했다. 이후 승인된 실제 측정과720p 항등 패딩 제거 결과는 위 절에 기록했다.

```powershell
# 파일 해시만 검사. 장치 실행 없음.
.\run-resolution-probe.ps1 -Resolution 720p
.\run-resolution-probe.ps1 -Resolution 540p

# 사용자가 새 NPU 사용 시간을 승인한 후 각 단계 실행.
.\run-resolution-probe.ps1 -Resolution 720p -Iterations 10 -Run
.\run-resolution-probe.ps1 -Resolution 540p -Iterations 10 -Run
```

같은 FP16/balanced/detailed profiling 설정으로 해상도 효과부터 분리한다. 파생 모델의 host 입출력 합계는720p 약33.2MB,540p 약18.7MB이며 실제 전송량 전체를 뜻하지 않는다. 고해상도 출력 합성 경로는 아직 없다. INT8 후속 경로와 보정 자료 요건은 `INT8-NEXT.md`에 기록했다. ANVIL INT8 모델은 아직 생성하지 않았다.

### 기본 도구

- Windows ARM64, Snapdragon X1E80100. DriverStore에 V73 stub 및 FastRPC 파일이 있다. 파일 존재는 NPU 실행 성공을 의미하지 않는다.
- 공식 Microsoft.ML.OnnxRuntime.QNN 1.24.4, 포함 QAIRT 2.42.0을 이 폴더에만 내려받아 풀었다. 시스템 SDK/드라이버/PATH를 변경하지 않았다. NuGet의 원본과 MIT/Qualcomm/ThirdParty 고지는 `ort-qnn-1.24.4`에 보존했다. 출처/해시는 `evidence/downloads.json`.
- MSVC ARM64로 `runtime/npu-probe.exe` 빌드 성공. EXE와 모든 runtime PE DLL의 ARM64 헤더 확인. EXE SHA256 `59517848f33dfbe26a9fe0f5208c41a227471949d2f7981c0f867bcb992602d9`.
- 작은 QDQ UINT8 평균 Conv 모델, 같은 FP32 평균 Conv 모델, 검토한 ANVIL FP32 모델의 ONNX checker 통과. 구조 검사만 수행했다. `scripts/prepare_models.py`는 장치 runtime을 import하지 않는다.
- 프로파일 판정의 CPU-only 합성 사례 7개 통과: QNN만 허용, CPU 혼용/CPU만/미상 provider/누락 provider/빈 프로파일 거부. 실제 NPU 실행 결과는 아니다.
- `run-probe.ps1` 기본 실행은 파일 해시만 확인한다. `-Run`이 있어야 장치 프로그램을 실행한다. 최초 세 단계의 사용자 승인 실행 결과는 위에 기록했다. 추가 실행 전에도 사용 시간을 협의한다.

## 실행 순서

이 폴더를 작업 디렉터리로 사용한다. 첫 두 모델은 NPU 연결과 산술 정확성을 점검하는 작은 Conv이며 움직임 보간 모델이 아니다.

```powershell
# 파일 준비 확인만; NPU 실행 없음
.\run-probe.ps1

# 사용자가 준비됐거나 에이전트 실행 시간을 승인한 뒤에만
.\run-probe.ps1 -Stage SmokeQuantized -Run
.\run-probe.ps1 -Stage SmokeFp16 -Run
.\run-probe.ps1 -Stage Anvil -Iterations 10 -Run
```

앞 단계가 실패하면 원인을 먼저 확인한다. CPU 대체 실행으로 성공 처리하지 않는다. `QnnHtp.dll`을 명시하고 ORT의 `session.disable_cpu_ep_fallback=1`, `offload_graph_io_quantization=0`을 적용했다. 동봉 runtime에서는 QNN CPU/GPU backend DLL도 제외했다. ORT 프로파일에서 QNNExecutionProvider kernel 이벤트가 있고 다른 provider나 provider가 누락된 kernel이 없어야 `HTP_EXECUTION_VERIFIED`로 기록한다. 이 상태도 게임 보간 성공은 아니다.

각 호출은 1회 첫 추론 + 3회 warmup 후 지정 횟수를 측정한다. NPU 전력 설정은 첫 연결 확인용 `balanced`다. 자동 강제 종료, 서비스 등록, Cemu 실행, 화면 입력은 없다. 컴파일/세션 생성이 예상보다 길어질 수 있다. `evidence/htp-...`에 실제 exit code, console, ORT/QNN profile, 결과 JSON 및 마지막 출력 tensor를 보존한다. 다음 실행이 이전 자료를 덮어쓰지 않는다.

## 무엇을 측정하는가

- 세션/그래프 준비 시간, 입력 준비 시간, 최초 추론 시간.
- ORT Run의 평균/p50/p95/최소/최대 host wall time. 출력 할당, RPC/host 전송, 상세 profiling overhead가 포함된다. 순수 NPU kernel 시간으로 해석하지 않는다.
- 작은 Conv는 원본 입력의 채널별 평균이라는 별도 산술 oracle과 전 출력 값을 비교한다. UINT8 오차≤1, FP16 경로 float I/O 오차≤0.002를 요구한다.
- ANVIL에는 결정적인 합성 입력을 사용한다. 유한한 출력인지 점검하며 잔상/움직임 보간 화질을 검증하지 않는다. 모델의 FP32 host 입력은 약49.8MB이고 예상 출력은 약24.9MB다. 실제 GPU↔NPU 전송 비용은 별도 계측해야 한다.
- Vulkan readback/upload, 게임의 운동 추정, ANVIL 입력 정렬, 최종 합성, 동시 Cemu 부하, frame pacing은 아직 없다. NPU 추론 시간만 기존 LSFG 전체 프레임 시간과 비교해 승패를 선언하지 않는다.

## ANVIL 적용 조건

`models/anvil-small-1080p-fp32.onnx`는 기존 검토에서 사용한 hexscale commit `8fed58387dcd5b417910b71f15b12d3aa1e509fa`의 파일이며 SHA256 `65e871aed25b331e3a3747cf9019942121a94af71997476f5804a24b768cd0d8`과 일치한다. `ANVIL-LICENSE`도 보존했다. 입력은 `[1,6,1080,1920]` 하나이고, ONNX graph는142개 노드이며 Conv32/Relu31/ConvTranspose4 및 정적 shape/pad/crop 관련 노드를 포함한다. 출력 metadata에는 symbolic axis가 있어 ORT의 상수/shape 정리 후 HTP가 지원하는지 실제로 확인해야 한다. 원본 모델은 변경하지 않았다.

원 논문 계열은 별도로 정렬한 프레임과 NPU 잔차 합성을 사용한다. Cemu에는 영상 디코더 운동 벡터가 없으므로 게임용 운동 추정/정렬 경로가 필요하다. FP16이 동작하더라도 성능이 부족하면 실제 게임 프레임을 이용한 양자화와 화질 검증이 다음 단계다. 합성 입력으로 보정한 모델을 게임용 완성본이라고 표시하지 않는다.

첫 실행이 성공하면 전체 전송 경로의 비용을 계측하고, 기존 GPU LSFG와 같은 프레임 쌍으로 비교한다. Cemu 연결은 그 뒤 별도 backend로 진행하며 GPU 기준본을 보존한다. 원본≥30 FPS 목표에는 NPU 추론뿐 아니라 메모리 대역폭·전력 공유와 추가 지연도 포함된다.

## 출처

- [공식 ONNX Runtime QNN 문서](https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html): Windows ARM64, runtime 포함 패키지, HTP 선택, CPU fallback 비활성화.
- [공식 NuGet 1.24.4](https://www.nuget.org/packages/Microsoft.ML.OnnxRuntime.QNN/1.24.4): 버전을 고정해 준비했다.
- [검토한 hexscale 모델](https://github.com/54pkp/hexscale/tree/8fed58387dcd5b417910b71f15b12d3aa1e509fa/models): 모델/manifest/라이선스.
- [ANVIL 원 프로젝트](https://github.com/NihilDigit/anvil): prealignment, FP16/INT8 HTP 실험과 영상 디코더 운동 벡터 전제. 다른 모바일 SoC의 결과를 이 PC 성능으로 환산하지 않는다.
