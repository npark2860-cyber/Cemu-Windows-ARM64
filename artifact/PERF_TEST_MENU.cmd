@echo off
setlocal EnableExtensions
cd /d "%~dp0"

:menu
cls
echo ============================================================
echo          Cemu ARM64 Performance Benchmark Menu
echo ============================================================
echo.
echo  [0] BASELINE
echo  [1] UDIV64 only
echo  [2] No Extra Fence only
echo  [3] ARM64 Serialize only
echo  [4] Skip WAW Barrier only
echo  [5] Skip RT Load Barrier only
echo  [6] Force Render Pass Reuse only
echo  [7] ARM64 NEON Texture Hash only
echo  [Q] Quit
echo.
echo Test rule for every preset:
echo   - Same BOTW save / location / camera / settings
echo   - After the scene is stable, leave it untouched for 1 minute
echo   - Then keep it untouched for 5 minutes
echo   - Close Cemu after the 5 minute measurement
echo.
echo Cemu writes a sample every 10 seconds.
echo Each run is also preserved in the Cemu user-data perf-logs folder.
echo ============================================================
set "SEL="
set /p "SEL=Select preset: "

if /I "%SEL%"=="Q" goto :eof
if "%SEL%"=="0" goto baseline
if "%SEL%"=="1" goto udiv64
if "%SEL%"=="2" goto nofence
if "%SEL%"=="3" goto serialize
if "%SEL%"=="4" goto skipwaw
if "%SEL%"=="5" goto skiprtload
if "%SEL%"=="6" goto passreuse
if "%SEL%"=="7" goto texturehashneon
goto menu

:baseline
set "CEMU_PERF_PRESET=BASELINE"
set "CEMU_EXPERIMENTS=perf-log"
goto run

:udiv64
set "CEMU_PERF_PRESET=UDIV64"
set "CEMU_EXPERIMENTS=timer-udiv64,perf-log"
goto run

:nofence
set "CEMU_PERF_PRESET=NO_EXTRA_FENCE"
set "CEMU_EXPERIMENTS=timer-no-extra-fence,perf-log"
goto run

:serialize
set "CEMU_PERF_PRESET=ARM64_SERIALIZE"
set "CEMU_EXPERIMENTS=timer-arm64-serialize,perf-log"
goto run

:skipwaw
set "CEMU_PERF_PRESET=SKIP_WAW_BARRIER"
set "CEMU_EXPERIMENTS=perf-skip-waw-barrier,perf-log"
goto run

:skiprtload
set "CEMU_PERF_PRESET=SKIP_RT_LOAD_BARRIER"
set "CEMU_EXPERIMENTS=perf-skip-rt-load-barrier,perf-log"
goto run

:passreuse
set "CEMU_PERF_PRESET=FORCE_PASS_REUSE"
set "CEMU_EXPERIMENTS=perf-force-pass-reuse,perf-log"
goto run

:texturehashneon
set "CEMU_PERF_PRESET=TEXTURE_HASH_NEON"
set "CEMU_EXPERIMENTS=texture-hash-neon,perf-log"
goto run

:run
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "CEMU_PERF_RUN_ID=%%I"
set "CEMU_PERF_BRANCH=runtime-experiments-arm64"
echo.
echo ------------------------------------------------------------
echo Preset      : %CEMU_PERF_PRESET%
echo Run ID      : %CEMU_PERF_RUN_ID%
echo Experiments : %CEMU_EXPERIMENTS%
echo ------------------------------------------------------------
echo.
start "" /wait "%~dp0Cemu-Test.exe"
echo.
echo Cemu closed. The performance result has been preserved automatically.
pause
goto menu
