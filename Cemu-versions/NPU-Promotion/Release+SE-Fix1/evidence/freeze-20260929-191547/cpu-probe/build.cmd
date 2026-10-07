@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" arm64 -vcvars_ver=14.51
if errorlevel 1 exit /b 1
pushd "%~dp0"
cl /nologo /std:c++20 /EHsc /O2 /utf-8 /MT test_haptic_paths.cpp /Fe:test-haptic-paths.exe
set "probeExit=%ERRORLEVEL%"
popd
exit /b %probeExit%
