@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" arm64 -vcvars_ver=14.51
if errorlevel 1 exit /b 1
set "out=%~dp0build\npu-module"
set "vk=%~dp0..\..\Test\LSFG-Release\package-original\lsfg-cemu-arm64\third_party\vulkan_headers\include"
cl /nologo /std:c++20 /EHsc /O2 /W4 /utf-8 /MT /I"%vk%" "%out%\test_native_restore.cpp" /Fo"%out%\test_native_restore.obj" /Fe"%out%\test-native-restore.exe"
if errorlevel 1 exit /b 1
"%out%\test-native-restore.exe"
exit /b %ERRORLEVEL%
