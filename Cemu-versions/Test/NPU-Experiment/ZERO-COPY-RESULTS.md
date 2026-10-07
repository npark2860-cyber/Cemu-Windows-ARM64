# GPU → NPU → GPU 공유 버퍼 전달 검증 성공

**최신 결과: revision5가 5회 모두 통과했다.** GPU가 매회 바꾼 입력을 NPU가 처리하고, GPU가 다시 읽은 출력이 독립 산술 검산과 일치했다. 입출력 모두 QNN 공유 memHandle을 사용했다. 작은 모델에서 애플리케이션 측 입출력 복사 없는 전달 경로를 확인했다.

사용자의 “지금 재검증해” 승인으로 **08:41:16.153~08:41:17.480**에 실행했고 장치 사용 종료를 안내했다. Cemu 실행이나 화면 조작은 없었다. GPU31.0.170.0과 NPU30.0.224.10000은 전후 동일했다.

## 성공 근거와 범위

- 도구 revision5, SHA256 `ee7db11e50962bba857cbe7acc4294fda1d43c903c2b8ff18b4ef44bacfca407`, 프로세스 exit0. 최종 판독 결과 `INTEROP_ROUNDTRIP_VERIFIED`.
- 32×32 UINT8 평균 모델의 입력 `[1,6,32,32]`, 출력 `[1,3,32,32]`를 각각 QnnHtpShared에 할당하고 Vulkan dedicated buffer로 import했다. 매 실행의 GPU 입력과 출력이 바뀌었고, 공유 tensor 주소도 유지됐다.
- GPU 입력은 기대 바이트와 전부 일치했다. NPU 출력은 5회 모두 최대 오차0.5 quantized byte로 허용치1 이내였다. 출력은 매회 달라졌으며 이전 출력이나 GPU가 채운 poison 값이 남은 결과가 아니다.
- QNN verbose 로그에서 공유 **memHandle 연결10회(입출력×5회), RAW clientBuf 연결0회**를 확인했다. `QnnHtp.dll`과 CPU fallback 금지 설정, ORT profile의 QNN 단독 kernel5개도 확인했다.
- CPU가 입력/출력 공유 payload를 채우거나 복사하는 경로는 사용하지 않았다. 다만 **결과 검산용 GPU→CPU readback 복사는 따로 수행했다.** 또한 GPU fence와 동기식 NPU Run을 순서대로 기다렸으므로 비동기 중첩 실행을 검증한 것은 아니다.
- 드라이버 내부 복사 부재, 실제 compute shader와 texture 변환,1080p 성능, 게임 보간 품질 및 완성된 Cemu framegen은 아직 미검증이다. 이 작은 모델은 ANVIL 모델이 아니다.

이번 도구는 QNN 메모리 연결을 보기 위한 verbose 로그를 켰고 별도 warmup도 없다. 첫 NPU Run25.4532ms, 이후6.3427~6.6336ms는 **연결 진단 기록**이며1080p 성능으로 비교하거나 환산하지 않는다.

성공 실행 원본: `evidence/vulkan-qnn-interop-20260929-084116-151-run.json`. 같은 이름의 폴더에 native 결과, ORT profile,5개 raw readback이 있으며 `-console.log`에 memHandle 기록이 있다. 실행 당시 manifest SHA256은 `fcd1632c88d1982c2db1ae4a37adc271fd0bc41aeaa314b61fc0add14bf74cac`이다. manifest의 준비 시점 표시는 원본 식별 보존을 위해 수정하지 않았다.

## 이전 실패와 수정 경위

2026-09-29. 사용자는 준비된 약1분 독립 GPU/NPU 검증 요청에 “ㄱㄱ”라고 승인했다. 장치 확인/재실행은08:26:44~08:30:37 사이에 이루어졌다. 도구 보완으로 예상 시간을 넘겼음을 알리고, 장치 실행 종료와 컴퓨터 사용 가능 상태를 안내했다. 이후에는 저장 자료 분석과 CPU 빌드만 수행했다.

### 첫 사용 시간에 확인한 사실

- 실제 Qualcomm Adreno X1-85 GPU의 vendor ID는 `0x5143`이다. Microsoft D3D12 변환 장치 이름에도 Adreno가 포함되어 초기 이름 기반 선택이 실패했다. 이는 GPU 기능 미지원 결과가 아니다. native vendor 조건으로 수정했다.
- GPU 드라이버 `31.0.170.0`은 `VK_EXT_external_memory_host`, `VK_KHR_external_memory_win32`, `VK_KHR_external_semaphore_win32`를 광고했다. 각 기능의 모든 사용 조합이 검증된 것은 아니다.
- host pointer 최소 정렬은4096byte, storage/transfer 용도 host allocation import는 지원됐다. 실제 buffer에는 dedicated allocation이 필요해 `VkMemoryDedicatedAllocateInfo`를 추가했다.
- **QnnHtpShared 입력/출력을 Vulkan으로 import하는 데 성공했다.** 입력8192byte, 출력4096byte import였고, 정렬 offset은 둘 다0이었다. memory type4의 flags7은 DEVICE_LOCAL+HOST_VISIBLE+HOST_COHERENT이다. tensor 논리 크기는6144/3072byte였다.
- GPU 입력 생성 후 QNN graph1회 실행까지 진행했으나, GPU가 다시 읽은 출력은 첫 round의 산술 검산에서 실패했다. 따라서 zero-copy 왕복 성공으로 판정하지 않는다. CPU fallback 없는 QNN kernel1개는 ORT profile로 확인했다.

원본 JSON의 앞선 `UNSUPPORTED`는 각 당시 도구의 선택/할당 제한을 포함한다. 전체 하드웨어 경로가 불가능하다는 뜻으로 해석하지 않는다. 마지막 revision4는 `FAILED`이며 output oracle 불일치다.

### 코드와 로그에서 발견한 입력 사본 문제

현재 ORT1.24.4의 [IOBinding::BindInput](https://github.com/microsoft/onnxruntime/blob/v1.24.4/onnxruntime/core/session/IOBinding.cc)은 `CopyOneInputAcrossDevices`를 호출한다. [QNN EP](https://github.com/microsoft/onnxruntime/blob/v1.24.4/onnxruntime/core/providers/qnn/qnn_execution_provider.cc)는 기본 CPU 장치를 입력 대상으로 보고하고, 공유 allocator는 HOST_ACCESSIBLE 메모리로 분류된다. [복사 판단 코드](https://github.com/microsoft/onnxruntime/blob/v1.24.4/onnxruntime/core/framework/utils.cc)는 이 위치가 다르면 사본을 만든다.

revision4는 BindInput 이후에 GPU가 입력을 채웠다. 실행 로그에는 이 연결 시점에 입력과 같은6144byte CPU arena 할당이 있다. 따라서 GPU 갱신 전 내용의 사본을 NPU가 읽은 것이 구체적인 원인 후보다. 실패한 raw readback은 당시 코드가 검산 뒤에 저장하도록 되어 있어 남지 않았으므로, 다른 원인까지 배제한 최종 확정은 아니다.

### 검증한 revision5

- `BindInput`을 사용하지 않고, 원래 공유 tensor와 미리 할당한 출력을 매번 직접 `Session::Run`에 전달한다. ORT의 CPU-addressable EP 실행 경로에는 NoCopy 분기가 있고, QNN은 HOST_ACCESSIBLE tensor를 memHandle로 등록하는 코드가 있다. tensor를 단순 CPU 메모리로 재표시하지 않는다.
- QNN의 [tensor 메모리 연결 코드](https://github.com/microsoft/onnxruntime/blob/v1.24.4/onnxruntime/core/providers/qnn/builder/qnn_model.cc)에 있는 verbose 로그를 켠다. 판독기는5회 입출력에 해당하는 memHandle 연결10개와 RAW clientBuf0개를 요구한다.
- 직접 Run 뒤 공유 tensor 포인터가 유지되는지 확인한다. GPU readback은 검산 전에 저장하고, 실패하면 첫 오차 위치와 실제/예상 값도 기록한다.
- ARM64 빌드, 파일/드라이버 preflight, 합성 판독 검사8개가 통과했다. 이후 승인된 장치 실행에서 직접 Run과 memHandle 경로로 바꾼 revision5가 실제 왕복 검산5회를 통과했다.

따라서 BindInput 사전 복사 경로를 제거한 수정은 실제 문제를 해결했다. 다만 revision4의 실패 바이트가 없어 당시 출력이 정확히 어떤 사본이었는지까지 복원한 것은 아니다.

verbose logging을 켠 작은 연결 진단이므로 여기의 실행 시간은1080p 성능 비교에 쓰지 않는다. 통과하더라도 드라이버 내부 복사 부재, 실제 compute shader,1080p texture 변환/합성, Cemu 전체 framegen을 증명하는 단계는 아니다.

## 이전 공유 메모리 성능 결과의 해석

1080p tuning의19.598ms 결과는 고정 입력을 먼저 채운 뒤 BindInput하고 Run만 반복한 값이다. 위 사본 경로가 있어도 고정 입력 출력은 맞을 수 있다. 따라서 그 숫자로 바뀌는 입력의 공유 메모리 전달이나 입력 복사 제거까지 입증했다고 볼 수 없다. 일반 메모리에서 QNN 상세 추적만 끈19.923ms 결과는 이 BindInput 문제와 구분된다.

전체 결과와 실행 목록: `evidence/interop-results-20260929.json`.
현재 검증된 도구의 준비 manifest: `evidence/interop-probe-manifest.json` revision5.
이전 도구/source/manifest는 `evidence/interop-probe-v1`부터 `interop-probe-v4`에 보존했다.

## 다음 확인 항목

확인된 직접 Run + 공유 memHandle 경로를1080p ANVIL U8NHWC 입력/출력에 적용하고, GPU가 매회 입력을 갱신할 때의 전체 비용을 측정해야 한다. texture에서 입력을 만드는 변환, 잔차 출력의 GPU 소비와 합성, GPU/NPU 동기화 시간을 각각 구분한다. 그 뒤 움직임 정렬 및 Cemu 동시 부하를 검증한다. 추가 장치 실행은 새 사용 시간을 맞춘 뒤 진행한다.
