@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" arm64
if errorlevel 1 exit /b 1
cl /nologo /std:c++20 /EHsc /W4 /O2 /I"generic-voice-haptics\tests\enhanced_sound\stubs" /I"generic-voice-haptics\src" "generic-voice-haptics\tests\enhanced_sound\lookup_tests.cpp" /Fe:se-completion-audit\generic_lookup_tests.exe /Fo:se-completion-audit\generic_lookup_tests.obj
if errorlevel 1 exit /b 1
se-completion-audit\generic_lookup_tests.exe
exit /b %errorlevel%
