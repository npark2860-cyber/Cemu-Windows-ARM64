@echo off
setlocal
set "CEMU_EXPERIMENTS=perf-log"
set "CEMU_PERF_PRESET=ARM64_RNAME_LDP_BASELINE"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "CEMU_PERF_RUN_ID=%%I"
set "CEMU_PERF_BRANCH=runtime-experiments-arm64"
echo [ARM64 RNAME LDP] Baseline. Candidate disabled.
echo [ARM64 RNAME LDP] Use the fixed BOTW scene and keep the camera/player still.
echo.
start "" "%~dp0Cemu-Test.exe"
endlocal
