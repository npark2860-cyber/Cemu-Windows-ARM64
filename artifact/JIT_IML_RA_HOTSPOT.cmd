@echo off
setlocal
set "CEMU_EXPERIMENTS=jit-hotspot-native,jit-iml-ra-hotspot,perf-log"
set "CEMU_PERF_PRESET=JIT_IML_RA_HOTSPOT"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "CEMU_PERF_RUN_ID=%%I"
set "CEMU_PERF_BRANCH=runtime-experiments-arm64"
echo [JIT ROOT CAUSE] Targeted IML -^> RA -^> AArch64 diagnostics enabled.
echo [JIT ROOT CAUSE] Primary guest target: 0x0420CB80.
echo [JIT ROOT CAUSE] Branch-target follow: 0x02A281A0.
echo [JIT ROOT CAUSE] Run the same BOTW scene, then Debug ^> View PPC threads.
echo [JIT ROOT CAUSE] Profile 0E001800 / Default Core 1 for 60 seconds.
echo.
start "" "%~dp0Cemu-Test.exe"
endlocal
