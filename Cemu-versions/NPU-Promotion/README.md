# Cemu ARM64 — NPU 기능 정식 통합본

**2026-10-05 Release+SE 및 설치 폴더 수정:** 기존 `Release+SE/runtime/Cemu-Release-SE-NPU.exe`를 ABI 3으로 갱신했다. 아래 Release의 원본 해상도 보존·GPU 지연 대응과 사용자가 확인한 Fix 1의 UTF-8 햅틱 경로 수정을 함께 포함한다. NPU 모듈 소스와 DLL은 Release와 바이트가 같으며, 공통 CPU 검사 결과는 동일 소스에서 재사용했다. SE의 ARM64 빌드와 패키지 해시 검증은 새로 통과했다. 이번 SE 실행 파일의 게임 검증은 대기 중이다.

`C:\Emulators\Cemu_arm64`에는 NPU 의존 파일이 빠져 있었다. 확인 중 추가된 동일 파일 17개는 보존하고, 누락 파일 및 호환 SE 실행 파일 33개를 설치한 뒤 전체 50개 파일의 해시를 확인했다. 기존 일반 Release와 다른 실행 파일, AppData 설정·세이브는 보존했다. `portable` 폴더를 만들지 않았으며 Cemu/GPU/NPU는 실행하지 않았다. 설치 기록·교체 전 SE 백업은 `Release+SE/evidence/npu-runtime-20261005`에 있다. 현재 Release와 Release+SE는 ABI 3이고 진단 두 종류는 ABI 2이므로, 다른 패키지의 EXE와 NPU DLL을 섞지 않는다.

**2026-10-01 Release 버그 수정:** 기존 `Release/runtime/Cemu-Release-NPU.exe` 위치에서 원본 해상도 보존과 GPU 지연 대응을 수정했다. 원본은 출력 해상도 그대로 복사하고, NPU 입력과 생성 프레임에만 1080p/720p 처리 해상도를 적용한다. GPU/NPU 작업이 진행 중이면 표시 지연을 1~3프레임 범위에서 늘린다. 추가 지연은 OFF/ON·화면 재생성·긴 캡처 중단 때 초기화하며, 세션 중 원본을 건너뛰어 줄이지 않는다. 이미 표시한 원본보다 과거인 보간 결과는 계속 폐기한다. 원본 이미지 4개와 작업 슬롯 5개로 자원 사용을 제한했다.

동일 경로의 EXE·NPU DLL·한국어 설명을 함께 갱신했다(ABI 3). 설정·그래픽 팩·MLC·세이브는 변경하지 않았다. 이전 파일과 증거는 `Release/evidence/cadence-native-20261001/before`에 보존했다. CPU 검사 4491개 및 ARM64 빌드가 통과했으며, 원본 복사 검사는 실제 함수와 Vulkan 명령 모형을 사용한 CPU 검사다. **수정본의 GPU/NPU 및 게임 재검증은 아직 하지 않았다.** 아래의 공통 동작·동일 모듈에 대한 설명은 9월 29일 패키지 기준이며, 현재 Release와 Release+SE에는 위의 수정이 우선한다.

2026-09-29. 사용자가 NPU RC1의 게임 테스트를 마친 뒤 보고한 성공을 기준으로, 네 버전에 NPU 전용 기능을 통합했다. 각 버전의 Windows ARM64 빌드와 파일 검증이 완료됐다. **이후 사용자가 Release+SE에서 이어하기 후 종료를 보고했다.** 한글 햅틱 경로 예외를 CPU 검사로 재현·수정한 [Release+SE Fix 1](Release+SE-Fix1/README.md)을 별도로 준비했고 사용자가 해결을 확인했다. 다른 세 버전의 해당 증상은 미확인이다. 원본 기준 소스·배포물과 RC1은 보존했다.

| 버전 | 기준 커밋 | 실행 파일 | 소스 |
|---|---|---|---|
| Release | `c5205ccbc8ff` | [실행 파일](Release/runtime/Cemu-Release-NPU.exe) | [소스](Release/source/) |
| Release+SE | `9c0b899eb317` | [실행 파일](Release+SE/runtime/Cemu-Release-SE-NPU.exe) | [소스](Release+SE/source/) |
| Diagnostics | `6aa13388289e` | [실행 파일](Diagnostics/runtime/Cemu-Diagnostics-NPU.exe) | [소스](Diagnostics/source/) |
| Diagnostics+SE | `b18d8faae5a4` | [실행 파일](Diagnostics+SE/runtime/Cemu-Diagnostics-SE-NPU.exe) | [소스](Diagnostics+SE/source/) |

EXE만 따로 옮기지 말고 각 `runtime` 폴더 전체를 사용한다. 창 제목에 버전과 `NPU`가 표시된다. Release+SE는 사용자가 최종이라고 지정한 SE_Test/PR #5의 `9c0b899` 기능 코드를 기준으로 한다. Diagnostics는 ARM64 진단 UI를 유지한다. Diagnostics+SE는 별도로 확정한 Cue Capture V2 기준을 유지하며, Release+SE의 최신 일반 햅틱 기능과 동일한 소스라는 뜻은 아니다. SE 정책/햅틱 자료는 각 소스의 `enhanced_sound_policies`와 기존 버전의 배포물에 보존돼 있다.

## 사용

일반 설정의 그래픽 탭에서 **NPU 프레임 생성**을 켠다. 세션 시작 시 기본 OFF이며, OFF는 원본 표시다. Vulkan/SDR 출력이 필요하다. NPU 모듈과 자원은 미리 준비하고, ON 전환 시 이력을 초기화한다. 늦은 생성 프레임은 건너뛴다. 표시 FPS는 실제로 제출한 원본과 생성 프레임을 합산하므로 항상 고정 2배는 아니다.

- **1080p / 기본**, **720p / 성능** 중 선택한다. 해상도 변경은 다음 게임 실행부터 적용된다.
- 초기 코드 기본값은 1080p다. 이 로컬 패키지의 설정은 사용자가 마지막으로 테스트한 RC1의 720p 선택을 복사했다.
- Release와 Release+SE는 원본 출력 해상도를 보존하고 NPU 입력·생성 프레임에만 선택한 처리 해상도를 적용한다. 기존 ABI 2 진단 패키지는 원본·생성 이미지 모두 선택한 처리 해상도를 거친다. 기존 LSFG의 75% 설정과 다른 선택지다.
- 기존 GPU LSFG 기능은 포함하지 않는다. `Lossless.dll`은 필요 없다.
- 일반 설정의 언어 선택을 따른다. 기존 한국어 823개 항목을 보존하고 NPU 메뉴·설명·알림 11개를 추가했다. 다른 언어의 기존 번역은 보존했고 새 NPU 문구는 아직 영어로 표시된다. 번역 원본은 각 소스의 `i18n/npu`다.

각 runtime의 portable 설정·컨트롤러·그래픽 팩·셰이더 캐시는 독립 복사본이다. MLC 경로는 기존 저장 데이터 경로를 가리킨다. 저장 데이터를 복사하거나 수정하지 않았다. 이 폴더는 기존 실험 폴더의 MLC와 드라이버 저장소를 참조하므로, 다른 PC로 옮길 때에는 그 경로와 QNN 환경을 다시 설정해야 한다.

## 검증 범위

`verify-packages.ps1`는 실행 파일·DLL·모델·셰이더·언어 파일과 변경 소스의 SHA-256, 준비 당시 드라이버를 확인한다. Cemu나 GPU/NPU 검증 도구를 실행하지 않는다. 사용 후 바뀌는 portable 설정·캐시는 고정 파일 검증에서 제외한다.

모든 실행 파일은 ARM64이고, 각 기준 커밋·버전별 창 제목·NPU 빌드 옵션을 확인했다. 릴리즈 두 종류는 진단 코드 제외를 확인했다. 진단 버전은 소스·오브젝트·라이브러리·EXE의 진단 UI 마커를 확인했고, 진단+SE는 V2 CSV 기록 코드와 스키마를 확인했다. NPU 모듈·두 해상도 모델·SPIR-V·ORT/QNN 라이브러리는 사용자가 통과시킨 RC1과 바이트가 같다. RC1의 기존 CPU 검사 536개 결과는 그대로 적용되는 변경 없는 모듈/계약의 과거 검증 기록이다.

`evidence/user-acceptance.json`과 게임 로그에는 사용자 RC1 확인 기록이 있다. 마지막 720p 로그의 1440p 출력 안정 구간은 원본 약 35.0FPS, 생성 약 34.6FPS, accepted present 약 69.6FPS였다. 이는 동일 장면 A/B 성능 측정이나 실제 디스플레이 scanout 검증을 뜻하지 않는다.

## 소스와 재현 기록

각 `source`는 해당 기준 커밋 및 재귀 서브모듈을 복사한 별도 Git 저장소다. 기준 소스를 덮어쓰지 않고 `codex/npu-*` 브랜치에 CI 전처리·NPU 공통 변경·버전 제목·번역 변경을 적용했다. 아직 원격에 push하지 않았다. 변경 파일 목록/해시와 추적 파일 패치는 `evidence/source-files.json`, `evidence/source.patch`에 있고 새 파일도 source에 보존돼 있다.

`build.ps1 -Variant <버전> -Pass <새 이름>`으로 기존 로그를 보존하면서 다시 빌드한다. Q:가 다른 작업에 사용 중이면 중단한다. Release는 같은 Q: 경로와 도구 체인을 사용한 RC1 빌드 캐시를 재사용하되 동일 바이트의 입력만 기존 시각을 유지했다. 나머지는 각각 별도 빌드 디렉터리에서 시작했다. `shared-module-source`는 RC1 모듈·셰이더 소스 원본 복사본이며, 그 안의 과거 빌드 스크립트는 원래 실험 폴더의 상대 경로를 그대로 기록한다.

`NPU-PROMOTION.json`이 네 패키지의 색인이고 각 폴더의 `NPU-BUILD.json`이 고정 파일 manifest다. 원래 네 기준 버전의 정체성은 상위 `catalog.json`과 `Verify-Versions.ps1`로 별도 확인한다.

## 후속 수정 — Release+SE Unified 팩 형식 선언

2026-09-29 19:15 KST. 사용자 화면의 `Unsupported version`은 MLC 경로와 무관하게, 복사된 DualSense Experience 팩의 `version = 9` 선언 때문에 발생했다. 이 SE 기준은 팩 형식 8까지 지원한다. 설치된 73개 경로의 옵션을 SE 파서와 대조하고 참조한 햅틱 파일 12개가 있는지 확인한 뒤, Release+SE의 해당 rules.txt에서 형식 숫자만 8로 수정했다. 사운드/햅틱 내용·실행 파일·MLC는 변경하지 않았다. 원본과 수정 기록은 `Release+SE/evidence/se-pack-format-fix`에 있다. Cemu 재시작으로 팩 정의를 다시 읽어야 한다. 실제 컨트롤러/게임 재검증은 하지 않았다. 향후 패키징에도 동일한 검사를 적용했다.
