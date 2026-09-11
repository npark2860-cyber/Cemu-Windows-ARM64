@echo off
setlocal
set "CEMU_EXPERIMENTS=arm64-cyclecheck-reuse,perf-log"
set "CEMU_PERF_PRESET=ARM64_CYCLECHECK_REUSE_CANDIDATE"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "CEMU_PERF_RUN_ID=%%I"
set "CEMU_PERF_BRANCH=runtime-experiments-arm64"
echo [ARM64 CYCLECHECK REUSE] Candidate enabled.
echo [ARM64 CYCLECHECK REUSE] Use the same fixed BOTW scene and keep the camera/player still.
echo.
start "" "%~dp0Cemu-Test.exe"
endlocal
