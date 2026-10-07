# Cemu ARM64의 NPU 프레임 생성 검토

**후속 실측 갱신(2026-09-29):** 사용자 시간 승인 후 별도 `../NPU-Experiment`에서 Windows ARM64 QNN HTP 구동에 성공했다. 작은 UINT8/FP16 Conv 산술검사와 원본 ANVIL1080p 모델 모두 CPUfallback 없이 실행되고 QNN 전용 ORT kernel profile/exit0을 확인했다. ANVIL FP16 초기 설정(balanced,상세profiling)의10회평균128.937ms,p95131.046ms; QNN accelerator의 wait 제외 실행도평균97.081ms였다. 현재 설정은30생성/s 목표에미달하며 보간화질/GPU전송/Cemu통합은미검증이다. [실측 및 다음 단계](../NPU-Experiment/README.md), `../NPU-Experiment/evidence/first-htp-results.json` 참고. 아래는 실험 전 검토 기록이다.

2026-09-29. 사용자 제공 저장소를 읽기만 했다. SDK 설치, 외부 코드 실행, Cemu/GPU/NPU 실험은 하지 않았다. 검토한 소스 사본과 커밋은 `evidence/npu-reference`에 보관한다.

NPU는 후보가 될 수 있다. 현재 자료로 입증된 것은 QNN 실행 코드와 오프라인 보간 경로의 존재다. 이 PC에서 원본 30 FPS를 유지하며 60 FPS로 표시할 수 있다는 결과는 아직 없다. 현재 LSFG 성능 저하의 원인이 GPU 계산인지 렌더 스레드 대기인지 먼저 분리해야 한다.

| 자료 | 확인한 내용 | Cemu에 적용할 때 남은 작업 |
|---|---|---|
| [lsfg-npu](https://github.com/54pkp/lsfg-npu/tree/cddbb00c2b306b6aab30c676be556e6e98ce123b) | 실행 구현체가 아닌 설계·타당성 연구. LSFG 그래프의 준비/생성 분리와 GPU/NPU 전달 조건을 검토한다. | 기존 DLL의 Vulkan 셰이더가 변환 가능한 ONNX/QNN 모델이라는 뜻은 아니다. 이 문서의 v3.1 파이프라인을 현재 제공된 legacy 모듈과 동일한 구현으로 간주하지 않는다. |
| [hexscale](https://github.com/54pkp/hexscale/tree/8fed58387dcd5b417910b71f15b12d3aa1e509fa) | `qnn_runtime.cpp`의 provider 로딩, 모델 로딩, 실제 `graphExecute` 호출을 확인했다. `interpolate.cpp`는 외부 프레임·운동 벡터 파일을 읽어 Vulkan 평활화와 QNN 잔차 합성을 호출한다. | Windows x64 QNN CPU 검증과 Linux ARM64 교차 빌드가 Windows ARM64 NPU 실측을 대신하지 않는다. 게임 운동 추정과 자동 중간 프레임 표시는 미완성이다. |
| [ANVIL](https://arxiv.org/abs/2603.26835) | 저자는 H.264 디코더 운동 벡터를 재사용하고 NPU에는 합성 잔차 추론을 맡긴다. | Cemu의 최종 이미지 경로에는 그 디코더 운동 벡터가 없다. 별도 GPU 추정 또는 게임별 벡터 확보가 필요하다. 다른 기기의 영상 재생 성능을 Cemu 성능으로 환산하지 않는다. |

## 소스에서 확인한 제약

- Hexscale Vulkan layer는 프레임을 host buffer로 읽고 fence를 기다린다. 전송·처리·업로드까지 포함하는 동기 복사 경로다. 그 layer를 그대로 붙이는 방식은 현재의 렌더 스레드 직렬화를 개선한다고 볼 수 없다.
- QNN 실행은 `std::vector<float>` 입력을 모델 입출력 형식으로 pack하고 `graphExecute` 후 unpack한다. 공유 DRAM이라는 이유만으로 Vulkan 이미지와 QNN 텐서의 zero-copy 호환성을 가정하지 않는다.
- 제공된 ANVIL 모델은 FP32, 입력 `[1,6,1080,1920]`, 출력 `[1,3,1080,1920]`이다. Manifest는 NPU 실측을 false로 표시한다. INT8 보정에는 대표적인 게임 프레임과 화질 검증이 필요하다.
- 제공된 XLSR context는 SM8750/v79 대상으로 생성되었고 초해상도용이다. 현재 PC용 프레임 생성 모델로 사용할 수 있다는 근거가 아니다.
- 공식 [ONNX Runtime QNN 문서](https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html)는 Windows ARM64의 HTP 실행 경로를 제공한다. 초기 검증은 HTP 백엔드를 명시하고 CPU fallback을 금지하여, CPU 실행을 NPU 성공으로 잘못 판단하지 않아야 한다.

## 권장하는 실험 순서

1. 현재 Release 시험본에서 OFF/ON GPU timestamps, CPU submit/완료 대기 시간을 수집한다. 원본 40→20 하락을 NPU 필요성의 증거로 곧바로 해석하지 않는다.
2. Cemu와 분리된 Windows ARM64 HTP 실행으로 모델 한 쌍의 정확성·실제 백엔드·전체 시간을 확인한다. QNN 추론 시간 외에도 운동 추정, 정렬, packing, 양방향 전송, GPU 후처리를 측정한다. 실행은 사용자의 시간 승인 후에만 한다.
3. 비용이 유리한 경우 Cemu 내부에 선택 가능한 생성 backend로 연결한다. 최초 비교 입력은 기존과 같은 FSR 후 프레임으로 유지한다. 추론은 worker에서 처리하고 렌더 스레드는 다음 프레임을 준비한다.
4. 입력 두 장과 결과의 수명을 slot별 완료 상태로 관리한다. 크기 변경·OFF·오류 후 완료되지 않은 slot을 덮어쓰지 않는다. 늦은 결과는 취소/폐기 상태로 관리하고 원본 표시를 계속한다. NPU 완료가 확인되기 전 GPU consumer를 풀지 않는다.
5. 원본 ≥30 FPS, 지속적인 생성 처리량, 고른 60 Hz 표시, 추가 지연과 게임 화질을 함께 검증한다. 성공 전 네 유지 버전에는 적용하지 않는다.

개념적인 후보 경로는 `FSR 후 프레임 쌍 → 운동 추정/정렬 → NPU 잔차 합성 → GPU 최종 합성 → 표시`다. 이것은 ANVIL 계열의 새 backend 설계이며 현재 LSFG의 동등한 NPU 이식 완료를 뜻하지 않는다. GPU/NPU가 동시에 작업해도 메모리 대역폭과 전력 한도를 공유할 수 있으므로 실제 Cemu 부하에서 이득을 확인해야 한다.

30→60 보간의 생성 작업은 초당 30회다. 처리량 예산 약 33.3ms와 화면 표시 간격 16.7ms는 다르다. 과거·현재 두 프레임을 쓰는 설계의 버퍼링 지연도 따로 측정해야 한다.
