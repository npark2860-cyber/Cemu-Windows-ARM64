# Cemu 실행 파일 백업 (2026-10-07)

로컬 작업 폴더(`Cemu 최적화`)를 네 버전으로 정리하면서 만든 실행 파일 백업입니다. 비공개 저장소의 비공개 백업이며 배포용이 아닙니다.

| 버전 | 소스 브랜치 | 실행 파일 |
|---|---|---|
| 릴리즈 | `final-adreno-compat-arm64` (c5205cc) | `release-ci-run-34314391691.zip` (CI run 34314391691, Cemu.exe) |
| 릴리즈NPU | `codex/npu-release` | `release-npu-package.tgz` + `npu-shared-runtime.tgz` |
| 릴리즈+SE+NPU | `codex/npu-release-se` | `release-se-npu-package.tgz` + `npu-shared-runtime.tgz` |
| 진단NPU+SE | `codex/npu-diagnostics-se` | `diagnostics-se-npu-package.tgz` + `npu-shared-runtime.tgz` |

NPU 패키지를 복원할 때는 같은 폴더에 해당 버전 패키지와 `npu-shared-runtime.tgz`(QNN/ONNX Runtime DLL, 세 버전 공통)를 함께 풉니다. 패키지에는 portable 설정·컨트롤러·게임 프로필과 SE용 BotW 팩(BowAdaptiveTriggerV208, DualSenseExperience)이 들어 있고, 다시 받을 수 있는 커뮤니티 그래픽 팩, 셰이더 캐시, 세이브 데이터는 넣지 않았습니다.

`rpc-path.txt`는 이 PC의 Windows DriverStore 경로를 가리키므로 다른 PC에서는 다시 설정해야 합니다. 릴리즈NPU와 릴리즈+SE+NPU는 ABI 3, 진단NPU+SE는 ABI 2이므로 서로 다른 패키지의 EXE와 `cemu_npu.dll`을 섞지 마세요.

SHA-256은 `SHA256SUMS.txt`에 있습니다.
