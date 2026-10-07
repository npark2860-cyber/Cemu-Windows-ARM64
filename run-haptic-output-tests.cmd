@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" arm64
if errorlevel 1 exit /b 1
cl /nologo /std:c++20 /EHsc /W4 /O2 /I"generic-voice-haptics\src" /I"generic-voice-haptics\dependencies\Gamepad-Core\Source\Public" "generic-voice-haptics\tests\enhanced_sound\haptic_output_tests.cpp" "generic-voice-haptics\dependencies\Gamepad-Core\Source\Private\GImplementations\Utils\GamepadOutput.cpp" "generic-voice-haptics\dependencies\Gamepad-Core\Source\Private\GCore\Utils\CR32.cpp" /Fe:se-completion-audit\haptic_output_tests.exe /Fo:se-completion-audit\
if errorlevel 1 exit /b 1
se-completion-audit\haptic_output_tests.exe
exit /b %errorlevel%
