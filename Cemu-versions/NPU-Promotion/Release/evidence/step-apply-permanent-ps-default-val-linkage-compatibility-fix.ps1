$ErrorActionPreference='Stop'
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\angel\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' ./tools/compat/Apply-PSDefaultLinkageFix.py
if($LASTEXITCODE -ne 0) {throw "Preprocessing step failed"}
