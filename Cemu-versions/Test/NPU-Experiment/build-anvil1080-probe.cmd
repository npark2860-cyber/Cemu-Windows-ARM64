@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" arm64 -vcvars_ver=14.51
if errorlevel 1 exit /b 1
pushd "%~dp0"
for %%S in (generate pack compose) do (
  tools\glslang-16.6.0\bin\glslang.exe -V --target-env vulkan1.1 shaders\anvil1080-%%S.comp -o shaders\anvil1080-%%S.spv
  if errorlevel 1 exit /b 1
)
cl /nologo /std:c++20 /EHsc /O2 /W4 /utf-8 /MT /Z7 /DNOMINMAX /DWIN32_LEAN_AND_MEAN /I"ort-qnn-1.24.4\build\native\include" /I"..\LSFG-Release\package-original\lsfg-cemu-arm64\third_party\vulkan_headers\include" src\anvil1080_pipeline_probe.cpp /Fobuild\anvil1080_pipeline_probe.obj /Feruntime\anvil1080-pipeline-probe.exe /link "ort-qnn-1.24.4\runtimes\win-arm64\native\onnxruntime.lib" /DEBUG:FULL /OPT:REF /OPT:ICF /PDB:evidence\anvil1080-pipeline-probe.pdb
set "probeExit=%ERRORLEVEL%"
popd
exit /b %probeExit%
