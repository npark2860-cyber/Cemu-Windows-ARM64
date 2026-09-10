@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0profiling\CPU_PROFILE_OPEN_LAST.ps1"
endlocal
