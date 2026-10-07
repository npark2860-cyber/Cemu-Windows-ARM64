# 1080p 호출·공유 메모리 비교 준비

2026-09-29. 현재 NPU 드라이버 `30.0.224.10000`에서 관측한 평균 36.012~38.384ms를 출발점으로 한다. 아래 후보는 빌드/파일 검증 단계이며 실제 개선 여부는 새 장치 시험으로 확인해야 한다. 사용자가 요청한 대로 NPU 실행 전 사용 시간을 별도로 맞춘다.

## 비교 순서

| 순서 | 후보 | QNN 추적 | 입출력 | 성능 모드 |
|---|---|---|---|---|
| 1 | Baseline | detailed | 기존 일반 메모리, 출력 매번 할당 | balanced |
| 2 | NoQnnProfile | off | 1과 동일 | balanced |
| 3 | ReuseHost | off | 일반 메모리, 출력 미리 할당 후 I/O binding으로 재사용 | balanced |
| 4 | SharedBalanced | off | QNN 공유 메모리에 입출력을 할당하고 재사용 | balanced |
| 5 | SharedSustained | off | 4와 동일 | sustained_high_performance |
| 6 | Baseline 반복 | detailed | 1과 동일 | balanced |

같은 U8/NHWC 1080p 모델, 원래의 논리 입력, 첫 실행 1회 + warmup 3회 + 측정 30회다. 첫/마지막 기준 실행으로 시간에 따른 변동도 확인한다. 작은 표본의 평균 개선만으로 장시간 발열 또는 Cemu 동시 부하에서 유지된다고 판단하지 않는다. 조건 3은 버퍼 재사용과 I/O binding을 함께 적용하므로 각각의 독립 효과를 분리하지 않는다.

QNN 상세 추적은 끌 수 있지만 **ORT profile은 모든 후보에서 유지**하여 실제 모든 추론이 QNN 한 그래프로 실행됐는지 확인한다. 완전히 추적을 끈 운영 성능이라고 부르지 않는다. CPU fallback 금지와 명시적인 QnnHtp backend는 유지한다. off 후보에는 장치 내부 구간 시간이 없으며 이를 0ms로 보고하지 않는다.

## 근거와 구현

- 공식 [QNN 설정 문서](https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html)는 `profiling_level`, `htp_performance_mode`, `enable_htp_shared_memory_allocator`를 설명한다.
- 현재 사용 중인 버전에 맞춘 [ORT v1.24.4 공유 메모리 예제](https://github.com/microsoft/onnxruntime/blob/v1.24.4/onnxruntime/test/shared_lib/test_inference.cc)와 [allocator 구현](https://github.com/microsoft/onnxruntime/blob/v1.24.4/onnxruntime/core/providers/qnn/qnn_allocator.cc)을 확인했고 원문을 `reference/ort-v1.24.4/`에 보관했다.
- 새 도구 `npu-tuning-probe.exe`는 원래 I/O probe를 보존한 별도 실행 파일이다. 공유 메모리의 실제 allocator 이름도 검사한다.
- 공유 메모리 조건은 현재 설치된 드라이버의 `libcdsprpc.dll`을 절대 경로 및 SHA256으로 고정한다. 해당 DLL만 자식 시험 프로세스 안에서 먼저 로드하며, 시스템 PATH나 드라이버를 바꾸거나 DLL을 복사하지 않는다. RPC DLL은 session과 모든 tensor가 해제될 때까지 유지한다. 공유 메모리를 사용할 수 없으면 그 조건을 실패 처리한다.
- 재사용 조건은 Run 뒤 output synchronization까지 측정하여 단순 제출 시간을 완료 시간으로 오해하지 않도록 한다. I/O tensor와 binding은 반복 중 유지하며 출력 버퍼 주소가 바뀌면 실패한다.
- 모델/도구/설정, 정확한 I/O shape/type, 원본 U8NHWC 출력 SHA256 일치, 매 추론 QNN 단일 kernel 여부를 모두 확인한 뒤 성공으로 판정한다. 측정 순서대로 각 시간을 저장한다.

## 해석 범위

입력은 한 번 채운 합성 영상이며 반복 호출마다 고정이다. 공유 메모리로 게임 프레임을 매번 쓰는 비용, GPU와의 동기화·전송, 영상 정렬·합성은 포함하지 않는다. 공유 allocator 사용 확인은 Vulkan과 NPU 사이의 무복사 경로를 증명하지 않는다. 33.3ms보다 짧아져도 완성된 Cemu 30→60FPS 경로가 입증되는 것은 아니다.

새 드라이버에 관해 사용자가 붙여 준 변경 내역은 보안 강화와 버그 수정에 따른 안정성 개선을 명시하고, NPU Fixes/개발자 변경/새 API는 None이다. 문서 표기 `1.2.4667.8400`과 설치 드라이버 `30.0.224.10000`의 버전 대응은 별도로 확인하지 않았다. 이전 실행과의 시간 차이 원인을 이 설명만으로 확정하지 않는다.

```powershell
# 해시와 설치 드라이버만 확인; 장치 실행 없음
.\run-tuning-probe.ps1 -Variant SharedBalanced

# 새 NPU 사용 시간 승인 후에만 한 조건 실행
.\run-tuning-probe.ps1 -Variant Baseline -Iterations 30 -Run
```

각 결과와 실패 원인은 새 evidence 디렉터리에 남는다. 기존 Cemu GPU 기준본, 이전 모델, 실행 도구와 manifest는 변경하지 않는다.
