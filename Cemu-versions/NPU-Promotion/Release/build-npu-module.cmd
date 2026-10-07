@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" arm64 -vcvars_ver=14.51
if errorlevel 1 exit /b 1
set "src=%~dp0source\dependencies\npu-cemu"
set "out=%~dp0build\npu-module"
set "ort=%~dp0..\..\Test\NPU-Experiment\ort-qnn-1.24.4"
set "vk=%~dp0..\..\Test\LSFG-Release\package-original\lsfg-cemu-arm64\third_party\vulkan_headers\include"
if not exist "%out%" mkdir "%out%"
cl /nologo /std:c++20 /EHsc /O2 /W4 /utf-8 /MT /Z7 /DNOMINMAX /DWIN32_LEAN_AND_MEAN /LD /I"%ort%\build\native\include" /I"%vk%" "%src%\npu_cemu.cpp" /Fo"%out%\npu_cemu.obj" /Fe"%out%\cemu_npu.dll" /link "%ort%\runtimes\win-arm64\native\onnxruntime.lib" /DEBUG:FULL /OPT:REF /OPT:ICF /PDB:"%out%\cemu_npu.pdb"
if errorlevel 1 exit /b 1
for %%t in (buffered_timeline ort_paths processing_profile) do (
    cl /nologo /std:c++20 /EHsc /O2 /W4 /utf-8 /MT /DNOMINMAX /DWIN32_LEAN_AND_MEAN "%src%\test_%%t.cpp" /Fo"%out%\test_%%t.obj" /Fe"%out%\test-%%t.exe"
    if errorlevel 1 exit /b 1
    "%out%\test-%%t.exe" "%out%\path-fixture"
    if errorlevel 1 exit /b 1
)
exit /b 0
