# Vulkan ↔ QNN 공유 버퍼 독립 검증

사용자가 zero-copy 가능성을 물은 뒤 “진행 ㄱㄱ”라고 개발을 요청했다. 기존 Cemu와1080p 측정 도구는 유지하고 작은 버퍼용 ARM64 probe를 따로 준비한다. 실제 GPU/NPU 실행 전 사용 시간을 맞춘다.

## 순서

1. 시스템 Vulkan loader에서 Adreno 장치와 드라이버 API 버전 및 외부 메모리 확장을 조회한다. `VK_EXT_external_memory_host`가 없거나 storage/transfer buffer의 host allocation import를 지원하지 않으면 **UNSUPPORTED**로 종료한다. 이 경우 QNN 세션은 만들지 않는다.
2. 현재 NPU 드라이버의 해시가 고정된 RPC DLL과 기존 ORT1.24.4/QNN runtime을 사용한다. 작은 UINT8 평균 모델 `[1,6,32,32] → [1,3,32,32]`를 CPU fallback 없이 HTP에서 실행하도록 준비한다. 1080p ANVIL과 달리 NCHW인 산술 검사용 모델이다.
3. QnnHtpShared allocator가 만든 별개 입력/출력 allocation에서 GPU 요구 정렬을 만족하는 범위를 잡는다. ORT allocator 소스는 allocation 내부 포인터의 offset 등록을 지원한다. 버퍼 요구 크기와 실제 backing 범위를 확인하고 `vkGetMemoryHostPointerPropertiesEXT`의 memoryTypeBits와 buffer 요구 bits를 교차한다. HOST_VISIBLE+HOST_COHERENT 타입만 사용한다. host import가 거부되거나 이 조건을 만족하지 않으면 중단한다.
4. GPU의 `vkCmdFillBuffer`로 채널·4바이트 lane·round마다 다른 입력을 만들고, 출력을 독립적인 poison 값으로 채운다. transfer→host barrier와 fence 완료 후 같은 주소를 QNN 입력/출력 tensor로 사용한다. 입력을 CPU에서 shared payload로 memcpy하지 않는다.
5. 동기식 QNN Run과 출력 완료를 기다린 뒤, GPU가 같은 출력 buffer를 읽어 별도 진단용 readback buffer로 옮긴다. CPU는 그 진단 버퍼에서 GPU 입력과 평균 산술 결과를 검산한다. 같은 공유 버퍼를 유지한 채 5회 입력을 바꾸며, 출력도 바뀌어야 통과한다.

## 검증 범위

이 시험이 통과하면 애플리케이션 코드가 GPU→NPU→GPU 사이에 payload를 CPU memcpy하지 않고, import한 같은 RPC allocation을 이용해 바뀌는 데이터를 전달했음을 확인할 수 있다. **드라이버 내부에 복사가 전혀 없음을 증명하지는 않는다.** 최종 결과 확인을 위한 GPU→CPU 진단 readback은 별도로 존재한다.

이번 GPU 작업은 transfer 명령이다. storage-buffer usage로 import 가능한지도 확인하지만 실제 compute shader, FSR texture→U8/NHWC 변환,1080p 성능, 잔차 합성, 비동기 semaphore 연결은 검증하지 않는다. 일반 host-visible coherent 메모리와 동기식 RPC 완료를 통한 순차 handoff 실험이며, 모든 플랫폼에서 통하는 외부 장치 cache/소유권 프로토콜을 확립한 것으로 취급하지 않는다.

공유 메모리/타입/정렬/import 실패 시 다른 handle type을 추측해서 강행하지 않는다. 이 probe는 `HOST_ALLOCATION_BIT_EXT` 경로만 다룬다. FOREIGN/DX12 등 다른 경로의 가능성까지 부정하는 판정도 하지 않는다. Vulkan import를 해제하기 전에는 backing RPC allocation을 해제하지 않는다.

ORT profile은 켜 두어5회 모두 실제 QNN graph로 실행했는지 확인한다. 모델·실행 파일·관련 source/header·현재 GPU/NPU 드라이버를 고정하며, 새 디렉터리에 단계별 결과와 진단 readback을 저장한다. NPU 상세 추적은 off, performance는 balanced다. 테스트 시간은 연결 검증용이며1080p 성능 비교에 쓰지 않는다.

## 근거

- [Vulkan host pointer import](https://docs.vulkan.org/refpages/latest/refpages/source/VkImportMemoryHostPointerInfoEXT.html): 플랫폼별 import 거부 가능성, 포인터 정렬, allocation 수명과 접근 동기화 요구.
- [Vulkan host pointer properties](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetMemoryHostPointerPropertiesEXT.html): 개별 포인터의 호환 메모리 타입 조회.
- [외부 host memory 확장](https://docs.vulkan.org/refpages/latest/refpages/source/VK_EXT_external_memory_host.html): 크기/포인터 정렬과 import 기능.
- `reference/ort-v1.24.4/qnn_allocator.cc`: 공유 backing allocation 추적과 내부 offset 등록.
- `reference/ort-v1.24.4/test_inference.cc`: QnnHtpShared allocator와 I/O binding 예제.

Cemu에는 `CreateBufferFromHostMemory`가 있지만 사용 지점이 주석 처리되어 있고 포인터별 타입 조회도 없어, 현재 GPU/NPU 조합에서 동작한다는 근거로 사용하지 않는다. 별도 probe에서 먼저 확인한다.

```powershell
# 파일/드라이버 확인만. Vulkan/NPU library를 로드하지 않음.
.\run-interop-probe.ps1

# 새 GPU/NPU 사용 시간 승인 후에만 실행
.\run-interop-probe.ps1 -Run
```
