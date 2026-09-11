@echo off
setlocal
set "CEMU_EXPERIMENTS=arm64-cyclecheck-reuse,jit-iml-ra-hotspot,perf-log"
set "CEMU_PERF_PRESET=ARM64_CYCLECHECK_REUSE_VERIFY"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "CEMU_PERF_RUN_ID=%%I"
set "CEMU_PERF_BRANCH=runtime-experiments-arm64"
echo [ARM64 CYCLECHECK REUSE VERIFY] Candidate + targeted IML/native diagnostics enabled.
echo [ARM64 CYCLECHECK REUSE VERIFY] Expected: COUNT_CYCLES 12B, CYCLE_CHECK 8B at 0x02A281A0 and 0x0420CB80.
echo [ARM64 CYCLECHECK REUSE VERIFY] Load BOTW and close after both targeted JIT traces are emitted. PPC profiling is not required.
echo.
start "" "%~dp0Cemu-Test.exe"
endlocal
