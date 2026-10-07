# 1080p GPU → ANVIL → GPU 합성 검증 성공

**revision2가 정확성 검사3종과 성능 측정30회를 통과했다.** 사용자의 “지금 재검증해” 승인으로09:12:34.185~09:12:56.371에 실행했고 장치 사용 종료를 안내했다. GPU31.0.170.0/NPU30.0.224.10000은 전후 동일했다. Cemu 실행이나 화면 조작은 없었다.

## 검증 결과

- 서로 다른 합성 패턴3종 모두 GPU의 RGBA8→NHWC 입력이 독립 CPU 패턴과 전부 일치했다.
- GPU가 읽은 공유 NPU 출력은 패턴별 일반 메모리 QNN 기준과 바이트 단위로 같았다. phase0은 기존1080p 출력 SHA256과도 일치했다.
- GPU 잔차 합성은3패턴의 RGB 전부 독립 계산과 일치했고 최대 오차0, alpha255였다. packed-byte 읽기 수정으로 앞선 합성 문제가 해결됐다.
- Verify에는 공유 memHandle6개와 기준 RAW clientBuf6개, QNN kernel6개가 있었다. Measure는 QNN kernel34개(첫 실행1+warmup3+측정30)였고 CPU fallback 없이 HTP만 사용했다.
- 성능 측정 중3패턴을 순환했다. 루프에는 진단 readback을 넣지 않았고 종료 후 마지막 phase0 전체를 재검산했다. 따라서 측정의 모든 중간 프레임을 개별 readback으로 검증했다고 해석하지 않는다.

## 성능

새 프로세스에서 QNN 상세 추적과 verbose 로그를 끄고, ORT profile과 balanced 설정을 유지했다. 첫 실행1회와 warmup3회를 제외한30회다.

| CPU wall 구간 | 평균 | p95 | 최대 |
|---|---:|---:|---:|
| GPU 입력 준비와 완료 대기 | 1.0372ms | 1.4125ms | 1.5007ms |
| NPU 직접 Run | 19.5440ms | 19.7850ms | 19.8883ms |
| GPU 잔차 합성과 완료 대기 | 0.8127ms | 0.9412ms | 1.5326ms |
| **전체 직렬 처리** | **21.3951ms** | **21.8377ms** | **22.3159ms** |

전체 최소21.0198ms, **30회 모두33.333ms 미만**이었다. NPU 외의 평균 비용은 전체에서 Run을 뺀1.8511ms다. 작은 host 간격 때문에 각 wall 평균 합과 전체가 미세하게 다르다. 각 열의 p95/최대는 서로 다른 표본일 수 있으므로 더하지 않는다.

GPU timestamp 평균은 합성 이미지 생성0.1483ms, NHWC pack0.3768ms, 잔차 합성0.3409ms였다. 두 QueueSubmit 호출 평균은0.0297/0.0448ms, 두 fence wait 평균은0.9472/0.7027ms다. 이 값들은 위 wall 구간에 포함되며 중복해서 더하지 않는다. GPU timestamp는 구간 분리를 위한 직렬 barrier를 사용한 command 구간이다.

전체에는 합성 입력 생성, output poison, 두 host fence wait가 포함된다. session/pipeline 생성, 파일 저장, 진단 readback, CPU 검산과 일반 메모리 기준 추론은 제외했다. 측정 프로세스 session 생성4.502초도 별도다.

## 해석과 남은 작업

이 독립 시험에서 초당30회 보간의33.333ms 예산 대비 평균11.9382ms가 남았다. 그러나 실제 운동 추정/정렬, Cemu 렌더·FSR·present, 동시 메모리/전력 경쟁, 장시간 발열은 아직 포함되지 않았다. Cemu가11.9ms 안에 렌더된다는 뜻이나60FPS 달성의 증거가 아니다.

**현재 시험의 동기식 Run을 Cemu 렌더 루프에 그대로 삽입하면 약19.5ms를 기다리게 된다.** Cemu 연동에서는 별도 NPU 작업자와 프레임 슬롯/완료 상태를 통해 게임 렌더와 추론을 겹치는 설계가 필요하다. 먼저 움직임 정렬을 연결하고, 승인된 실기 시간에 원본/출력 FPS·지연·화질·resize 안정성을 확인한다. 기존 GPU LSFG 기준본과 네 유지 버전은 변경하지 않았다.

애플리케이션 측 CPU 입출력 복사 없는 공유 전달을1080p에서 확인했다. 진단 readback은 별도 복사이며 드라이버 내부 무복사는 증명하지 않았다. 입력과 양자화 보정은 합성이므로 실제 게임 품질도 미검증이다.

성공 세션: `evidence/anvil1080-session-20260929-091234-183.json`.
정확성 실행: `evidence/anvil1080-verify-20260929-091234-186-run.json`.
성능 실행: `evidence/anvil1080-measure-20260929-091248-040-run.json`.
전체 표본과 증거 요약: `evidence/anvil1080-results-20260929.json`.

## 이전 실패와 수정 경위

2026-09-29. 사용자의 “지금 검증해” 승인으로09:04:49.791~09:05:01.974에 첫 검증을 실행했다. 프로세스는 검산 실패를 보고하고 exit1로 종료했다. 성능 측정은 시작하지 않았으며, 장치 사용 종료와 컴퓨터 사용 가능 상태를 알렸다. 이후 분석·수정·빌드는 CPU 작업만 수행했다.

### 첫 실행에서 확인된 부분

- 실제1080p GPU RGBA8 이미지2개를 공유 NHWC 입력으로 변환했다. 저장된 진단 파일 전체를 검사한 결과 **입력12,441,600byte의 불일치는0개**다.
- GPU가 읽어낸 NPU 잔차 출력6,220,800byte의 SHA256은 **`0432f24c82156b07286f45a6c8957673ea3e4d4aee55338dc11bf241bfc03eed`**로 기존 일반 메모리1080p 기준과 완전히 같다. 첫 phase0 하나에 대한 결과다.
- QNN 공유 memHandle 입출력2개와 QNN 단독 kernel1개, QnnHtp.dll 및 CPU fallback 금지 설정을 확인했다. GPU/NPU 버전은 전후31.0.170.0/30.0.224.10000으로 같다.
- 큰 공유 버퍼의 Vulkan import도 성공했다. 입력12,443,648byte, 출력6,221,824byte, offset0, memory flags7이었다.

### 실패 구간과 저장 자료 분석

마지막 GPU residual compose가 검산과 달랐다. RGB6,220,800개 채널 중983,175개가 허용치1을 넘었고, 최대 오차는112였다. Alpha는 모두255였다.

관측값 전체를 분석하자, **RGB의 두 번째/세 번째 채널이4byte uint 경계를 넘어도 첫 채널의 uint word를 재사용한 경우**의 CPU 계산과 실제 GPU 합성이6,220,800개 채널 전부 정확히 같았다(최대 오차0). 이는 무작위 캐시 손상보다 packed-byte 읽기 경로 문제를 지지한다. 원 shader의 SPIR-V에는 ArrayStride4와 각 byteAt 함수의 UDiv/UMod/AccessChain이 있다. 다만 GPU 드라이버 내부 컴파일 원인까지 증명한 것은 아니므로 드라이버 버그라고 확정하지 않는다.

실패 raw 파일은 검산 전에 저장되어 있어 입력/NPU 출력/합성을 구분해 확인할 수 있었다. 첫 검사에서 종료됐기 때문에 phase1/2, 일반 메모리 새 비교3종, 전체 검증 및 성능값은 없다. session 생성11.629초는 모델 준비 시간이지 프레임 처리 시간이 아니다.

### revision2 수정

동적 byteAt 호출을 없애고,4 RGB 픽셀의12byte를3 uint로 명시적으로 읽고 고정 shift로 펼치도록 GPU 합성을 수정했다. 입력/NPU/메모리 전달 경로는 같다. 실패 시 합성 픽셀 위치와 실제/예상 값도 남긴다.

ARM64 빌드, shader 컴파일, 해시/드라이버 preflight가 통과했다. 독립 CPU 판독 검사에는 서로 다른 잔차가 uint 경계를 넘는 수기 fixture와 잘못된 첫 word 재사용 거부를 추가해16개가 통과했다. 이후 승인된 revision2 장치 검증과 성능 측정도 위와 같이 통과했다.

현재 도구 SHA256: `b711bbdae5e83a46520e20e117c5616c427a36431dc5b6eab5125159f6904bf3`.
첫 실행 도구와 바뀐 소스/셰이더/manifest/PDB는 `evidence/anvil1080-probe-v1`에 보존했다.
현재 manifest는 실행 당시 해시 보존을 위해 준비 시점 표시를 유지하며, 실제 성공 여부는 실행 기록과 본 결과 문서로 확인한다.

## 기록

- 첫 세션: `evidence/anvil1080-session-20260929-090449-790.json`
- 실행과 원본: `evidence/anvil1080-verify-20260929-090449-792-run.json` 및 같은 이름의 폴더
- 저장 자료 분석: 해당 폴더의 `offline-diagnosis.json`, `compose-word-boundary-diagnosis.json`
- 초기 SPIR-V: `evidence/anvil1080-compose-v1-spirv.txt`
- 요약: `evidence/anvil1080-results-20260929.json`
- 새 준비: `evidence/anvil1080-probe-manifest.json`, `evidence/anvil1080-preflight-v2.json`, `evidence/anvil1080-offline-tests-v2.json`

이 결과는 실제 게임 보간 품질, 운동 정렬, Cemu 동시 실행,60FPS 달성을 증명하지 않는다.
