# 1080p INT8 성능·호환성 후보

2026-09-29. 사용자가 “1080p까지 해보지 그랬어”, “어차피 실험인데”라고 요청해 대표 게임 자료를 기다리는 정식 양자화와 초기 성능 실험을 분리했다. 기존 `INT8-NEXT.md`는 게임 품질 검증 경로이며, 이 문서는 우선 실행해 보는 합성 보정 후보에 해당한다.

## 준비 결과

- 원본: ANVIL FP32 SHA256 `65e871aed25b331e3a3747cf9019942121a94af71997476f5804a24b768cd0d8`.
- 후보: `evidence/int8-prep-20260929-071500-022764/anvil-1080p-synthetic-u8u8.onnx`.
- 후보 SHA256: `ec1abb0d5921a5117ff247bc7803287b44be38423af8e84393d8553cee84d95f`. 크기943,947bytes.
- QNN용 QDQ: 8비트 unsigned 가중치와 활성값, per-tensor, INT32 bias. Conv32/ConvTranspose4/Add17/Pad1/Slice2의 데이터 입력과 출력 양자화, scale 유효성, ONNX checker를 확인했다.
- 입력 `[1,6,1080,1920]`, 출력 `[1,3,1080,1920]`. host I/O는 FP32로 기존 FP16 시험과 같다. 이번 후보만으로 host 전송량이 줄어들지는 않는다.
- CPU 한 스레드에서136×240 합성 타일4개(검정, 흰색, gradient/checker와 이동, 균일 잡음)로88개 활성값 범위를 수집해1080p 그래프에 적용했다. CNN 가중치와 연산 구조는 동일하다. 이 범위는 실제1080p 게임 프레임의 대표 범위가 아니다.
- 별도 작은 합성 잡음에서 FP32와 U8 QDQ 출력을 비교했다. 유한값/비상수 출력 통과, 잔차 최대 절대 오차0.135447, RMSE0.018648. 이 값은 게임 화면의 PSNR/SSIM이나 품질 합격을 의미하지 않는다.
- NPU와 전체1080p 추론은 준비 과정에서 실행하지 않았다. 준비 계산은 약1.34초였고, Cemu/GPU/화면 조작은 없었다.

Python ORT1.24.4 CPU, flatbuffers25.12.19, sympy1.14.0, mpmath1.3.0, packaging26.0을 공식 PyPI wheel로 작업 폴더 `quant-tools`에만 풀었다. 시스템 Python이나 기존 ARM64 QNN runtime을 변경하지 않았다. 기존 `model-tools`의 ONNX1.20.1/numpy 등을 사용한다. wheel 해시는 `evidence/quantization-tools.json`에 있다. 한글 절대 경로의 ONNX native shape inference 문제는 별도 준비 프로세스의 cwd와 ASCII 상대경로로 해결했다.

## 실행

기존 Cemu/FP16/해상도 실험 파일과 원본 로그는 유지한다. 아래 실행은 **사용자가 새 측정 시간을 승인한 후** 순서대로 수행한다. 두 후보는 같은 원본 native probe, balanced 전력, detailed profiling, 첫 실행1회+warmup3회+측정10회를 사용한다.

```powershell
# 준비 상태 검사만. 장치 실행 없음.
.\run-int8-probe.ps1

# 새 시간 승인 후: 1080p FP16 재측정 → 1080p U8/U8 실험.
.\run-resolution-probe.ps1 -Resolution 1080p -Iterations 10 -Run
.\run-int8-probe.ps1 -Iterations 10 -Run
```

프로브는 QnnHtp backend, CPU fallback 금지다. U8 QDQ 후보가 하나의 QNN 그래프로 실행되고 매 추론의 실제 입출력 shape/형식, 출력 크기/유한값, iteration 수까지 맞아야 통과한다. 양자화 그래프의 지원 오류나 다른 provider 사용은 성공으로 표시하지 않는다. QNN 하위 구현의 실제 instruction 수준 정밀도를 직접 측정하는 도구는 아니다.

이번 판정 범위는1080p NPU 호환성 및 속도다. 실제 게임에는 clipping/잔상/세부 손실이 생길 수 있다. 게임용 대표 보정, Vulkan 전송, 운동 추정·정렬, 최종 합성, Cemu 동시 부하와 지속 성능은 뒤에서 별도로 검증한다.
