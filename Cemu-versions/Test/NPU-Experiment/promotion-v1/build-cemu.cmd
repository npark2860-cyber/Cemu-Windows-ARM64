@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" arm64 -vcvars_ver=14.51
if errorlevel 1 exit /b 1
"C:\Program Files\CMake\bin\cmake.exe" -S Q:/source -B Q:/build -UCEMU_ENABLE_LSFG -DCEMU_ENABLE_NPU=ON
if errorlevel 1 exit /b 1
"C:\Program Files\CMake\bin\cmake.exe" --build Q:/build --target CemuBin --parallel 2
exit /b %ERRORLEVEL%
