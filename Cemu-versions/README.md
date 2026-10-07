# Cemu 기준 버전 — 확정 목록

**NPU 통합본:** 사용자 RC1 검증 후 만든 네 버전의 소스·실행 파일은 [NPU-Promotion](NPU-Promotion/README.md)에 있다. 아래 목록은 보존한 기존 기준 배포물이며, 새 NPU 빌드의 색인은 `NPU-Promotion/NPU-PROMOTION.json`이다.

**기준 버전은 네 개다. 최종 SE는 사용자가 지정한 `C:\Emulators\Cemu_arm64\Cemu_se_test.exe`다.**
Test는 별도의 고정 버전이 아니라 그때그때 테스트하는 용도다.

## 실행 파일로 확인한 기준

2026-09-29에 설치된 EXE와 GitHub CI 배포물을 SHA-256으로 대조했다. 아래 파일의 출처를 확인한 뒤 사용자 요청으로 이전 `Cemu_se.exe`를 폐기했다. 최종본과 나머지 파일은 그대로 유지했다.

| 설치 파일 | 확정한 역할 | 대응 빌드 |
|---|---|---|
| `Cemu.exe` | 릴리즈 기준 | [34314391691](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/actions/runs/34314391691) |
| `Cemu_se_test.exe` | **최종 SE / 릴리즈+SE 기준** | [35507685980](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/actions/runs/35507685980) |
| `Cemu-Diagnostics.exe` | 진단 기준 | [34314435136](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/actions/runs/34314435136) |
| ~~`Cemu_se.exe`~~ | **폐기 완료 — 휴지통으로 이동** | 이전 빌드 35399518440 |

진단+SE는 위 설치 폴더에서 확인되지 않아 아래 별도 소스/배포물로 보관했다.

## 로컬에 정리한 네 버전

| 역할 | 소스 | 기준 소스 커밋 | 실행 파일 |
|---|---|---|---|
| 릴리즈 | `Release/source` | `c5205ccbc8ff` | [Cemu.exe](Release/binaries/run-34314391691/Cemu.exe) |
| **최종 SE / 릴리즈+SE** | `Release+SE/source` | **`9c0b899eb317`** | [Cemu.exe](Release+SE/binaries/run-35507685980/Cemu.exe) |
| 진단 | `Diagnostics/source` | `6aa13388289ed` | [Cemu-Diagnostics.exe](Diagnostics/binaries/run-34314435136/Cemu-Diagnostics.exe) |
| 진단+SE | `Diagnostics+SE/source` | `b18d8faae5a4` | [Cemu-EnhancedSound-CueCaptureV2-ARM64.exe](Diagnostics+SE/binaries/run-35435066660/Cemu-EnhancedSound-CueCaptureV2-ARM64.exe) |

소스에는 해당 커밋의 재귀 서브모듈을 포함했다. 각 역할의 `archives/`는 원본 배포 ZIP, `binaries/run-번호/`는 압축 해제본이다. 배포 ZIP이 EXE만 제공한 경우 게임/설정/저장 데이터/별도 DLL을 임의로 추가하지 않았다.

## 최종 SE의 정확한 출처

- 사용자가 최종이라고 지정한 파일: `C:\Emulators\Cemu_arm64\Cemu_se_test.exe`.
- SHA-256: `e8791dbea63e85111c1b9a4feab98f31ca469b1802caf379aa5120cffa2dc9c8`.
- [PR #5](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/pull/5)의 마지막 기능 수정: `9c0b899eb31792353909ac7ff81ed42b2dd7f8fa`, 한국시간 2026-09-20 20:20:30.
- 그 다음 커밋 `e851c8377c2c0fbcdc9042cf3971f60f0395d78b`은 빌드 workflow만 변경했다. 기능 코드는 동일하다.
- CI run `35507685980` 성공, artifact `cemu-arm64-test-se-astra` 생성. 설치된 파일과 SHA-256 일치.
- 현재 관련 브랜치, PR 목록, 최신 전체 CI 기록에서 그보다 새로운 관련 코드 변경을 찾지 못했다.
- GitHub에서는 PR #5가 아직 `test_SE` 대상 Draft/open 상태다. **사용자의 최종 SE 지정과 GitHub 병합 상태를 구분한다.** 이번 작업에서 PR/브랜치를 병합하거나 push하지 않았다.
- PR 본문의 과거 “full build pending” 이후에 위 CI 빌드가 성공했다. 실제 게임/컨트롤러 검증 완료 여부는 빌드 성공만으로 판단하지 않는다.

## 이전 버전 보관

- 원격 `Release+SE`의 기존 HEAD `240b52c853f3` 소스: `Release+SE/history/source-240b52c853f3/`.
- 이전 `Cemu_se.exe`, 그 대응 로컬 배포 EXE와 ZIP은 사용자 요청으로 휴지통으로 옮겼다. 사용하거나 다시 배포하지 않는다. 폐기 기록: `evidence/discarded-old-se.json`.
- 9월 19일의 이전 SE/haptic Test 스냅샷: `Test/source/`, `Test/binaries/run-35453884407/`.
- 기존 `../Cemu-release`는 실제 `Release+SE` 브랜치의 이전 기준 소스다.
- 기존 `../source-review`는 미커밋 LSFG 실험 변경을 포함한다. 기준 릴리즈로 사용하지 않는다.
- 이전 SE 참조 소스는 이력 대조용으로만 보관하며 빌드 기준에서 제외한다. 기존 작업 폴더 및 게임 설정/저장 데이터는 보존했다.

## 검증 및 LSFG 작업

`catalog.json`에 역할, 브랜치, 커밋, CI/workflow/artifact, ZIP 및 파일 SHA-256, 설치본 일치를 기록했다. `./Verify-Versions.ps1`로 네 기준 소스/서브모듈/파일 정체성을 확인할 수 있다. 이는 실행 안정성이나 LSFG 성공을 판정하는 검사가 아니다.

로컬 빌드는 실제 workflow의 전처리까지 재현해야 한다. 릴리즈는 빌드 전에 pre-e834 호환성, PS DEFAULT_VAL, FSR1 EASU/RCAS, 창 제목 패치를 적용한다.

LSFG는 별도 실험 환경에서 초기화, OFF 패스스루, ON 생성/표시, 전환, 종료를 검증한다. 성공 후 **위 네 기준 버전에 LSFG 변경만 각각 통합**한다. 최종 SE에 포함된 최신 기능을 이전 `Cemu_se.exe` 수준으로 되돌리지 않는다.
