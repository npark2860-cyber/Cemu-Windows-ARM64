@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" arm64 -vcvars_ver=14.51
if errorlevel 1 exit /b 1
pushd "%~dp0"
cl /nologo /std:c++20 /EHsc /O2 /W4 /utf-8 /MT /I"..\..\LSFG-Release\package-original\lsfg-cemu-arm64\third_party\vulkan_headers\include" build\test_overlay_contract.cpp /Fobuild\test_overlay_contract.obj /Febuild\test-overlay-contract.exe
set "buildExit=%ERRORLEVEL%"
popd
exit /b %buildExit%
