$ErrorActionPreference='Stop'
$global:LASTEXITCODE=0
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\angel\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' ./tools/diagnostics/release/Verify-ReleaseDiagnosticUIBuild.py --stage source --stamp-source
if($LASTEXITCODE -ne 0) {throw "Preprocessing step failed"}
