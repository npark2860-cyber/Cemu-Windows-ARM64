@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" arm64 -vcvars_ver=14.51
if errorlevel 1 exit /b 1
pushd "%~dp0"
cl /nologo /std:c++20 /EHsc /O2 /W4 /utf-8 /MT /DNOMINMAX /DWIN32_LEAN_AND_MEAN /I"..\ort-qnn-1.24.4\build\native\include" /I"..\..\LSFG-Release\package-original\lsfg-cemu-arm64\third_party\vulkan_headers\include" module-smoke-probe.cpp /Fobuild\module-smoke-probe.obj /Febuild\module-smoke-probe.exe /link "..\ort-qnn-1.24.4\runtimes\win-arm64\native\onnxruntime.lib"
set "buildExit=%ERRORLEVEL%"
popd
exit /b %buildExit%
