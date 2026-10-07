@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" arm64 -vcvars_ver=14.51
if errorlevel 1 exit /b 1
pushd "%~dp0"
if not exist build mkdir build
cl /nologo /std:c++20 /EHsc /O2 /W4 /utf-8 /MT /Z7 /DNOMINMAX /DWIN32_LEAN_AND_MEAN /LD /I"..\ort-qnn-1.24.4\build\native\include" /I"..\..\LSFG-Release\package-original\lsfg-cemu-arm64\third_party\vulkan_headers\include" npu_cemu.cpp /Fobuild\npu_cemu.obj /Febuild\cemu_npu.dll /link "..\ort-qnn-1.24.4\runtimes\win-arm64\native\onnxruntime.lib" /DEBUG:FULL /OPT:REF /OPT:ICF /PDB:build\cemu_npu.pdb
if errorlevel 1 exit /b 1
cl /nologo /std:c++20 /EHsc /O2 /W4 /utf-8 /MT test_buffered_timeline.cpp /Fobuild\test_buffered_timeline.obj /Febuild\test-buffered-timeline.exe
if errorlevel 1 exit /b 1
cl /nologo /std:c++20 /EHsc /O2 /W4 /utf-8 /MT /DNOMINMAX /DWIN32_LEAN_AND_MEAN test_ort_paths.cpp /Fobuild\test_ort_paths.obj /Febuild\test-ort-paths.exe
if errorlevel 1 exit /b 1
cl /nologo /std:c++20 /EHsc /O2 /W4 /utf-8 /MT test_processing_profile.cpp /Fobuild\test_processing_profile.obj /Febuild\test-processing-profile.exe
set "buildExit=%ERRORLEVEL%"
popd
exit /b %buildExit%
