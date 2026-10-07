$ErrorActionPreference='Stop'
$global:LASTEXITCODE=0
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\angel\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools/add_enhanced_sound_cue_capture_v2.py
if($LASTEXITCODE -ne 0) {throw "Preprocessing step failed"}
