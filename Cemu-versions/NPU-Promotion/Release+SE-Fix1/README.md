# Release+SE NPU — Fix 1

이어하기 후 종료된 Release+SE에서 발견한 **한글 경로의 햅틱 파일 로딩 예외**를 수정한 별도 후보 빌드다. 원본 Release+SE 및 다른 세 버전은 교체하지 않았다.

실행 파일: [Cemu-Release-SE-NPU-Fix1.exe](runtime/Cemu-Release-SE-NPU-Fix1.exe). 창 제목에 `Release+SE | NPU | Fix 1`이 표시된다. EXE만 옮기지 말고 runtime 폴더 전체를 사용한다.

## 변경과 확인

UTF-8 문자열인 hapticPath를 Windows 기본 문자셋으로 암묵 변환하면서 예외가 발생했다. `_utf8ToPath()`를 사용해 명시적으로 변환한다. 실제 기능 변경은 한 줄이고, 다른 두 소스 변경은 창 제목의 Fix 1 표시다. 그 외 부모 패키지 소스 1669개와 NPU DLL·모델·셰이더·QNN·번역 파일은 같다.

CPU 검사에서 기존 변환은 ACP949 환경의 한글 경로에 있는 12개 햅틱 파일 모두에서 예외를 발생시켰다. 수정 변환은 12개 모두 로딩했고, 직접 유니코드 경로로 읽은 결과와 샘플·루프 정보가 일치했다(3386개 검사). ARM64 Release 빌드와 패키지 해시 검증을 통과했다. 이는 실제 게임·컨트롤러 재검증을 대신하지 않는다.

보존한 사용자 로그에서 NPU는 OFF, 추론 횟수는 0이었다. 이 경로 예외는 재현했지만 기존 Windows 오류 기록의 모든 크래시가 같은 원인이라고 단정하지 않는다.

## 직접 확인

1. 기존 Cemu를 종료하고 위 Fix 1을 실행한다.
2. NPU OFF 상태에서 같은 게임의 이어하기를 확인한다.
3. 정상 진행되면 NPU ON 상태도 확인한다.

현재 Release+SE의 설정·컨트롤러·게임 설정·그래픽 팩·셰이더 캐시를 독립 복사했다. MLC 선택은 `C:/Users/angel/AppData/Roaming/Cemu/mlc01` 그대로다. MLC 폴더 및 세이브는 복사하거나 수정하지 않았다. Unified 팩의 형식 8 수정도 보존했다.

`verify.ps1`은 고정 파일과 변경 소스의 해시만 검사하며 Cemu·GPU·NPU·컨트롤러를 실행하지 않는다. 사용 후 바뀌는 portable 설정과 캐시는 고정 해시 검사에서 제외한다. 소스 차이는 `evidence/fix1-vs-parent.patch`, CPU 재현과 당시 로그는 `evidence/freeze-20260929-191547`에 있다. 부모 빌드와 이 빌드의 정체성은 `NPU-BUILD.json`에 기록했다.

Diagnostics+SE는 이전 CueCaptureV2 소스를 사용하며 이 일반 햅틱 경로가 없다. 사용자는 아직 그 버전에서 이어하기를 시험하지 않았다. 같은 프리징의 재현 여부는 미확인이다.
