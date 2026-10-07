# ANVIL 8비트 양자화 후속 실험

2026-09-29. 현재 ANVIL 실행은 FP32 ONNX/host I/O에 HTP FP16 옵션을 적용한 것이다. 먼저 성공한 32×32 UINT8 QDQ Conv는 연결과 산술 검증용이며 ANVIL INT8 성공을 뜻하지 않는다.

## 진행 경로

1. 준비된 1080p/720p/540p FP16 경로를 같은 balanced 전력 설정과 상세 profiling 조건에서 측정한다. 1080p 최초 측정은 평균128.937ms다. 해상도만 바꿨을 때의 비용을 분리한다.
2. 배포 입력과 같은 전처리로 만든 정렬된 RGB 프레임 쌍을 보정 데이터로 준비한다. ANVIL 입력은 NCHW FLOAT `[1,6,H,W]`이고 출력은 3채널 잔차다. Cemu용 운동 추정/정렬이 아직 없으므로 원본 게임 스크린샷을 임의로 두 번 붙인 것을 대표 보정 자료로 간주하지 않는다. 보정용과 품질 평가용 장면은 분리하고 전처리 설정과 입력 파일 해시를 기록한다.
3. 별도 x64 Python 환경에서 ORT 1.24.4의 QNN 전처리와 `get_qnn_qdq_config`/`quantize`를 사용해 QDQ 후보를 만든다. 첫 후보는 **8비트 가중치 + 8비트 활성값**이다. QNN에 맞춰 `QuantType.QUInt8`을 우선 검토한다. 흔히 INT8 경로라고 부르지만 이 후보의 저장 형식은 unsigned 8-bit다. 단순히 모델 파일의 float 가중치만 정수로 바꾸는 작업과 다르다. 현재 실험 폴더에는 Python ORT 양자화 도구와 대표 보정 데이터가 없으며, ANVIL 양자화 모델을 아직 생성하지 않았다.
4. 같은 해상도의 FP16과 U8/U8을 비교한다. 모든 연산의 실제 HTP 배치와 입출력 모양, 평균/p95 추론 시간을 확인한다. 현재 그래프의 Conv32, ConvTranspose4, Add17, Relu31 및 Pad/Slice는 QNN 지원 연산 목록에 있으나, 양자화 뒤 그래프 전체가 이 장치에서 실행되는지는 별도 확인 사항이다. 상수 shape/pad/crop 처리를 검증하며 float fallback을 성공으로 표시하지 않는다.
5. 잔차 및 합성 영상의 오차, 얇은 선/HUD, 빠른 카메라 이동, 새로 드러나는 영역, 연속 프레임의 떨림을 확인한다. 단순한 합성 입력 추론은 속도/호환성 예비 시험으로만 표시할 수 있다. 화질이 부족하면 8비트 가중치 + 16비트 활성값 또는 필요한 연산만 정밀도를 높이는 후보를 비교한다. 이 후보를 순수 8비트라고 표시하지 않는다.

## 판정 범위

INT8이 정확히 FP16의 두 배 속도라는 가정은 하지 않는다. NPU 연산, 입출력 형식 변환, 메모리 이동, 운동 추정/warp, 최종 합성 비용을 구분한다. 낮은 해상도 잔차를 고해상도 출력에 적용하는 방법과 화질은 아직 구현/검증하지 않았다. 기존 GPU LSFG Cemu 기준본은 보존한다.

실제 NPU/GPU/Cemu 실행은 사용자가 새 시간 사용을 승인한 후 진행한다. 장시간 CPU 보정/품질 평가도 사전에 예상 사용량을 알리고 시간을 협의한다.

## 근거

- [ONNX Runtime QNN 문서](https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html): QDQ, 대표 보정 데이터, x64 변환 환경과 uint8/uint16 선택. 문서에 남아 있는 "HTP only quantized" 문구는 같은 페이지의 FP16 옵션 및 이 장치의 실제 성공 결과와 함께 해석해야 한다.
- [ORT 1.24.4 QNN quantization 설정 소스](https://github.com/microsoft/onnxruntime/blob/v1.24.4/onnxruntime/python/tools/quantization/execution_providers/qnn/quant_config.py): QNN용 정적 QDQ 설정과 혼합 정밀도 설정.
- [ANVIL 원 프로젝트](https://github.com/NihilDigit/anvil): prealignment와 보정/평가 분리, 장치별 FP16/INT8 실험. Android V75 결과를 이 Windows V73 장치의 예상 성능으로 환산하지 않는다.
