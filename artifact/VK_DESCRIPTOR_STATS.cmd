@echo off
setlocal
set "CEMU_EXPERIMENTS=vk-descriptor-stats,perf-log"
set "CEMU_PERF_PRESET=VK_DESCRIPTOR_STATS"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "CEMU_PERF_RUN_ID=%%I"
set "CEMU_PERF_BRANCH=runtime-experiments-arm64"
echo [VULKAN DESCRIPTOR] Report-only descriptor path counters enabled.
echo [VULKAN DESCRIPTOR] Run the same BOTW fixed scene for about 60 seconds.
echo [VULKAN DESCRIPTOR] Expected log tag: [VK_DESCRIPTOR_STATS]
echo.
start "" "%~dp0Cemu-Test.exe"
endlocal
