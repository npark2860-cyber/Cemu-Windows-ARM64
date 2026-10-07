# 1080p INT8 입출력·배치 실험

2026-09-29. 앞선 U8/U8 그래프의 FLOAT32 I/O 측정은105.306ms였고, 가장 큰 개별 NODE profile 항목은 입력 근처 Transpose였다. 사용자의 “오키”에 따라 다음 후보를 준비했다. 이 준비 과정에는 NPU/GPU/Cemu 실행이 없다. 별도 측정 시간 승인을 받은 뒤 실행한다.

## 세 후보

| 후보 | host I/O | 입력·출력 배치 | 변경 |
|---|---|---|---|
| FloatNCHW | FLOAT32 | NCHW | 앞서 측정한 U8/U8 QDQ 모델, 새 probe의 비교 기준 |
| U8NCHW | UINT8 | NCHW | 그래프 경계의 입력 QuantizeLinear와 출력 DequantizeLinear만 제거 |
| U8NHWC | UINT8 | NHWC | U8NCHW에 ORT QNN의 channel-last I/O 변환 적용 |

모두1920×1080, 같은 가중치/양자화 범위다. 새로운 학습이나 보정은 없다. 기존 작은 합성 데이터의 보정 범위를 그대로 사용하므로 게임 화질 검증을 대신하지 않는다.

U8 모델의 입력12,441,600bytes와 출력6,220,800bytes 합계는18,662,400bytes로, FLOAT32 I/O74,649,600bytes의1/4이다. 이는 host tensor 크기이며 실제 전체 메모리 이동량을 뜻하지 않는다. 입력 scale=0.003921568859368563, zero point=0. 출력 잔차는 `(u8 - 128) * 0.00330072408542037`로 복원한다.

`update_io_to_channel_last`는 입력/출력에 반대 방향 Transpose를 두어 QNN layout 변환 때 상쇄될 기회를 만든다. ONNX 파일에는 Transpose2개가 추가된다. 실제 NPU 그래프에서 제거되는지, 시간이 줄어드는지는 프로파일로 확인해야 한다. 원본 양자화 연산이나 가중치를 임의로 NHWC 형태로 바꾸지는 않았다.

## CPU 확인과 새 probe

`scripts/prepare_io_experiment.py`가 세 가지136×240 입력 패턴으로 CPU 한 스레드 검사를 수행했다. U8 NCHW와 NHWC 출력은 배치를 복원하면 바이트 단위로 같았고, U8 출력을 float로 복원한 값은 기존 FLOAT32 I/O QDQ 모델과 최대 절대 오차0이었다. 전체1080p 수치/NPU 검증은 아직 하지 않았다. 원본 모델과 이전 결과는 그대로 유지했다.

준비 기록은 `evidence/io-prep-20260929-072654-165595/preparation.json`이다.

- U8NCHW SHA256 `55b8bae4441de0341d92470091b6174a3cd57b077ed178d14f3a690f658f7699`.
- U8NHWC SHA256 `8bf0fbfd3be38cf571da5b79a47a83259a9ade9441688fc5defb06bbda0ecd3c`.
- `runtime/npu-io-probe.exe`: ARM64,322,048bytes, SHA256 `9045a2127994d531de9f93057bc63bdfe18aa70ddb86eb07c8c931d3e35eb9b3`.

새 probe는 기존 원본과 동일한 balanced/detailed profiling/동기 Run 측정 방식을 사용한다. NHWC 메모리 위치를 원래 NCHW의 논리 좌표로 변환해 동일한 영상 값으로 채운다. 모델 입출력 shape와 dtype/layout을 검사해 JSON에 기록한다. 새 소스·EXE·PDB·빌드 스크립트는 별도 이름으로 저장해 기존 실행 파일의 해시를 유지했다.

## 측정 절차

```powershell
# 파일 해시만 검사, 장치 실행 없음.
.\run-io-probe.ps1 -Variant FloatNCHW
.\run-io-probe.ps1 -Variant U8NCHW
.\run-io-probe.ps1 -Variant U8NHWC

# 새 시간 승인 후, 각 단계가 성공하면 다음 단계 실행.
.\run-io-probe.ps1 -Variant FloatNCHW -Iterations 10 -Run
.\run-io-probe.ps1 -Variant U8NCHW -Iterations 10 -Run
.\run-io-probe.ps1 -Variant U8NHWC -Iterations 10 -Run
```

각 모델은 첫 추론1회+warmup3회+측정10회다. QnnHtp, CPU fallback 금지, QNN 단일 fused graph14회, 실제 입출력 shape/type/layout 및 결과 크기를 검증한다. `scripts/read-io-result.ps1`는 실제 기록을 검증하며 예측 성능을 만들어내지 않는다. 시험 후 저장된 결과를 배치/scale에 맞춰 복원해 이전 모델과 비교하고, 프로파일에서 Transpose/Quantize/Dequantize 비용 변화를 확인한다.

NPU Run 밖의 입력 양자화/packing·출력 dequantization, Vulkan 이동, 운동 추정/warp/합성은 측정에 포함되지 않는다. 그래프에서 제거된 비용이 전체 시스템에서도 사라졌다고 해석하지 않는다. 최종 구현에서 입력 생성 단계와 U8/NHWC packing을 통합하고 출력 scale을 합성 shader에 적용할 수 있는지는 후속 작업이다.
