@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" arm64 -vcvars_ver=14.51
if errorlevel 1 exit /b 1
pushd "%~dp0"
if not exist build mkdir build
if not exist runtime mkdir runtime
cl /nologo /std:c++20 /EHsc /O2 /W4 /utf-8 /MT /Z7 /DNOMINMAX /DWIN32_LEAN_AND_MEAN /I"ort-qnn-1.24.4\build\native\include" /I"..\LSFG-Release\package-original\lsfg-cemu-arm64\third_party\vulkan_headers\include" src\npu_vulkan_interop_probe.cpp /Fobuild\npu_vulkan_interop_probe.obj /Feruntime\npu-vulkan-interop-probe.exe /link "ort-qnn-1.24.4\runtimes\win-arm64\native\onnxruntime.lib" /DEBUG:FULL /OPT:REF /OPT:ICF /PDB:evidence\npu-vulkan-interop-probe.pdb
set "probeExit=%ERRORLEVEL%"
popd
exit /b %probeExit%
