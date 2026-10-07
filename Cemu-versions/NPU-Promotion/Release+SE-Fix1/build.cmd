@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" arm64 -vcvars_ver=14.51
if errorlevel 1 exit /b 1
set "PATH=Q:\toolchain;C:\Program Files\CMake\bin;C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja;%PATH%"
rem The parent build cache uses these same virtual paths. CMake and dependency
rem inputs are byte-identical; Ninja determines the required rebuilds.
cmake --build Q:/build --target CemuBin --parallel 4
exit /b %ERRORLEVEL%
