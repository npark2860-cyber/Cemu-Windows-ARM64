# Test_SE 로컬 미완료 파일 확인 결과

확인일: 2026-09-20

## 결론

추가로 업로드해야 할 SE 코드나 테스트 변경은 없다. 로컬에 남은 변경은 이미 GitHub에 반영되어 최신 성공한 Test_SE 빌드에 포함되어 있다. 로컬 checkout은 이전 기준인 668acee에 머물러 있어 변경 파일로 표시된다. 이를 미반영 변경으로 오해해서 다시 적용하면 안 된다.

- 실제 빌드 브랜치: `build/test-se-once`
- 성공한 빌드 HEAD: `4b55a6d40167b96b899e6fbe782bc9cf3736ab3f`
- 최적화 반영 commit: `b676b9be25941689dddeae2649b574c41fffd956`
- 빌드: https://github.com/npark2860-cyber/Cemu-Windows-ARM64/actions/runs/35461865661
- 결과: completed / success

## 비교한 파일

다음 7개 파일은 줄바꿈 형식을 정규화하면 로컬과 성공한 빌드의 Git 소스 내용이 같다. 추적 중인 C++ 파일 4개는 `git diff --ignore-cr-at-eol --exit-code`도 통과했다.

- `src/Cafe/OS/common/BotWSoundFingerprintCatalog.h`
- `src/Cafe/OS/common/BotWSoundSourceTracer.h`
- `src/Cafe/OS/common/EnhancedSoundRouter.h`
- `src/Cafe/OS/libs/snd_core/ax_voice.cpp`
- `tests/enhanced_sound/CMakeLists.txt`
- `tests/enhanced_sound/lookup_tests.cpp`
- `tests/enhanced_sound/stubs/Cafe/HW/MMU/MMU.h`

## 이번에 완료한 검증

Visual Studio 2026 MSVC 14.51, ARM64, C++20, /O2, /W4로 기존 독립 테스트를 컴파일하고 실행했다. Cemu 바이너리 빌드가 아닌 production lookup headers를 사용하는 테스트 실행이다.

- PASS: glob, 49-rule routes, collisions, invalidation, concurrent table updates
- PASS: ranges, overlap, miss invalidation, eviction, same-address BARS writes
- PASS: dedup identity, candidate order, ambiguity, guest writes, catalog eviction/re-registration
- Exit code: 0
- 기존 `EnhancedSoundPackedBars.h:157`의 signed/unsigned 비교 경고 C4018 1건 발생. 이번 작업에서 해당 소스는 변경하지 않았다.

이 검증은 lookup 결과와 캐시 무효화 동작에 관한 것이다. 새 FPS 측정이나 실기 테스트를 수행했다는 의미는 아니다. 실기 테스트 완료는 사용자의 보고에 따른다.

## 처리 범위

C++ 수정, branch 전환, commit/push, GitHub workflow 재실행은 하지 않았다. 기존 로컬 변경과 `cemu.zip`은 삭제하지 않고 보존했다. `cemu.zip`은 Git 메타데이터도 포함하는 로컬 소스 스냅샷으로, 추가 코드 반영에 필요하지 않으며 업로드하지 않았다.

독립 테스트 실행 스크립트와 결과는 이 audit 디렉터리에만 저장했다. 실행은 이 디렉터리에서 `cmd.exe /d /c .\run-lookup-tests.cmd`로 재현할 수 있다.
