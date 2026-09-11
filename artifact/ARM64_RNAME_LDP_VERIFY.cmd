@echo off
setlocal
set "CEMU_EXPERIMENTS=arm64-rname-ldp,jit-iml-ra-hotspot,perf-log"
set "CEMU_PERF_PRESET=ARM64_RNAME_LDP_VERIFY"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "CEMU_PERF_RUN_ID=%%I"
set "CEMU_PERF_BRANCH=runtime-experiments-arm64"
echo [ARM64 RNAME LDP VERIFY] LDP candidate + targeted JIT code mapping enabled.
echo [ARM64 RNAME LDP VERIFY] Load the same BOTW scene, wait until gameplay is stable, then close Cemu.
echo [ARM64 RNAME LDP VERIFY] No PPC thread profiling is required for this verification run.
echo.
start "" "%~dp0Cemu-Test.exe"
endlocal
