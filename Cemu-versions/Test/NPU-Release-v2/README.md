# Cemu ARM64 NPU EXP v2 — Release

실행 파일은 `runtime/Cemu-npu-exp-v2.exe`, 제목은 **Cemu ARM64 [NPU EXP v2 - Release]**다. 기존 GPU LSFG 기준본과 NPU v1은 그대로 보존했다. SE나 진단 버전이 아니다.

## 이번 수정

v1 게임 로그에서 NPU 초기화가 한글 경로 변환 오류로 실패했고, 추론은 `runs=0`이었다. 같은 UTF-8 절대 경로를 시스템 코드 페이지 949의 파일 경로로 해석할 때 동일한 예외가 CPU 검사에서 재현됐다. QNN에는 검증된 ORT DLL 디렉터리 기준의 ASCII 파일명 `QnnHtp.dll`을 전달한다. ORT 1.24.4의 해당 로더는 이 경우 UTF-16 절대 경로를 만들어 `LoadLibraryExW`로 연다. 모델 경로도 UTF-16을 유지한다. 프로세스 PATH/작업 디렉터리나 시스템 언어 설정은 변경하지 않는다.

근거: [ORT 1.24.4 QNN Windows DlOpen](https://github.com/microsoft/onnxruntime/blob/v1.24.4/onnxruntime/core/providers/qnn/builder/qnn_backend_manager.cc#L2094-L2112), CPU 검사 `../NPU-Experiment/evidence/npu-path-cpu-tests-v2.log`.

**NPU 처리는 1920×1080 고정이며 2560×1440 출력도 허용한다.** FSR 등 출력 처리 후 프레임을 GPU로 1080p에 맞춰 캡처하고, 보간 결과와 보관한 원본을 선형 필터로 출력 크기에 확대한다. 이 단순 경로에서는 NPU ON 동안 원본도 1080p를 거치므로 네이티브 1440p보다 선명도가 줄 수 있다. Cemu의 게임 렌더 해상도 설정은 자동으로 변경하지 않는다. OFF에서는 캡처/추론/확대를 생략하고 원래 출력으로 돌아간다. Cemu 오버레이는 확대 후 출력 해상도에서 그린다.

초기화 실패와 실행 중 오류는 화면 알림과 `portable/log.txt`에 남는다. 모듈 초기화 오류에는 실패한 단계도 포함한다.

## 사용

1. Vulkan으로 게임을 실행한다. 시작 시 NPU 세션과 고정 자원을 준비하지만 추론은 OFF다.
2. 일반 설정 → 그래픽 → **NPU frame generation (experimental, 1080p/1440p output)**을 켠다. GPU LSFG와 동시에 켤 수 없다.
3. 실제 출력 창이 **1920×1080 또는 2560×1440 SDR**이어야 한다. 다른 창 크기에서는 원본 화면을 표시하고 알린다. 1440p 디스플레이에서는 전체화면을 사용할 수 있다.
4. 로그의 `[NPU] READY/OFF`, `[NPU] ON`, `[NPU-PROFILE] runs>0`을 확인한다. 체크박스 표시나 작업 관리자의 순간 사용량만으로 실행 성공을 판단하지 않는다.

앱을 다시 시작하면 NPU는 OFF다. 설정은 `runtime/portable`에 별도로 복사된다. MLC는 기존 LSFG Release 시험의 MLC를 공유하므로 게임 실행 시 기존 저장 데이터를 사용할 수 있다. NPU v1 및 GPU LSFG 실행 파일은 덮어쓰지 않는다.

## 검증 상태와 제한

`NPU-RELEASE-BUILD.json`은 빌드 당시 파일·드라이버·소스 해시와 CPU 검사 상태를 고정한 기록이다. 경로 회귀 검사 7개와 프레임 순서 검사 17개가 통과했다. 게임 및 확대 표시 성능/화질은 별도 실기 검증이 필요하다. 단독 NPU 실험의 약 30.8ms 결과를 이 게임 통합본 성능으로 해석해서는 안 된다.

`verify-build.ps1`과 `run-module-smoke.ps1`의 기본 호출은 파일 확인만 한다. 컴퓨터 사용 시간을 합의한 뒤 `run-module-smoke.ps1 -Run`을 실행하면 Cemu/UI 없이 같은 DLL의 초기화, OFF 추론 0회, 합성 입력의 NPU 추론 완료를 검사한다. 결과는 `../NPU-Experiment/evidence/npu-module-smoke-v2-*`에 별도로 저장한다. 이 검사는 실제 게임 화질이나 1440p 표시를 검증하지 않는다.

원본 한 프레임을 보관하므로 입력 지연이 늘어난다. 늦은 생성 결과는 버린다. 표시 FPS는 성공한 present 수이며 실제 디스플레이의 균등한 표시 간격은 아직 검증되지 않았다. 움직임 계산은 ±16픽셀, 4픽셀 정밀도의 실험이며 복잡한 게임 장면의 품질은 미검증이다. 네 유지 버전에 승격하지 않았다.
