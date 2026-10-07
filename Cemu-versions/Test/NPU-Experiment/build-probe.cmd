@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" arm64 -vcvars_ver=14.51
if errorlevel 1 exit /b 1
pushd "%~dp0"
if not exist build mkdir build
if not exist runtime mkdir runtime
cl /nologo /std:c++20 /EHsc /O2 /W4 /utf-8 /MT /Z7 /DNOMINMAX /DWIN32_LEAN_AND_MEAN /I"ort-qnn-1.24.4\build\native\include" src\npu_probe.cpp /Fobuild\npu_probe.obj /Feruntime\npu-probe.exe /link "ort-qnn-1.24.4\runtimes\win-arm64\native\onnxruntime.lib" /DEBUG:FULL /OPT:REF /OPT:ICF /PDB:evidence\npu-probe.pdb
set "probeExit=%ERRORLEVEL%"
popd
exit /b %probeExit%
