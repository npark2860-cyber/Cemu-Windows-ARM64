@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" arm64
if errorlevel 1 exit /b 2
cl /nologo /std:c++20 /EHsc /W4 /O2 /I"se-completion-audit\haptic-before" /I"generic-voice-haptics\src" "generic-voice-haptics\tests\enhanced_sound\haptic_tests.cpp" /Fe:se-completion-audit\haptic_before.exe /Fo:se-completion-audit\haptic_before.obj
if errorlevel 1 exit /b 2
se-completion-audit\haptic_before.exe
exit /b %errorlevel%
