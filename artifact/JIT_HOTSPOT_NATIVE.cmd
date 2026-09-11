@echo off
setlocal
set "CEMU_EXPERIMENTS=jit-hotspot-native,perf-log"
set "CEMU_PERF_PRESET=JIT_HOTSPOT_NATIVE"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "CEMU_PERF_RUN_ID=%%I"
set "CEMU_PERF_BRANCH=runtime-experiments-arm64"
echo [JIT HOTSPOT] BOTW guest-PC to ARM64 native mapping enabled.
echo [JIT HOTSPOT] Run the same BOTW scene, then Debug ^> View PPC threads.
echo [JIT HOTSPOT] Profile 0E001800 / Default Core 1 for 60 seconds.
echo.
start "" "%~dp0Cemu-Test.exe"
endlocal
