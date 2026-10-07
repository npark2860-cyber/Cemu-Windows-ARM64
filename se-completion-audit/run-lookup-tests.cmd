@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" arm64
if errorlevel 1 exit /b 1
cl /nologo /std:c++20 /EHsc /W4 /O2 /I"..\test-se\tests\enhanced_sound\stubs" /I"..\test-se\src" "..\test-se\tests\enhanced_sound\lookup_tests.cpp" /Fe:enhanced_sound_lookup_tests.exe /Fo:lookup_tests.obj
if errorlevel 1 exit /b 1
enhanced_sound_lookup_tests.exe
exit /b %errorlevel%
