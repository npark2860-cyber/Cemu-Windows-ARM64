@echo off
setlocal
set "CEMU_EXPERIMENTS=arm64-compare-reuse,jit-hotspot-native,perf-log"
set "CEMU_PERF_PRESET=ARM64_COMPARE_REUSE"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "CEMU_PERF_RUN_ID=%%i"
set "CEMU_PERF_BRANCH=runtime-experiments-arm64"
start "" "%~dp0Cemu-Test.exe"
endlocal
