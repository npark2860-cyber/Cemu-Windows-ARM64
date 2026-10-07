# Cemu 최적화 작업 기록 (2026-10-07)

로컬 작업 폴더 `Cemu 최적화`를 네 버전(릴리즈, 릴리즈NPU, 릴리즈+SE+NPU, 진단NPU+SE)으로 정리하면서 지운 실험 폴더의 문서, 스크립트, 측정 기록을 보관한 브랜치입니다. 1MB 미만의 텍스트 파일(md, py, ps1, cmd, cpp, h, json, csv, txt, xml, ini, 셰이더 소스 등)만 들어 있습니다.

넣지 않은 것: 전체 Cemu 소스 사본(GitHub 브랜치에 이미 있음), 빌드 결과물, 도구 체인, 셰이더 캐시, 그래픽 팩, 대용량 로그, 게임 실행 파일(rpx/rpl).

관련 브랜치:
- `codex/npu-release`, `codex/npu-release-se`, `codex/npu-diagnostics-se`: 정리 후 남긴 NPU 세 버전의 소스
- `codex/lsfg-release`: Test/LSFG-Release의 GPU LSFG 실험 소스
- `backup/runtime-2026-10-07`: 네 버전의 실행 파일 패키지
