# 1080p GPU 이미지 → ANVIL → GPU 합성 검증

2026-09-29. 사용자의 “오키 ㄱㄱ”에 따라 준비했다. 이 문서는 실행 전 고정한 계획이다. 장치 실행 결과는 별도 결과 파일에 기록한다. 기존 Cemu GPU LSFG 실행 파일과 네 유지 버전은 변경하지 않는다.

## 목적과 처리 경로

앞선32×32 시험에서 검증한 QnnHtpShared + Vulkan host import + 직접 Session::Run을1080p ANVIL UINT8 NHWC 모델에 적용한다. 매회 GPU에서 바뀌는 두 장의 RGBA8 UNORM image를 생성하고, compute shader가 공유 입력 버퍼에 RGB×2를 NHWC로 묶는다. NPU가 공유 출력에 잔차를 쓰면 GPU shader가 이를 역양자화해 입력 평균과 합성하고 RGBA8 image에 저장한다.

이는 실제 Vulkan image/compute 경로를 사용하는 독립 시험이다. 입력은 합성 패턴3종이고 움직임 추정/warp는 없다. 잔차 합성은 `clamp((A+B)/2 + (q-128)*0.00330072408542037, 0, 1)` 소비 동작을 검사한다. 영상 품질이나 ANVIL을 게임용 framegen으로 완성했음을 뜻하지 않는다.

고정 모델은 `evidence/io-prep-20260929-072654-165595/anvil-1080p-u8nhwc.onnx`, SHA256 `8bf0fbfd3be38cf571da5b79a47a83259a9ade9441688fc5defb06bbda0ecd3c`이다. 합성 보정 모델이라는 기존 제한도 유지한다. 입출력 크기는12,441,600/6,220,800byte다.

## 정확성 먼저, 성능은 별도 프로세스

`run-anvil1080-probe.ps1`은 기본적으로 해시와 드라이버만 검사한다. `-Run`은 다음 순서를 실행하며 첫 검증 실패 시 성능 실행을 시작하지 않는다.

1. **Verify:** 상세 로그를 켜고 서로 다른 패턴3종을 GPU→공유 NPU→GPU로 처리한다. 각 패턴마다 일반 CPU 메모리에 독립 생성한 같은 입력으로 QNN HTP를 한 번 더 실행한다. 이는 CPU inference fallback이 아니라 별도의 입출력 경로를 쓴 동일 NPU 기준이다. 입력6채널 배치와 합성 픽셀은 독립 CPU 산술 검산을 한다. NPU 출력은 두 경로가 바이트 단위로 같아야 한다. phase0은 기존1080p 출력 SHA256 `0432f24c82156b07286f45a6c8957673ea3e4d4aee55338dc11bf241bfc03eed`까지 확인한다. 공유 memHandle6개, 기준 RAW clientBuf6개, QNN kernel6개를 요구한다.
2. **Measure:** 상세 로그를 끈 새 프로세스에서 첫 실행1회, warmup3회, 측정30회를 실행한다.3패턴을 순환하며 GPU 이미지 생성·입력 변환·NPU 추론·출력 합성을 반복한다. 측정 루프 중 readback은 없고,34번째 종료 후 최종 phase0만 진단 readback으로 전체 검산한다. QNN kernel34개와 정확한 입출력 shape를 요구한다.

두 실행 모두 QNN 상세 profiling은 off, 성능 모드는 balanced이며 ORT profile은 유지한다. CPU fallback을 금지하고 QnnHtp.dll을 명시한다. GPU/NPU 드라이버 및 RPC DLL은 기존 검증값에 고정한다. 원본 공유 tensor를 직접 Run에 전달하고 주소가 유지되는지 검사한다.

## 시간 기록

- GPU timestamp: 합성 입력 이미지 생성, RGBA8→UINT8 NHWC pack, 잔차 합성의 각 command 구간. queue timestamp 지원과 wrap bits를 확인한다. 구간을 분리하기 위한 보수적 직렬 barrier를 사용한다.
- CPU wall: 입력 준비 명령 기록부터 GPU fence 완료까지, `Session::Run`, 합성 명령 기록부터 fence 완료까지, 이 세 구간을 포함한 전체 직렬 처리 시간.
- 두 제출의 `vkQueueSubmit` 호출 및 `vkWaitForFences` 시간도 따로 기록한다. 공용 Cemu queue mutex는 이 독립 도구에 존재하지 않는다.
- 출력 poison fill, 합성 패턴 생성, 두 host fence wait는 전체 wall time에 포함된다. session/pipeline 생성, 파일 쓰기, 진단 readback, CPU 검산, 일반 메모리 기준 추론은 제외된다. GPU 시간과 submit/wait는 wall time 안에 중첩되므로 더하지 않는다.

30회 mean/p50/p95/min/max 및33.333ms 미만 횟수를 보고한다. 이 수치를 실제 게임 FPS로 환산하지 않는다. Cemu 렌더, FSR, 운동 정렬, present, GPU/NPU 동시 부하와 장시간 발열 비용은 포함되지 않는다. 이 도구는 비동기 중첩의 성능을 측정하지 않는다.

## 실행과 증거

`runtime/anvil1080-pipeline-probe.exe`는 ARM64다. 명시적 `--run-devices`와 모든 경로/모드가 없으면 Vulkan/QNN 초기화 전에 거부한다. 화면이나 창을 생성하지 않는다. 시간을 다시 맞춘 뒤 실행하며, 강제 종료나 타 프로그램 조작은 하지 않는다.

Verify의 패턴별 진단 파일은 `[입력12,441,600][NPU출력6,220,800][합성RGBA8,294,400]`을 연결한26,956,800byte다. 이는 결과 검사를 위한 별도 GPU→CPU 복사이며 운영 전달 경로에 포함되지 않는다. 일반 메모리 기준 출력 파일도3개 보존한다. Measure는 마지막 진단 파일만 저장한다. 로그/원본 JSON/ORT profile/판독 결과는 실행별 새 폴더에 남는다.

도구와 소스·shader·모델 해시는 `evidence/anvil1080-probe-manifest.json`에 고정한다. 기존 런타임 및 작은 시험의 해시 검사도 함께 수행한다. 빌드는 GPU/NPU를 사용하지 않는다. 판독기의 offline 검사는 손으로 계산한 작은 NHWC/합성 fixture와 잘못된 입력·poison·alpha·profile·timing 거부를 포함한다.

## 출처

- 셰이더 컴파일러는 [Khronos glslang16.6.0 공식 배포](https://github.com/KhronosGroup/glslang/releases/tag/16.6.0)를 실험 폴더에만 받았으며, GitHub 공개 asset SHA256과 비교했다. 원본 다운로드 정보는 `evidence/glslang-16.6.0-origin.json`에 있다. 시스템 설치나 PATH 변경은 없다.
- [Vulkan timestamp 명세](https://docs.vulkan.org/refpages/latest/refpages/source/vkCmdWriteTimestamp.html)에 맞춰 queue의 유효 bit와 timestampPeriod를 사용한다.
- 모델의 원 연구와 운동 정렬의 별도 역할은 [ANVIL 원 저장소](https://github.com/NihilDigit/anvil)를 참고한다. 본 시험의 합성 residual consumer는 실제 게임의 정렬 경로를 대체하지 않는다.
